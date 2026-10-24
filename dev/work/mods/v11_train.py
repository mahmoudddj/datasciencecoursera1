"""V11 training and evaluation driver (on top of v9_train / v10_train).

Prespecified protocol (19 Oct 2026, before any _11 result):
- losses: 'utility_weighted_bce' (PRIMARY), 'bce', 'tls' (temporal label smoothing);
  the hazard arm trains a discrete-time survival likelihood. Loss comparators run on the arms
  listed in cfg['loss_comparison_arms']. The loss carried to the full cohort is chosen by the
  rank-average of VALIDATION-split utility and AUPRC (never on test).
- early stopping on validation AUPRC (patience cfg['patience']); AdamW weight decay 1e-4.
- self-supervised pretraining on an unlabelled corpus (no sepsis labels; protected patients
  excluded): 'site' encoder = the target database's corpus; 'pooled' = both databases.
- evaluation: the v10 panel (utility, AUPRC, AUROC, sensitivity at the false-alarm budget,
  warning time, false alarms/day, calibration) + lead time versus the first antibiotic order,
  a conformal alarm policy, trajectory-rich hours, transfer rows (model of one database applied
  to the other database's DEVELOPMENT patients; the final holdout stays sealed), and a
  prespecified mean ensemble.
"""
from pathlib import Path
import json,os,gc,math,pickle
import numpy as np
import pandas as pd
import torch
from torch import nn
from sklearn.metrics import average_precision_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from v9_train import (AGE_SCALE,SequenceStore,fit_normalizer,loader,batch_to,seed_all,predict,calibrate,apply_calibration,
    select_threshold,evaluate,clustered_ci,paired_difference,atomic_json,atomic_torch,train_observers,OSTA_FAMILY)
from v9_models import ObserverBank,ExperimentModel
from v10_train import tabular_arrays,tabular_predict,utility_block,hospital_ci
from v10_protocol import partition,protected_group
from v10_evaluation import patient_utilities,normalized_from,utility_threshold_sweep
from v11_models import make_model,Pretrainer,SSL_ARMS,measured_channels,FAST,HAZARD_EDGES,HEAD_HORIZONS
from v9_data import signature,sha

V9_ARMS=['osta','output_fusion','cnn']
TABULAR=['logistic','boosted_tree','signature_boosted_tree']
NEURAL_V11=['flat_osta','flat_osta_heads','grud','tcn','cnn_osta','ssl_cnn_osta','ssl_cnn_flat','ssl_cnn_osta_pooled','ssl_cnn_flat_pooled','event_osta','hazard_ssl_cnn_osta']
ENSEMBLE_MEMBERS=['osta','cnn','ssl_cnn_osta']
PROXY_FEATURES=['Med_Hydrocortisone_24h','Imaging_24h','Prophylaxis_Surgical_24h','Prophylaxis_Medical']

# ----------------------------------------------------------------------------- losses
def utility_gap_weight(delta):
    """U_TP - U_FN of the PhysioNet utility as a function of hours from onset (delta = hour - onset):
    1.0 at -6 h rising linearly to 2.0 at +3 h."""
    return 1.+(delta.clamp(-6.,3.)+6.)/9.

def targets_and_weights(batch,onsets,loss,horizon=6,tls_tau=12.):
    """(target, weight) over all hours. weight=0 excludes an hour. onsets: (B,) hours, NaN if no onset."""
    y=batch['y'];elig=batch['eligible'];mask=batch['mask'];hours=batch['hours']
    on=onsets.view(-1,1);has=torch.isfinite(on);delta=torch.where(has,hours-torch.nan_to_num(on),torch.full_like(hours,-1e9))
    if loss=='bce':return y,elig
    if loss=='utility_weighted_bce':
        post=has&(delta>=0)&(delta<=3)&(mask>.5)          # onset .. onset+3 h: training positives only
        target=torch.where(post,torch.ones_like(y),y);use=((elig>.5)|post).float()
        pos=(target>.5)&(use>.5);w=torch.where(pos,utility_gap_weight(delta),torch.ones_like(y))
        if pos.any():w=torch.where(pos,w/w[pos].mean(),w)   # positive weights normalised to mean 1
        return target,w*use
    if loss=='tls':
        d=-delta  # hours until onset
        ramp=.5*torch.clamp(1-(d-horizon)/tls_tau,min=0.)
        soft=torch.where(has&(d>horizon)&(elig>.5),ramp,y)
        return soft,elig
    raise ValueError('Unknown loss '+str(loss))

def hazard_nll(hazards,batch,onsets):
    """Discrete-time survival likelihood over HAZARD_EDGES bins for every pre-onset (or non-septic)
    observed hour; censored at the end of the observed stay. hazards: (B,T,K) in (0,1)."""
    hours=batch['hours'];mask=batch['mask'];on=onsets.view(-1,1);has=torch.isfinite(on)
    last=(hours*mask).max(1,keepdim=True).values;c=last-hours               # known follow-up from each hour
    d=torch.where(has,torch.nan_to_num(on)-hours,torch.full_like(hours,float('inf')))
    use=(mask>.5)&((~has)|(d>0))
    edges=torch.tensor(HAZARD_EDGES,device=hours.device);lo=edges[:-1].view(1,1,-1);hi=edges[1:].view(1,1,-1)
    dd=d.unsqueeze(-1);cc=c.unsqueeze(-1)
    event=(dd>lo)&(dd<=hi)&(dd<=cc)                                          # onset falls in this bin and is observed
    survived=(hi<=cc)&(dd>hi)                                                # bin fully observed without onset
    ll=(torch.log(hazards)*event.float()+torch.log1p(-hazards)*survived.float()).sum(-1)
    return -(ll*use.float()).sum()/use.float().sum().clamp_min(1.)

# ----------------------------------------------------------------------------- stores
class SignatureStore(SequenceStore):
    """Appends depth-2 path signatures of the fast channels (time-augmented, carried-forward
    z-scored values) over trailing windows: level-1 increments and level-2 iterated integrals.
    Used only by the signature_boosted_tree arm (the PhysioNet 2019 winner's method)."""
    def __init__(self,index,features,norm,max_hours,windows=(6,24)):
        super().__init__(index,features,norm,max_hours)
        self.fast=[f for f in FAST if f in features];self.fidx=[features.index(f) for f in self.fast];self.windows=windows
        d=len(self.fast)+1;names=['t']+self.fast
        self.sig_names=[f'Sig{w}h_{a}' for w in windows for a in names]+[f'Sig{w}h_{a}_{b}' for w in windows for a in names for b in names]
        self.base_features=list(features);self.features=list(features)+self.sig_names
    def base_item(self,i):
        self.features,ext=self.base_features,self.features
        try:return super().__getitem__(i)
        finally:self.features=ext
    @staticmethod
    def signatures(path):
        """path: (n,d) points. Returns level-1 (d,) and level-2 (d*d,) signature terms."""
        if len(path)<2:return np.zeros(path.shape[1]),np.zeros(path.shape[1]**2)
        # Exact level-2 iterated integrals of the piecewise-linear path (Chen's identity on linear segments).
        inc=np.diff(path,axis=0);cum=path[:-1]-path[0]
        return path[-1]-path[0],(cum.T@inc+.5*inc.T@inc).ravel()
    def __getitem__(self,i):
        item=self.base_item(i);x=item['x'];n=int(item['mask'].sum());out=np.zeros((x.shape[0],len(self.sig_names)),np.float32)
        vals=x[:n][:,self.fidx];t=(item['hours'][:n]/24.)[:,None];P=np.concatenate([t,vals],1);col=0
        for w in self.windows:
            d=P.shape[1];l1=np.zeros((n,d));l2=np.zeros((n,d*d))
            for k in range(n):
                a,b=self.signatures(P[max(0,k-w):k+1]);l1[k]=a;l2[k]=b
            out[:n,col:col+d]=l1;col+=d;out[:n,col:col+d*d]=l2;col+=d*d
        item['x']=np.concatenate([x,out],1);return item

def onset_tensor(store,device):
    return torch.tensor(store.index.OnsetHour.to_numpy(dtype=np.float32),device=device)

# ----------------------------------------------------------------------------- pretraining
def ssl_targets(x,mask,pt):
    """Label-free targets from the batch itself (future values of the same stay)."""
    b,t,_=x.shape;enc=pt.encoder
    fresh=(x[:,:,enc.observed]>.5)&(x[:,:,enc.ages]*AGE_SCALE<1)&(mask.unsqueeze(-1)>.5)
    nxt_val=torch.zeros_like(x[:,:,enc.values]);nxt_ok=torch.zeros_like(fresh)
    nxt_val[:,:-1]=x[:,1:,enc.values];nxt_ok[:,:-1]=fresh[:,1:]
    # measured within 6 h: any fresh observation in (t, t+6]
    cs=torch.cumsum(fresh.float(),1);pad=torch.cat([torch.zeros_like(cs[:,:1]),cs],1)
    idx=torch.arange(t,device=x.device);hi=torch.clamp(idx+6,max=t-1)
    within=(pad[:,hi+1]-pad[:,idx+1])>0;within_ok=(mask.unsqueeze(-1)>.5)&((idx+1)<t).view(1,t,1)
    out={'forecast':(nxt_val,nxt_ok),'measured':(within.float(),within_ok)}
    if pt.sofa:
        s=x[:,:,pt.sofa];so=x[:,:,pt.sofa_obs]>.5;organ=[];ok=[];worse=[];wok=[]
        for h in (6,12,24):
            fut=torch.zeros_like(s);fok=torch.zeros_like(so)
            if t>h:fut[:,:-h]=s[:,h:];fok[:,:-h]=so[:,h:]&(mask[:,h:].unsqueeze(-1)>.5)
            organ.append(fut);ok.append(fok)
            # any component rises within h hours (known now and later)
            m=torch.zeros_like(s);mk=torch.zeros_like(so)
            for j in range(1,h+1):
                if t>j:
                    cand=torch.full_like(s,-1e9);cand[:,:-j]=torch.where(so[:,j:]&(mask[:,j:].unsqueeze(-1)>.5),s[:,j:],torch.full_like(s[:,j:],-1e9))
                    m=torch.maximum(m,cand) if j>1 else cand;mk[:,:-j]|=so[:,j:]&(mask[:,j:].unsqueeze(-1)>.5)
            known=so&mk;rise=((m>s+1e-6)&known).any(-1);worse.append(rise.float());wok.append(known.any(-1))
        out['organ']=(torch.stack(organ,-1),torch.stack(ok,-1));out['worsen']=(torch.stack(worse,-1),torch.stack(wok,-1))
    return out

def ssl_loss(pred,targets):
    total=0.;parts={}
    for k,(tgt,ok) in targets.items():
        okf=ok.float()
        if okf.sum()==0:continue
        if k in ('measured','worsen'):l=nn.functional.binary_cross_entropy_with_logits(pred[k],tgt,reduction='none')
        else:l=nn.functional.smooth_l1_loss(pred[k],tgt,reduction='none')
        v=(l*okf).sum()/okf.sum();parts[k]=float(v.detach());total=total+v
    return total,parts

def pretrain(stores,features,cfg,seed,path,device,label='site'):
    """Self-supervised pretraining of the encoder on unlabelled stays. `stores`: list of SequenceStores
    (already normalised with the TARGET's normaliser). Checkpoint by validation SSL loss on a
    held-out tenth of the corpus stays. Returns the encoder state dict."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file():return torch.load(path,map_location='cpu',weights_only=False)['encoder']
    seed_all(seed);pt=Pretrainer(features,depth=cfg.get('cnn_depth',2),dropout=cfg['dropout']).to(device)
    opt=torch.optim.AdamW(pt.parameters(),lr=cfg['learning_rate'],weight_decay=1e-4)
    index=pd.concat([s.index for s in stores],ignore_index=True);norm=stores[0].norm
    val_mask=(np.arange(len(index))%10==0)
    train=SequenceStore(index[~val_mask],features,norm,cfg['max_hours']);val=SequenceStore(index[val_mask],features,norm,cfg['max_hours'])
    best=math.inf;history=[]
    for ep in range(cfg['ssl_epochs']):
        for split,store in [('train',train),('val',val)]:
            pt.train(split=='train');tot=0.;n=0;agg={}
            for b in loader(store,cfg['batch'],split=='train',seed+ep):
                q=batch_to(b,device);x=q['x']
                with torch.set_grad_enabled(split=='train'):
                    tg=ssl_targets(x,q['mask'],pt);loss,parts=ssl_loss(pt(x),tg)
                    if split=='train' and torch.is_tensor(loss):
                        opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(pt.parameters(),1.);opt.step()
                tot+=float(loss) if torch.is_tensor(loss) else 0.;n+=1
                for k,v in parts.items():agg[k]=agg.get(k,0.)+v
            avg=tot/max(n,1);history.append({'epoch':ep+1,'split':split,'loss':avg,**{k:v/max(n,1) for k,v in agg.items()}})
            if split=='val' and avg<best:
                best=avg;atomic_torch(path,{'encoder':{k:v.detach().cpu().clone() for k,v in pt.encoder.state_dict().items()},
                    'seed':seed,'population':label,'validation_ssl_loss':best,'stays':int(len(index)),'labels_used':'none'})
        print(f'SSL {label} epoch {ep+1} train {history[-2]["loss"]:.4f} val {history[-1]["loss"]:.4f}',flush=True)
    atomic_json(path.with_suffix('.history.json'),history)
    return torch.load(path,map_location='cpu',weights_only=False)['encoder']

# ----------------------------------------------------------------------------- neural training
def build_model(arm,features,bank,cfg,encoder_state=None):
    if arm in V9_ARMS:model=ExperimentModel(features,arm,bank.names,small=cfg['small_model'],dropout=cfg['dropout'])
    else:model=make_model(arm,features,cfg)
    if encoder_state is not None:model.encoder.load_state_dict(encoder_state)
    return model

def train_neural(arm,model,train,val,bank,cfg,seed,path,device,loss):
    path=Path(path);path.mkdir(parents=True,exist_ok=True);best_path=path/'best.pt';last_path=path/'last.pt'
    model.to(device);opt=torch.optim.AdamW(model.parameters(),lr=cfg['learning_rate'],weight_decay=cfg.get('weight_decay',1e-4))
    best=-1.;wait=0;start=0;history=[];onsets=onset_tensor(train,device)
    if last_path.is_file():
        st=torch.load(last_path,map_location=device,weights_only=False);model.load_state_dict(st['model']);opt.load_state_dict(st['optimizer'])
        start=st['epoch']+1;best=st['best'];wait=st['wait'];history=st['history']
    ld=loader(train,cfg['batch'],True,seed);ld.batch_sampler.epoch=start
    p_in=float(cfg.get('input_dropout',0.) or 0.);groups,n_groups=feature_groups(train.features) if p_in>0 else (None,0)
    heads=getattr(model,'heads',None) is not None
    for ep in range(start,cfg['epochs']):
        if wait>=cfg['patience']:break
        seed_all(seed+ep);model.train();bank.eval();tot=0.;nb=0
        for b in ld:
            b=batch_to(b,device)
            with torch.no_grad():z=bank(b['x']) if arm in OSTA_FAMILY and arm!='osta' else None
            xin=input_dropout(b['x'],groups,n_groups,p_in) if p_in>0 else b['x']
            logits=model(xin,b['mask'],b['hours'],z);on=onsets[b['idx']]
            if arm.startswith('hazard_'):l=hazard_nll(model.last_hazards,b,on)
            else:
                target,w=targets_and_weights(b,on,loss,cfg['horizon'],cfg.get('tls_tau',12.))
                if w.sum()==0:continue
                l=(nn.functional.binary_cross_entropy_with_logits(logits,target,reduction='none')*w).sum()/w.sum()
            if heads:l=uncertainty_weighted([l,heads_loss(model,b)],model.log_var)   # heads read the UNDROPPED targets from b['x']
            if not torch.isfinite(l):raise FloatingPointError(f'{arm}: nonfinite loss')
            opt.zero_grad();l.backward();nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step();tot+=float(l.detach());nb+=1
        pred,_=predict(model,bank,val,cfg['batch'],device)
        score=average_precision_score(pred.y,pred.logit) if pred.y.nunique()==2 else float('nan')
        if not np.isfinite(score):raise ValueError('Validation target has fewer than two classes')
        if score>best:best=score;wait=0;atomic_torch(best_path,{'state':model.state_dict(),'epoch':ep,'val_AUPRC':best})
        else:wait+=1
        history.append({'epoch':ep+1,'loss':tot/max(nb,1),'val_hourly_AUPRC':score,**({'task_weights':model.task_weights()} if heads else {})})
        atomic_torch(last_path,{'model':model.state_dict(),'optimizer':opt.state_dict(),'epoch':ep,'best':best,'wait':wait,'history':history})
        print(arm,loss,'epoch',ep+1,'loss',round(tot/max(nb,1),5),'validation AUPRC',round(score,5),flush=True)
    model.load_state_dict(torch.load(best_path,map_location=device,weights_only=False)['state'])
    atomic_json(path/'training_history.json',history);return model.eval()

# ----------------------------------------------------------------------------- stage 1b (protocol 10b)
def component_rise_targets(x,mask,sofa,sofa_obs,horizons=HEAD_HORIZONS):
    """Per-organ targets for the organ heads: for each SOFA component k and horizon h, 1 if the component
    is observed later within h hours at a HIGHER value than now (both observed), plus an any_organ target.
    Returns (target (B,T,K+1,H), ok (B,T,K+1,H)); ok marks hours where the target is defined. Label-free:
    built from the batch's own future values, as ssl_targets does, but kept per component."""
    s=x[:,:,sofa];so=x[:,:,sofa_obs]>.5;b,t,k=s.shape;tg=[];oks=[]
    for h in horizons:
        m=torch.full_like(s,-1e9);mk=torch.zeros_like(so)
        for j in range(1,h+1):
            if t>j:
                later=so[:,j:]&(mask[:,j:].unsqueeze(-1)>.5)
                cand=torch.full_like(s,-1e9);cand[:,:-j]=torch.where(later,s[:,j:],torch.full_like(s[:,j:],-1e9))
                m=torch.maximum(m,cand);mk[:,:-j]|=later
        known=so&mk;rise=(m>s+1e-6)&known
        anyk=known.any(-1,keepdim=True);anyr=(rise&known).any(-1,keepdim=True)
        tg.append(torch.cat([rise.float(),anyr.float()],-1));oks.append(torch.cat([known,anyk],-1))
    return torch.stack(tg,-1),torch.stack(oks,-1)

def heads_loss(model,b):
    """Mean BCE of the organ heads over defined, in-stay hours (the heads' own task loss)."""
    tgt,ok=component_rise_targets(b['x'],b['mask'],model.sofa,model.sofa_obs)
    okf=(ok&(b['mask'].unsqueeze(-1).unsqueeze(-1)>.5)).float()
    if okf.sum()==0:return None
    l=nn.functional.binary_cross_entropy_with_logits(model.last_head_logits,tgt,reduction='none')
    return (l*okf).sum()/okf.sum()

def uncertainty_weighted(losses,log_var):
    """Kendall, Gal & Cipolla (2018) multi-task weighting: sum_i exp(-s_i) L_i + s_i, s_i learned."""
    total=0.
    for i,l in enumerate(losses):
        if l is None:continue
        total=total+torch.exp(-log_var[i])*l+log_var[i]
    return total

def feature_groups(features):
    """Group id per feature column: a measured channel's value, _observed and _age columns share one id,
    so input dropout hides the three together (protocol 10b, item C)."""
    base={};ids=[]
    for f in features:
        bn=f[:-9] if f.endswith('_observed') else f[:-4] if f.endswith('_age') else f
        ids.append(base.setdefault(bn,len(base)))
    return torch.tensor(ids,dtype=torch.long),len(base)

def input_dropout(x,groups,n_groups,p,generator=None):
    """Hide whole predictor groups (value+flag+age together) with probability p per stay-hour. Training only.
    Hidden columns become 0 = the normalised mean (flags 0 = not measured)."""
    if p<=0:return x
    keep=(torch.rand(x.shape[0],x.shape[1],n_groups,device=x.device,generator=generator)>=p).float()
    return x*keep[:,:,groups.to(x.device)]

def fresh_hours(store):
    """Hours in which at least one measured channel was newly charted (age < 1 h), per stay-hour.
    Policy item F (protocol 10b): alarms may be restricted to these hours."""
    chans=measured_channels(store.features)
    oi=[store.features.index(f+'_observed') for f in chans];ai=[store.features.index(f+'_age') for f in chans];rows=[]
    for i in range(len(store)):
        b=store[i];n=int(b['mask'].sum());x=b['x'][:n]
        fresh=((x[:,oi]>.5)&(x[:,ai]*AGE_SCALE<1)).any(1) if oi else np.ones(n,bool)
        rows.append(pd.DataFrame({'Patient_ID':store.index.Patient_ID.iloc[i],'Hour':b['hours'][:n],'fresh':fresh}))
    return pd.concat(rows,ignore_index=True)

def with_fresh(d,fresh):
    """Attach the fresh flag to a prediction frame (missing hours count as not fresh)."""
    if fresh is None or 'fresh' in d:return d
    dd=d.assign(Patient_ID=d.Patient_ID.astype(str)).merge(fresh.assign(Patient_ID=fresh.Patient_ID.astype(str)),on=['Patient_ID','Hour'],how='left')
    dd['fresh']=dd.fresh.fillna(False).astype(bool);dd['Patient_ID']=d.Patient_ID.to_numpy();return dd

def alarm_fraction(d,threshold):
    """Share of scored hours at or above the threshold: the alarm rate the quantile operating point carries over."""
    return float(np.mean(d.risk.to_numpy()>=threshold))

def quantile_threshold(d,fraction,min_hours=10000):
    """Quantile operating point (protocol 10b, item E): the threshold that flags the same FRACTION of this
    population's own hours. Label-free. Below min_hours the caller must fall back to the absolute threshold."""
    r=d.risk.to_numpy(dtype=float)
    if len(r)<min_hours:return None
    if fraction<=0:return 1.0000001
    return float(np.quantile(r,1-min(fraction,1.)))

def operating_threshold(d,chosen,cfg,key='threshold',frac_key='alarm_fraction'):
    """Absolute (V11) or quantile (10b) operating point for a scored population; records which was used."""
    if cfg.get('operating_point','absolute')=='quantile' and frac_key in chosen:
        q=quantile_threshold(d,chosen[frac_key],cfg.get('quantile_min_hours',10000))
        if q is not None:return q,'quantile'
    return chosen[key],'absolute'

def alarm_records_v11(d,threshold,cooldown=6,horizon=6,persistence=1,fresh_only=False):
    """v9 alarm_records with two policy options: persistence (risk at or above the threshold for this many
    consecutive scored hours before an alarm) and fresh_only (alarms only in hours with new charting).
    False alarms are still counted against every scored hour (at_risk_hours)."""
    rows=[];use_fresh=fresh_only and 'fresh' in d
    for pid,g in d.groupby('Patient_ID',sort=False,observed=True):
        g=g.sort_values('Hour');onset=g.OnsetHour.iloc[0];last=-np.inf;false=0;leads=[];total=0;run=0;prev_h=None
        fr=g.fresh.to_numpy() if use_fresh else np.ones(len(g),bool)
        for h,p,f in zip(g.Hour,g.risk,fr):
            run=(run+1 if (prev_h is not None and h-prev_h<=1.001 and p>=threshold) else (1 if p>=threshold else 0));prev_h=h
            if p>=threshold and run>=persistence and f and h-last>=cooldown:
                last=h;total+=1
                if pd.notna(onset) and 0<onset-h<=horizon:leads.append(onset-h)
                else:false+=1
        evaluable=bool((g.y==1).any())
        rows.append({'Patient_ID':pid,'Group_ID':g.Group_ID.iloc[0],'event_evaluable':evaluable,'detected':bool(leads),
          'warning_hours':max(leads) if leads else np.nan,'false_alarms':false,'alarms':total,'at_risk_hours':len(g)})
    return pd.DataFrame(rows)

def evaluate_v11(d,threshold,cfg,persistence=1,fresh_only=False):
    """v9 evaluate (hourly metrics unchanged) with the event metrics recomputed under the alarm policy."""
    out,a,points=evaluate(d,threshold,cfg)
    if persistence==1 and not fresh_only:return out,a,points
    a=alarm_records_v11(d,threshold,cfg['alarm_cooldown'],cfg['horizon'],persistence,fresh_only);ev=a[a.event_evaluable]
    out.update({'alarm_PPV':float((a.alarms-a.false_alarms).sum()/a.alarms.sum()) if a.alarms.sum() else np.nan,
      'event_sensitivity':float(ev.detected.mean()) if len(ev) else np.nan,'missed_events':int((~ev.detected).sum()),
      'false_alarms_per_patient_day':float(a.false_alarms.sum()/a.at_risk_hours.sum()*24),'detected_event_denominator':int(ev.detected.sum()),
      'warning_hours_q25':float(ev.warning_hours.quantile(.25)) if ev.warning_hours.notna().any() else np.nan,
      'warning_hours_q75':float(ev.warning_hours.quantile(.75)) if ev.warning_hours.notna().any() else np.nan,
      'median_warning_hours_detected':float(ev.warning_hours.median()) if ev.warning_hours.notna().any() else np.nan})
    return out,a,points

def head_validation_auroc(model,store,cfg,device):
    """Per-organ head AUROC on a store's in-stay hours for the 6 h target (protocol 10b, rule 2)."""
    from sklearn.metrics import roc_auc_score
    if getattr(model,'heads',None) is None:return {}
    model.eval();bank_free=True;logit=[];tgt=[];okk=[]
    with torch.no_grad():
        for b in loader(store,cfg['batch']):
            b=batch_to(b,device);model(b['x'],b['mask'],b['hours'],None)
            t,ok=component_rise_targets(b['x'],b['mask'],model.sofa,model.sofa_obs)
            m=(b['mask'].unsqueeze(-1).unsqueeze(-1)>.5)&ok
            logit.append(model.last_head_logits.cpu().numpy());tgt.append(t.cpu().numpy());okk.append(m.cpu().numpy())
    L=np.concatenate(logit);T=np.concatenate(tgt);K=np.concatenate(okk);out={}
    for j,name in enumerate(model.head_names):
        sel=K[:,:,j,0];y=T[:,:,j,0][sel];p=L[:,:,j,0][sel]
        out['head_auroc_6h_'+name]=float(roc_auc_score(y,p)) if len(np.unique(y))==2 else np.nan
    return out

STAGE1B_GRID=[(op,pers,fresh) for op in ['absolute','quantile'] for pers in [1,2] for fresh in [False,True]]

# ----------------------------------------------------------------------------- tabular
def fit_tabular_v11(arm,train,val,cfg,seed,path):
    p=Path(path)/'estimator.pkl'
    if p.is_file():
        with p.open('rb') as f:return pickle.load(f)
    x,y=tabular_arrays(train,cfg['tabular_max_bytes'])
    if arm=='logistic':model=LogisticRegression(C=1.,solver='lbfgs',max_iter=1000,random_state=seed).fit(x,y)
    else:
        # Patient-grouped early stopping on the validation split (sklearn's internal split mixes hours of one patient).
        xv,yv=tabular_arrays(val,cfg['tabular_max_bytes']);step=cfg.get('tree_step',50);best=-1.;wait=0;best_iter=step;hist=[]
        model=HistGradientBoostingClassifier(max_iter=step,warm_start=True,early_stopping=False,learning_rate=.05,max_leaf_nodes=31,l2_regularization=1.,random_state=seed)
        for it in range(step,cfg.get('tree_max_iterations',1000)+1,step):
            model.set_params(max_iter=it);model.fit(x,y);ap=float(average_precision_score(yv,model.predict_proba(xv)[:,1]));hist.append({'iterations':it,'val_AUPRC':ap})
            if ap>best:best=ap;wait=0;best_iter=it
            else:wait+=1
            if wait>=cfg['patience']:break
        model=HistGradientBoostingClassifier(max_iter=best_iter,early_stopping=False,learning_rate=.05,max_leaf_nodes=31,l2_regularization=1.,random_state=seed).fit(x,y)
        atomic_json(Path(path)/'training_history.json',hist)
    tmp=p.with_suffix('.partial.pkl')
    with tmp.open('wb') as f:pickle.dump(model,f)
    os.replace(tmp,p);return model

# ----------------------------------------------------------------------------- extra evaluation
def antibiotic_lead(d,threshold,cfg):
    """Lead time of the first TIMELY alarm (within the 6 h window before onset) relative to the first
    antibiotic order around onset. Evaluation metadata only (the order time is never a predictor)."""
    if 'FirstAntibioticAroundOnset' not in d:return {}
    rows=[]
    for pid,g in d.groupby('Patient_ID',sort=False,observed=True):
        onset=g.OnsetHour.iloc[0];abx=g.FirstAntibioticAroundOnset.iloc[0]
        if not (pd.notna(onset) and pd.notna(abx)):continue
        g=g.sort_values('Hour');timely=g[(g.risk>=threshold)&(g.Hour<onset)&(g.Hour>=onset-cfg['horizon'])]
        rows.append({'detected':len(timely)>0,'lead_vs_antibiotic':(abx-timely.Hour.iloc[0]) if len(timely) else np.nan,'alarm_before_antibiotic':bool(len(timely) and timely.Hour.iloc[0]<abx)})
    if not rows:return {'antibiotic_lead_n':0}
    r=pd.DataFrame(rows);det=r[r.detected]
    return {'antibiotic_lead_n':int(len(r)),'antibiotic_lead_detected':int(len(det)),
            'median_lead_vs_first_antibiotic_hours':float(det.lead_vs_antibiotic.median()) if len(det) else np.nan,
            'fraction_alarm_before_first_antibiotic':float(r.alarm_before_antibiotic.mean())}

def ood_scores(store,z_cut=3.5):
    """Per-hour out-of-distribution score: fraction of OBSERVED measured channels with |z| > z_cut
    (model-agnostic; z from the training normaliser)."""
    ch=measured_channels(store.features);vi=[store.features.index(f) for f in ch];oi=[store.features.index(f+'_observed') for f in ch]
    rows=[]
    for i in range(len(store)):
        b=store[i];n=int(b['mask'].sum());x=b['x'][:n];obs=x[:,oi]>.5;ext=(np.abs(x[:,vi])>z_cut)&obs
        frac=np.where(obs.sum(1)>0,ext.sum(1)/np.maximum(obs.sum(1),1),0.)
        rows.append(pd.DataFrame({'Patient_ID':store.index.Patient_ID.iloc[i],'Hour':b['hours'][:n],'ood':frac.astype(np.float32)}))
    return pd.concat(rows,ignore_index=True)

def conformal_policy(cal,test,cal_ood,test_ood,cfg,alpha=.02):
    """Secondary alarm policy. (1) Abstain on out-of-distribution hours: ood above the (1-alpha)
    split-conformal quantile of calibration hours. (2) Alarm threshold = split-conformal quantile of
    calibration NON-SEPTIC eligible hours' risk at level 1-eps, eps = false-alarm budget per hour
    (budget/24), finite-sample corrected: a distribution-free bound on the hourly false-positive rate."""
    cal=cal.assign(Patient_ID=cal.Patient_ID.astype(str));test=test.assign(Patient_ID=test.Patient_ID.astype(str))
    c=cal.merge(cal_ood,on=['Patient_ID','Hour'],how='left');t=test.merge(test_ood,on=['Patient_ID','Hour'],how='left')
    s=np.sort(c.ood.fillna(0).to_numpy());n=len(s);k=min(n-1,int(np.ceil((n+1)*(1-alpha)))-1);tau=float(s[k]) if n else 1.
    neg=np.sort(c[c.y.eq(0)].risk.to_numpy());m=len(neg);eps=cfg['false_alarm_budget']/24.
    j=min(m-1,int(np.ceil((m+1)*(1-eps)))-1);thr=float(neg[j]) if m else 1.
    t=t.copy();abstain=t.ood.fillna(0)>tau;t.loc[abstain,'risk']=0.
    return t,{'conformal_threshold':thr,'conformal_ood_tau':tau,'conformal_abstained_fraction':float(abstain.mean())}

def dense_hours(store,required=('HR','MAP','Resp','O2Sat'),lookback=6,min_count=3):
    """Trajectory-rich hours: at least `min_count` fresh observations of EACH required channel in the
    trailing `lookback` hours (past/current information only)."""
    req=[f for f in required if f+'_observed' in store.features and f+'_age' in store.features]
    oi=[store.features.index(f+'_observed') for f in req];ai=[store.features.index(f+'_age') for f in req];rows=[]
    for i in range(len(store)):
        b=store[i];n=int(b['mask'].sum());x=b['x'][:n];fresh=((x[:,oi]>.5)&(x[:,ai]*AGE_SCALE<1)).astype(int)
        cs=np.vstack([np.zeros((1,len(req))),np.cumsum(fresh,0)]);counts=cs[np.arange(1,n+1)]-cs[np.maximum(0,np.arange(1,n+1)-lookback)]
        dense=(counts>=min_count).all(1) if req else np.ones(n,bool)
        rows.append(pd.DataFrame({'Patient_ID':store.index.Patient_ID.iloc[i],'Hour':b['hours'][:n],'dense':dense}))
    return pd.concat(rows,ignore_index=True)

def validation_panel(model_pred_val,cfg):
    """Validation-split utility and AUPRC used ONLY for the prespecified loss/shortlist rules."""
    out={'val_AUPRC':float(average_precision_score(model_pred_val.y,model_pred_val.logit)) if model_pred_val.y.nunique()==2 else np.nan}
    return out

# ----------------------------------------------------------------------------- driver
def run_fold_v11(index,features,target,cfg,root,transfer_index=None,corpus=None):
    """One target database: fit on its development split, evaluate internally; transfer to the other
    database's development patients; prespecified ensemble; conformal policy. cfg['arms'] lists the
    arms; cfg['loss'] is the primary loss; cfg['loss_comparison_arms'] x cfg['comparison_losses'] adds
    loss-comparator runs (saved as arm='<arm>@<loss>')."""
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    mf=partition(index,target,cfg)
    contract={'config':cfg,'features':features,'membership':mf[['Patient_ID','Group_ID','split']].to_dict('list'),
      'shards':{f:sha(f) for f in sorted(mf.file.unique())},'modules':{p.name:sha(p) for p in Path(__file__).parent.glob('v1*_*.py')}}
    key=signature(contract);marker=root/'contract.json'
    if marker.exists() and json.loads(marker.read_text())['sha256']!=key:raise ValueError('Run directory contract changed. Select a new RUN_KEY; old results are retained.')
    atomic_json(marker,{'sha256':key,'contract':contract});mf.to_parquet(root/'manifest.parquet',index=False)
    fit=SequenceStore(mf[mf.split.isin(['train','observer_fit'])],features,max_hours=cfg['max_hours']);norm=fit_normalizer(fit);np.savez(root/'normalization.npz',**norm);del fit
    stores={s:SequenceStore(mf[mf.split.eq(s)],features,norm,cfg['max_hours']) for s in ['train','observer_fit','val','calib','test']}
    atomic_json(root/'feature_schema.json',features)
    # Transfer: the OTHER database's development patients (never its protected holdout), scored with this target's calibration.
    other=None
    if transfer_index is not None:
        o=transfer_index[transfer_index.Dataset.ne(target)&~transfer_index.Group_ID.map(protected_group)]
        if len(o):other=SequenceStore(o.copy(),features,norm,cfg['max_hours'])
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu');results=[]
    cal_ood=ood_scores(stores['calib']);test_ood=ood_scores(stores['test']);dense=dense_hours(stores['test'])
    ssl_stores={}
    if corpus:
        for pop in ['site','pooled']:
            parts=[corpus[target]] if pop=='site' else [corpus[k] for k in sorted(corpus)]
            ssl_stores[pop]=[SequenceStore(ix,features,norm,cfg['max_hours']) for ix in parts if ix is not None and len(ix)]
    grid=[float(q) for q in (cfg.get('input_dropout_grid') or [0.])]
    jobs=[(a,cfg['loss'],q) for a in cfg['arms'] for q in grid]+[(a,l,0.) for a in cfg.get('loss_comparison_arms',[]) for l in cfg.get('comparison_losses',[]) if l!=cfg['loss']]
    stage1b=cfg.get('stage')=='1b'
    fresh_val=fresh_hours(stores['val']) if stage1b or cfg.get('fresh_only') else None
    fresh_test=fresh_hours(stores['test']) if cfg.get('fresh_only') else None
    for seed in cfg['seeds']:
        sd=root/f'seed_{seed}';sd.mkdir(exist_ok=True);seed_all(seed)
        need_bank=any(a in OSTA_FAMILY and a!='osta' for a,_,_ in jobs)
        bank=(train_observers(stores['observer_fit'],features,cfg,seed,sd/'observers.pt',device) if need_bank
              else ObserverBank(features,hidden=cfg['observer_hidden']).to(device).eval().requires_grad_(False))
        encoders={}
        for arm,loss,idrop in jobs:
            name=(arm if loss==cfg['loss'] else f'{arm}@{loss}')+(f'#id{idrop:g}' if idrop>0 else '');path=sd/name;path.mkdir(exist_ok=True);done=path/'completed.json'
            cfgj={**cfg,'input_dropout':idrop}
            if done.is_file():results+=json.loads(done.read_text());print('Reuse',target,name);continue
            seed_all(seed);tab=arm in TABULAR
            if tab:
                mk=lambda s:(SignatureStore(s.index,features,norm,cfg['max_hours']) if arm=='signature_boosted_tree' else s)
                model=fit_tabular_v11('boosted_tree' if arm=='signature_boosted_tree' else arm,mk(stores['train']),mk(stores['val']),cfg,seed,path)
                def pred(store,condition='normal',all_hours=False):return tabular_predict(model,mk(store),all_hours),{}
            else:
                enc=None
                if arm in SSL_ARMS:
                    pop=SSL_ARMS[arm]
                    if pop not in encoders:
                        if not ssl_stores.get(pop):raise ValueError(f'{arm}: no unlabelled corpus for population {pop}')
                        encoders[pop]=pretrain(ssl_stores[pop],features,cfg,seed,sd/f'ssl_encoder_{pop}.pt',device,pop)
                    enc=encoders[pop]
                model=build_model(arm,features,bank,cfg,enc)
                model=train_neural(arm,model,stores['train'],stores['val'],bank,cfgj,seed,path,device,loss)
                def pred(store,condition='normal',all_hours=False):return predict(model,bank,store,cfg['batch'],device,condition,all_hours)
            cal,_=pred(stores['calib']);params=calibrate(cal);cal=apply_calibration(cal,params);chosen,sweep=select_threshold(cal,cfg)
            chosen['alarm_fraction']=alarm_fraction(cal,chosen['threshold'])
            full_cal=pred(stores['calib'],all_hours=True)[0];full_test=pred(stores['test'],all_hours=True)[0]
            utility=utility_block(full_cal,full_test,params,cfg,seed,path)
            apply_calibration(full_test,params).to_parquet(path/'predictions_allhours.parquet',index=False)
            apply_calibration(full_cal,params).to_parquet(path/'predictions_allhours_calib.parquet',index=False)
            vp,_=pred(stores['val']);vcal=apply_calibration(vp,params);vfull=apply_calibration(pred(stores['val'],all_hours=True)[0],params)
            vthr,_=utility_threshold_sweep(apply_calibration(full_cal,params),np.unique(np.round(np.quantile(cal.risk,np.linspace(.5,.999,30)),6)))
            vutil=float(normalized_from(patient_utilities(vfull,vthr)))
            chosen['utility_alarm_fraction']=alarm_fraction(apply_calibration(full_cal,params),utility['utility_threshold'])
            heads_info={'task_weights':model.task_weights(),'head_names':model.head_names} if getattr(model,'heads',None) is not None else {}
            atomic_json(path/'calibration_and_threshold.json',{'platt':params,'chosen':chosen,'validation_utility':vutil,'validation_AUPRC':validation_panel(vp,cfg)['val_AUPRC'],'input_dropout':idrop,**heads_info})
            pd.DataFrame(sweep).to_csv(path/'threshold_sweep.csv',index=False)
            if stage1b:
                # ---- Protocol 10b: validation-only grid; the test split is scored, written and SEALED (not returned). ----
                vgrid=with_fresh(vcal,fresh_val);hauc=head_validation_auroc(model,stores['val'],cfg,device) if not tab else {}
                base_row={'target':target,'seed':seed,'arm':name,'base_arm':arm,'loss':loss if not tab else 'n/a','scope':'stage1b_validation_split',
                  'feature_count':len(features),'main_training_stays':len(stores['train']),'input_dropout':idrop,'validation_utility':vutil,
                  'validation_AUPRC':validation_panel(vp,cfg)['val_AUPRC'],'alarm_fraction':chosen['alarm_fraction'],'absolute_threshold':chosen['threshold'],
                  'task_weights':json.dumps(heads_info.get('task_weights')) if heads_info else '',**hauc}
                records=[]
                for op,pers,fresh in STAGE1B_GRID:
                    thr,used=operating_threshold(vgrid,chosen,{**cfg,'operating_point':op})
                    mv,_,_=evaluate_v11(vgrid,thr,cfg,pers,fresh)
                    records.append({**base_row,'condition':'validation_grid','operating_point':op,'operating_point_used':used,'persistence':pers,'fresh_only':fresh,'threshold_used':thr,**mv})
                d,_=pred(stores['test']);d=apply_calibration(d,params);m,alarms,points=evaluate(d,chosen['threshold'],cfg)
                m.update(clustered_ci(d,cfg['bootstrap'],seed));m.update(utility);m.update(antibiotic_lead(d,chosen['threshold'],cfg))
                sealed={'target':target,'seed':seed,'arm':name,'base_arm':arm,'loss':loss,'condition':'normal','scope':'stage1b_test_split_SEALED_until_stage2','input_dropout':idrop,**m}
                d.to_parquet(path/'predictions_normal.parquet',index=False);atomic_json(path/'test_rows_sealed.json',[sealed])
                results+=records;atomic_json(done,records);del model;gc.collect()
                if torch.cuda.is_available():torch.cuda.empty_cache()
                print('Completed (stage 1b, validation only)',target,name,flush=True);continue
            records=[]
            conditions=['normal']+(cfg['stress_conditions'] if (arm in OSTA_FAMILY and arm!='osta') else [])
            for condition in conditions:
                d,gates=pred(stores['test'],condition);d=apply_calibration(d,params);d=with_fresh(d,fresh_test)
                thr_t,op_used=operating_threshold(d,chosen,cfg)
                m,alarms,points=evaluate_v11(d,thr_t,cfg,cfg.get('persistence',1),bool(cfg.get('fresh_only',False)));m.update({'operating_point_used':op_used,'persistence':cfg.get('persistence',1),'fresh_only':bool(cfg.get('fresh_only',False))})
                if condition=='normal':
                    m.update(clustered_ci(d,cfg['bootstrap'],seed));m.update(hospital_ci(d,cfg['bootstrap'],seed));m.update(utility)
                    m.update(antibiotic_lead(d,thr_t,cfg))
                    m.update({'validation_utility':vutil,'validation_AUPRC':validation_panel(vp,cfg)['val_AUPRC'],'input_dropout':idrop,**heads_info})
                row={'target':target,'seed':seed,'arm':name,'base_arm':arm,'loss':loss if not tab else 'n/a','condition':condition,'scope':mf.evaluation_scope.iloc[0],
                  'feature_count':len(features),'main_training_stays':len(stores['train']),**m}
                records.append(row);d.to_parquet(path/f'predictions_{condition}.parquet',index=False)
                alarms.to_parquet(path/f'alarms_{condition}.parquet',index=False);points.to_csv(path/f'calibration_{condition}.csv',index=False)
                if condition=='normal':
                    # Conformal secondary policy and trajectory-rich subset on the same predictions.
                    tc,cinfo=conformal_policy(cal,d,cal_ood,test_ood,cfg,cfg.get('conformal_alpha',.02))
                    mc,_,_=evaluate(tc,cinfo['conformal_threshold'],cfg);mc.update(cinfo);mc.update(antibiotic_lead(tc,cinfo['conformal_threshold'],cfg))
                    records.append({**{k:v for k,v in row.items() if k not in m},'condition':'conformal',**mc})
                    dd=d.assign(Patient_ID=d.Patient_ID.astype(str)).merge(dense,on=['Patient_ID','Hour'],how='left');dd=dd[dd.dense.fillna(False).astype(bool)]
                    if dd.y.nunique()==2:
                        md,_,_=evaluate(dd,chosen['threshold'],cfg);records.append({**{k:v for k,v in row.items() if k not in m},'condition':'trajectory_rich',**md})
            if other is not None:
                dt,_=pred(other);dt=apply_calibration(dt,params);dt=with_fresh(dt,fresh_hours(other) if cfg.get('fresh_only') else None)
                thr_o,op_o=operating_threshold(dt,chosen,cfg);mt,at,pt_=evaluate_v11(dt,thr_o,cfg,cfg.get('persistence',1),bool(cfg.get('fresh_only',False)));mt.update({'operating_point_used':op_o})
                mt.update(clustered_ci(dt,cfg['bootstrap'],seed));mt.update(hospital_ci(dt,cfg['bootstrap'],seed))
                mt.update(utility_block(full_cal,pred(other,all_hours=True)[0],params,cfg,seed,_mk(path/'transfer')))
                mt.update(antibiotic_lead(dt,thr_o,cfg))
                ot=other.index.Dataset.iloc[0]
                records.append({'target':f'{ot}_from_{target}','seed':seed,'arm':name,'base_arm':arm,'loss':loss if not tab else 'n/a','condition':'normal',
                    'scope':'development_transfer_other_database_dev_patients','feature_count':len(features),'main_training_stays':len(stores['train']),**mt})
                dt.to_parquet(path/'transfer_predictions.parquet',index=False)
            results+=records;atomic_json(done,records);del model;gc.collect()
            if torch.cuda.is_available():torch.cuda.empty_cache()
            print('Completed',target,name,flush=True)
        # Prespecified mean ensemble of calibrated risks (no learned weights).
        members=[a for a in ENSEMBLE_MEMBERS if (sd/a/'predictions_normal.parquet').is_file()]
        if len(members)>=2 and not (sd/'ensemble_mean'/'completed.json').is_file():
            path=sd/'ensemble_mean';path.mkdir(exist_ok=True)
            def mean_of(fname):
                frames=[pd.read_parquet(sd/a/fname) for a in members];base=frames[0][[c for c in frames[0].columns if c!='risk']].copy()
                base['risk']=np.mean([f.risk.to_numpy() for f in frames],axis=0).astype(np.float32);return base
            calm=mean_of('predictions_allhours_calib.parquet');calm_e=calm[calm.Eligible.eq(1)];chosen,sweep=select_threshold(calm_e,cfg)
            testm=mean_of('predictions_allhours.parquet');teste=testm[testm.Eligible.eq(1)]
            ident={'intercept':0.,'slope':1.}
            def logitify(f):
                f=f.copy();r=np.clip(f.risk.to_numpy(float),1e-6,1-1e-6);f['logit']=np.log(r/(1-r));return f
            utility=utility_block(logitify(calm),logitify(testm),ident,cfg,seed,path)
            m,alarms,points=evaluate(teste,chosen['threshold'],cfg);m.update(clustered_ci(teste,cfg['bootstrap'],seed));m.update(hospital_ci(teste,cfg['bootstrap'],seed));m.update(utility)
            m.update(antibiotic_lead(teste,chosen['threshold'],cfg))
            row={'target':target,'seed':seed,'arm':'ensemble_mean','base_arm':'ensemble_mean','loss':cfg['loss'],'condition':'normal','scope':mf.evaluation_scope.iloc[0],
                 'feature_count':len(features),'main_training_stays':len(stores['train']),'members':'+'.join(members),**m}
            teste.to_parquet(path/'predictions_normal.parquet',index=False);atomic_json(path/'completed.json',[row]);results.append(row)
        # Paired comparisons against OSTA on identical hours.
        comparisons=[];p=sd/'osta'/'predictions_normal.parquet'
        if p.exists():
            for q_ in sorted(sd.glob('*/predictions_normal.parquet')):
                if q_.parent.name=='osta':continue
                comparisons.append({'comparison':q_.parent.name+' minus osta',**paired_difference(pd.read_parquet(q_),pd.read_parquet(p),cfg['bootstrap'],seed)})
        pd.DataFrame(comparisons).to_csv(sd/'paired_comparisons.csv',index=False)
    out=pd.DataFrame(results);out.to_csv(root/'results.csv',index=False);return out

def _mk(p):
    p=Path(p);p.mkdir(parents=True,exist_ok=True);return p
