"""Stage-2 training (protocol section 11 and 10c.2 items 2, 3, 7, 9, 14, 15, 17): stores, transforms, losses and the driver.

Everything here sits on top of the stage-1 code (v9_train, v10_train, v11_train, v11_models) and the stage-2 modules
(v12_manifest, v12_labels, v12_features, v12_models, v12_evaluate). Nothing is retrained in a scoring pass.

Stores
  Stage2Store      SequenceStore with: one normaliser per database (pooled training); an alternative per-stay target
                   (the suspicion-anchored event, 3 h horizon); per-stay soft label values and weights (label-stratified
                   training); practice-path transforms at evaluation (zero, per-population z-score, quantile mapping to
                   the training distribution); concept-grouped practice columns; weak targets for pretraining
                   (arrival sepsis, antibiotic start within 6 h).
  BaselineStore    the baseline-relative arm (item 7): the patient's own expanding baseline summaries computed on the
                   fly from the shard (relative, absolute or both), no masks or counts, ICU time kept.
Training
  train_stage2     the v11 training loop (AdamW, early stopping on validation AUPRC, per-epoch last.pt, resume) with a
                   weighted cross-entropy on soft per-hour targets; identical to train_neural for the primary target.
  pretrain_weak    weakly supervised multi-task pretraining of a flat OSTA core: arrival sepsis (hours <= 6), the six
                   SOFA components at +6/+12/+24 h, treatment events in the next 6 h (vasopressor start, invasive airway,
                   antibiotic start). Label-free with respect to the warning target. Returns the core state.
Driver
  run_stage2       arms in the section-11 order with seed tiering, per-arm completion markers, the scoring passes of
                   v12_evaluate on saved predictions, transfer rows, the eICU leave-hospital-out split for the pooled arm
                   and the MIMIC temporal validation. Test rows are returned only when the protocol has been frozen
                   (cfg['frozen']); otherwise they are written to disk and sealed, exactly as stage 1b did.
"""
from pathlib import Path
import json,gc,math,os,hashlib,time
import numpy as np
import pandas as pd
import torch
from torch import nn
from sklearn.metrics import average_precision_score,roc_auc_score
from v9_train import (AGE_SCALE,SequenceStore,fit_normalizer,loader,batch_to,seed_all,predict,calibrate,apply_calibration,
    select_threshold,evaluate,clustered_ci,atomic_json,atomic_torch)
from v9_models import organ_mapping
from v10_train import tabular_predict,utility_block,hospital_ci
from v10_protocol import partition,protected_group
from v11_models import make_model,FlatOSTA,measured_channels,HEAD_SOFA
from v11_train import (fit_tabular_v11,build_model,pretrain,evaluate_v11,alarm_fraction,operating_threshold,quantile_threshold,
    antibiotic_lead,ood_scores,validation_panel,input_dropout,feature_groups)
from v12_manifest import manifest,path_indices,concept_grouped_practice,base_name
from v12_labels import suspicion_label
from v12_features import baseline_relative,baseline_relative_columns,CHANNELS as BASELINE_CHANNELS
from v12_models import make_stage2_model,TwoChannelOSTA,SubsetFlatOSTA
from v12_evaluate import relabel,pre_treatment,pre_treatment_summary,documentation_strata,score,abstention_rows,adopt_abstention,threshold_transport,suspicion_readings
from v9_data import signature,sha

# ----------------------------------------------------------------------------- arms (section 11 order)
ARM_ORDER=['project','two_channel','pooled','suspicion','pretrained','predictor_sets','label_stratified','benchmarks','exploratory']
THREE_SEED_ARMS={'project','two_channel','pooled','suspicion','pretrained'}
TREATMENT_COLUMNS={'vasopressor':'VasopressorRecorded','airway':'Intubated'}

class NoBank:
    """Stands in for the observer bank where predict() expects one (no guidance is used in stage 2)."""
    names=[]
    def eval(self):return self
    def __call__(self,x):return None

# ----------------------------------------------------------------------------- stores
class Stage2Store(SequenceStore):
    """See the module docstring. `norms`: one normaliser or {Dataset: normaliser}. `target`: 'operational' (y and
    Eligible as stored in the shards) or 'suspicion' (rebuilt per hour from index.SuspicionHour with `horizon`).
    `index` may carry StayValue (soft label scale, default 1) and StayWeight (default 1). `practice`: a practice_spec.
    `concept`: list from concept_grouped_practice (appends the grouped columns; the model decides what it reads).
    `weak`: {'abx_starts': {Patient_ID: [hours]}, 'arrival': {Patient_ID: 0/1}} for pretraining targets."""
    def __init__(self,index,features,norms=None,max_hours=120,target='operational',horizon=3.,practice=None,concept=None,weak=None):
        super().__init__(index,features,None,max_hours)
        self.norms=norms if (norms is None or 'mean' in norms) else dict(norms);self.target=target;self.horizon=float(horizon)
        self.practice=practice;self.concept=concept or [];self.weak=weak or {}
        self.base_features=list(features);self.features=list(features)+[c for c,_,_ in self.concept]
        self._cidx=[([features.index(c) for c in cols],how) for _,cols,how in self.concept]
        self.has_value='StayValue' in self.index;self.has_weight='StayWeight' in self.index
    @property
    def norm(self):
        """The normaliser of the first database (for callers that need one)."""
        if self.norms is None:return None
        if 'mean' in self.norms:return self.norms
        return self.norms[self.index.Dataset.iloc[0]]
    @norm.setter
    def norm(self,value):self.norms=value
    def norm_for(self,i):
        if self.norms is None:return None
        if 'mean' in self.norms:return self.norms
        return self.norms[self.index.Dataset.iloc[i]]
    def raw_values(self,d,n):
        """The raw (unnormalised) predictor matrix of the first n hours of frame d, over base_features."""
        return d[self.base_features].iloc[:n].to_numpy(dtype=np.float32)
    def __getitem__(self,i):
        d=self.frame(i);n=min(len(d),self.max_hours);r=self.index.iloc[i]
        raw=self.raw_values(d,n);norm=self.norm_for(i)
        if norm is not None:
            x=(raw-norm['mean'])/norm['std']
            p=self.practice
            if p is not None and p['mode']=='zscore':
                x[:,p['idx']]=(raw[:,p['idx']]-p['mean'])/p['std']
            elif p is not None and p['mode']=='quantile':
                for k,j in enumerate(p['cont']):
                    v=raw[:,j];ok=np.isfinite(v)
                    if ok.any():
                        mapped=np.interp(v[ok],p['q_eval'][:,k],p['q_train'][:,k]);x[ok,j]=(mapped-norm['mean'][j])/norm['std'][j]
            x=np.nan_to_num(x,nan=0.,posinf=0.,neginf=0.);x=np.clip(x,-20,20)
        else:x=np.nan_to_num(raw,nan=0.,posinf=0.,neginf=0.)
        if self.practice is not None and self.practice['mode']=='zero':x[:,self.practice['idx']]=0.
        if self._cidx:
            extra=np.zeros((n,len(self._cidx)),np.float32)
            for k,(cols,how) in enumerate(self._cidx):
                block=raw[:,cols]
                if how=='mean':
                    with np.errstate(all='ignore'):extra[:,k]=np.nan_to_num(np.nanmean(block,1),nan=0.)
                else:
                    m=np.where(np.isfinite(block),block,np.inf).min(1)
                    extra[:,k]=np.where(np.isfinite(m),m/AGE_SCALE,0.)   # ages in days, as the normaliser scales them
            x=np.concatenate([x,extra],1)
        padded=np.zeros((self.max_hours,len(self.features)),np.float32);padded[:n]=x
        hours=np.zeros(self.max_hours,np.float32);hours[:n]=d.Hour.iloc[:n]
        y=np.zeros(self.max_hours,np.float32);eligible=np.zeros(self.max_hours,np.float32)
        if self.target=='suspicion':
            ev=float(r['SuspicionHour']) if 'SuspicionHour' in r.index and pd.notna(r['SuspicionHour']) else np.nan
            yy,ee=suspicion_label(d.Hour.iloc[:n].to_numpy(dtype=float),ev,self.horizon,followup_end=float(d.Hour.iloc[n-1]) if n else None)
            y[:n]=yy;eligible[:n]=ee
        else:
            y[:n]=d.SepsisLabel.iloc[:n];eligible[:n]=d.Eligible.iloc[:n]
        mask=np.zeros(self.max_hours,np.float32);mask[:n]=1
        value=float(r['StayValue']) if self.has_value and pd.notna(r['StayValue']) else 1.
        weight=float(r['StayWeight']) if self.has_weight and pd.notna(r['StayWeight']) else 1.
        item={'x':padded,'y':y,'eligible':eligible,'mask':mask,'hours':hours,'idx':i,
              'target':(y*value).astype(np.float32),'weight':(eligible*weight).astype(np.float32)}
        if self.weak:
            pid=r['Patient_ID'];abx=np.zeros(self.max_hours,np.float32);abx_ok=np.zeros(self.max_hours,np.float32)
            starts=self.weak.get('abx_starts',{}).get(pid)
            if starts is not None:
                h=hours[:n];s=np.asarray(starts,float)
                abx[:n]=np.array([((s>t)&(s<=t+6)).any() for t in h],np.float32);abx_ok[:n]=1
            arr=self.weak.get('arrival',{}).get(pid,np.nan)
            item.update({'abx6':abx,'abx6_ok':abx_ok,'arrival':np.float32(arr if pd.notna(arr) else 0.),'arrival_ok':np.float32(pd.notna(arr))})
        return item

class BaselineStore(Stage2Store):
    """Item 7. `mode`: 'relative' (deviation, z, 6 h slope, 24 h extremes per channel + ICULOS), 'absolute' (the same
    channels' values + ICULOS), 'both'. Computed from the shard frame per stay; no mask, age or count columns."""
    def __init__(self,index,features,norms=None,max_hours=120,mode='relative',channels=None,**kw):
        self.mode=mode;self.channels=[c for c in (channels or BASELINE_CHANNELS) if c in features and c+'_age' in features]
        rel=baseline_relative_columns(self.channels);absolute=list(self.channels);time_col=['ICULOS'] if 'ICULOS' in features else []
        cols={'relative':rel,'absolute':absolute,'both':absolute+rel}[mode]+time_col
        super().__init__(index,cols,norms,max_hours,**kw);self.shard_features=list(features);self.time_col=time_col
    def raw_values(self,d,n):
        f=d.iloc[:n];parts=[]
        if self.mode in ('absolute','both'):parts.append(f[self.channels].to_numpy(dtype=np.float32))
        if self.mode in ('relative','both'):parts.append(baseline_relative(f[['Hour']+self.channels+[c+'_age' for c in self.channels]],channels=self.channels).to_numpy(dtype=np.float32))
        if self.time_col:parts.append(f[self.time_col].to_numpy(dtype=np.float32))
        return np.concatenate(parts,1)

def fit_store_normalizer(store):
    """fit_normalizer for stores whose raw matrix is computed (BaselineStore); identical to v9 for plain stores."""
    if type(store) is SequenceStore or not isinstance(store,BaselineStore):return fit_normalizer(store)
    k=len(store.base_features);total=np.zeros(k);sq=total.copy();count=total.copy()
    for i in range(len(store)):
        d=store.frame(i);x=store.raw_values(d,min(len(d),store.max_hours)).astype(float);valid=np.isfinite(x)
        v=np.where(valid,x,0.);total+=v.sum(0);sq+=(v*v).sum(0);count+=valid.sum(0)
    mean=np.divide(total,count,out=np.zeros_like(total),where=count>0);var=np.divide(sq,count,out=np.ones_like(total),where=count>0)-mean**2
    std=np.sqrt(np.maximum(var,1e-6));std[count==0]=1
    return {'mean':mean.astype(np.float32),'std':std.astype(np.float32),'count':count.astype(int)}

def fit_norms(index,features,max_hours,datasets=None,store_cls=SequenceStore,**kw):
    """One normaliser per database, fitted on that database's training stays (pooled training keeps the databases'
    own scales; the single-database arms see exactly the stage-1 normaliser)."""
    out={}
    for ds in (datasets or sorted(index.Dataset.unique())):
        ix=index[index.Dataset.eq(ds)]
        if len(ix):out[ds]=fit_store_normalizer(store_cls(ix,features,None,max_hours,**kw) if store_cls is not SequenceStore else SequenceStore(ix,features,max_hours=max_hours))
    return out

def fit_quantiles(store,cols,probs):
    """Empirical quantiles of the RAW values of `cols` over the store's observed hours (for quantile mapping)."""
    vals=[[] for _ in cols]
    for i in range(len(store)):
        d=store.frame(i).iloc[:store.max_hours]
        for j,c in enumerate(cols):
            v=d[c].to_numpy(dtype=float);vals[j].append(v[np.isfinite(v)])
    out=np.zeros((len(probs),len(cols)),np.float64)
    for j in range(len(cols)):
        v=np.concatenate(vals[j]) if vals[j] else np.zeros(0)
        out[:,j]=np.quantile(v,probs) if len(v) else 0.
    return out

QUANTILE_PROBS=np.linspace(.005,.995,100)

def practice_spec(mode,features,manifest_df,train_store=None,eval_store=None):
    """Transform of the practice-path columns applied at EVALUATION (protocol item 14):
    'zero'      the practice columns are set to 0 (the training mean in normalised space);
    'zscore'    the practice columns are standardised with the EVALUATION population's own mean and sd (per hospital
                when the caller passes one hospital's store), so between-population rate differences are removed;
    'quantile'  the continuous practice columns are mapped through the evaluation population's empirical CDF and the
                training population's inverse CDF (masks are left as they are), then normalised as in training."""
    idx=path_indices(features,'practice',manifest_df)
    spec={'mode':mode,'idx':idx}
    if mode=='zscore':
        n=fit_normalizer(eval_store);spec['mean']=n['mean'][idx];spec['std']=n['std'][idx]
    if mode=='quantile':
        cont=[i for i in idx if not features[i].endswith('_observed')];spec['cont']=cont
        cc=[features[i] for i in cont];spec['q_train']=fit_quantiles(train_store,cc,QUANTILE_PROBS);spec['q_eval']=fit_quantiles(eval_store,cc,QUANTILE_PROBS)
    return spec

# ----------------------------------------------------------------------------- supervised training
def _soft_bce(logits,target,weight):
    l=nn.functional.binary_cross_entropy_with_logits(logits,target,reduction='none')
    return (l*weight).sum()/weight.sum()

def train_stage2(model,train,val,cfg,seed,path,device,label='stage2'):
    """Resumable training on the store's per-hour `target` and `weight` (plain BCE for the primary target; the soft
    label-stratified variants and the suspicion target come through the store). Early stopping on validation AUPRC of
    the hard label; per-epoch last.pt, best.pt by validation AUPRC, training_history.json."""
    path=Path(path);path.mkdir(parents=True,exist_ok=True);best_path=path/'best.pt';last_path=path/'last.pt'
    model.to(device);opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=cfg['learning_rate'],weight_decay=cfg.get('weight_decay',1e-4))
    best=-1.;wait=0;start=0;history=[]
    if last_path.is_file():
        st=torch.load(last_path,map_location=device,weights_only=False);model.load_state_dict(st['model']);opt.load_state_dict(st['optimizer'])
        start=st['epoch']+1;best=st['best'];wait=st['wait'];history=st['history']
    ld=loader(train,cfg['batch'],True,seed);ld.batch_sampler.epoch=start
    p_in=float(cfg.get('input_dropout',0.) or 0.);groups,n_groups=feature_groups(train.features) if p_in>0 else (None,0)
    bank=NoBank()
    for ep in range(start,cfg['epochs']):
        if wait>=cfg['patience']:break
        seed_all(seed+ep);model.train();tot=0.;nb=0
        for b in ld:
            b=batch_to(b,device)
            if b['weight'].sum()==0:continue
            xin=input_dropout(b['x'],groups,n_groups,p_in) if p_in>0 else b['x']
            logits=model(xin,b['mask'],b['hours'],None)
            l=_soft_bce(logits,b['target'],b['weight'])
            if not torch.isfinite(l):raise FloatingPointError(f'{label}: nonfinite loss')
            opt.zero_grad();l.backward();nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step();tot+=float(l.detach());nb+=1
        pred,_=predict(model,bank,val,cfg['batch'],device)
        s=average_precision_score(pred.y,pred.logit) if pred.y.nunique()==2 else float('nan')
        if not np.isfinite(s):raise ValueError(f'{label}: validation target has fewer than two classes')
        if s>best:best=s;wait=0;atomic_torch(best_path,{'state':model.state_dict(),'epoch':ep,'val_AUPRC':best})
        else:wait+=1
        history.append({'epoch':ep+1,'loss':tot/max(nb,1),'val_hourly_AUPRC':s})
        atomic_torch(last_path,{'model':model.state_dict(),'optimizer':opt.state_dict(),'epoch':ep,'best':best,'wait':wait,'history':history})
        print(label,'epoch',ep+1,'loss',round(tot/max(nb,1),5),'validation AUPRC',round(s,5),flush=True)
    model.load_state_dict(torch.load(best_path,map_location=device,weights_only=False)['state'])
    atomic_json(path/'training_history.json',history);return model.eval()

# ----------------------------------------------------------------------------- weakly supervised pretraining (item 3)
class WeakHeads(nn.Module):
    """Heads on the stay representation of a flat OSTA core (the input of its prediction head):
    arrival sepsis (one logit per hour, trained on hours <= 6 against the stay-level flag), the six SOFA components at
    +6/+12/+24 h (smooth-L1 on observed values), and three treatment events within the next 6 h (BCE)."""
    def __init__(self,features,small,dropout):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None;self._global=None
        self.backbone=FlatOSTA(features,small,dropout);self.core=self.backbone.core
        self.core.prediction_head[0].register_forward_hook(lambda m,i,o:setattr(self,'_global',i[0]))
        d=32 if small else 128
        self.sofa=[features.index(f) for f in HEAD_SOFA if f in features];self.sofa_obs=[features.index(f+'_observed') for f in HEAD_SOFA if f in features]
        self.treat=[features.index(c) for c in TREATMENT_COLUMNS.values() if c in features]
        self.arrival=nn.Linear(d,1);self.organ=nn.Sequential(nn.Linear(d,64),nn.GELU(),nn.Linear(64,max(1,len(self.sofa))*3))
        self.events=nn.Linear(d,len(self.treat)+1)   # + antibiotic start
        self.log_var=nn.Parameter(torch.zeros(3))
    def forward(self,x,mask,hours,guidance=None):
        out=self.core(x,mask,hours);b,t,_=x.shape;g=self._global
        return {'logits':out['logits'],'arrival':self.arrival(g).squeeze(-1),'organ':self.organ(g).reshape(b,t,max(1,len(self.sofa)),3),'events':self.events(g)}

def weak_targets(x,mask,hours,b,model):
    """Targets built from the batch itself and the store's weak labels. Every target has a validity mask."""
    bsz,t,_=x.shape;out={}
    early=(hours<=6.)&(mask>.5)&(b['arrival_ok'].view(-1,1)>.5)
    out['arrival']=(b['arrival'].view(-1,1).expand(bsz,t),early.float())
    if model.sofa:
        s=x[:,:,model.sofa];so=x[:,:,model.sofa_obs]>.5;fut=[];ok=[]
        for h in (6,12,24):
            f=torch.zeros_like(s);k=torch.zeros_like(so)
            if t>h:f[:,:-h]=s[:,h:];k[:,:-h]=so[:,h:]&(mask[:,h:].unsqueeze(-1)>.5)
            fut.append(f);ok.append(k)
        out['organ']=(torch.stack(fut,-1),torch.stack(ok,-1).float())
    ev=[];evok=[]
    for j in model.treat:
        now=x[:,:,j]>.5;start=torch.zeros_like(now);known=torch.zeros_like(now)
        for d in range(1,7):
            if t>d:start[:,:-d]|=(x[:,d:,j]>.5)&~now[:,:-d]&(mask[:,d:]>.5);known[:,:-d]|=(mask[:,d:]>.5)
        ev.append(start.float());evok.append((known&(mask>.5)).float())
    ev.append(b['abx6']);evok.append(b['abx6_ok']*mask)
    out['events']=(torch.stack(ev,-1),torch.stack(evok,-1))
    return out

def weak_loss(pred,targets,log_var):
    total=0.;parts={}
    for i,k in enumerate(['arrival','organ','events']):
        if k not in targets:continue
        tgt,ok=targets[k]
        if ok.sum()==0:continue
        l=nn.functional.smooth_l1_loss(pred[k],tgt,reduction='none') if k=='organ' else nn.functional.binary_cross_entropy_with_logits(pred[k],tgt,reduction='none')
        v=(l*ok).sum()/ok.sum();parts[k]=float(v.detach());total=total+torch.exp(-log_var[i])*v+log_var[i]
    return total,parts

def pretrain_weak(stores,features,cfg,seed,path,device,label='pooled'):
    """Multi-task weakly supervised pretraining of a flat OSTA core on the pretraining corpus (`stores`: list of
    Stage2Stores built with weak targets). Checkpoint by validation loss on a held-out tenth of the corpus patients;
    returns the core state dict (loadable into FlatOSTA.core)."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file():return torch.load(path,map_location='cpu',weights_only=False)['core']
    seed_all(seed);model=WeakHeads(features,cfg['small_model'],cfg['dropout']).to(device)
    opt=torch.optim.AdamW(model.parameters(),lr=cfg['learning_rate'],weight_decay=1e-4)
    index=pd.concat([s.index for s in stores],ignore_index=True);norms=stores[0].norms;weak=stores[0].weak
    groups=pd.factorize(index.Group_ID)[0];val_mask=(groups%10==0)
    train=Stage2Store(index[~val_mask],features,norms,cfg['max_hours'],weak=weak);val=Stage2Store(index[val_mask],features,norms,cfg['max_hours'],weak=weak)
    best=math.inf;history=[]
    for ep in range(cfg.get('pretrain_epochs',cfg.get('ssl_epochs',5))):
        for split,store in [('train',train),('val',val)]:
            model.train(split=='train');tot=0.;n=0;agg={}
            for b in loader(store,cfg['batch'],split=='train',seed+ep):
                q=batch_to(b,device)
                with torch.set_grad_enabled(split=='train'):
                    pred=model(q['x'],q['mask'],q['hours']);tg=weak_targets(q['x'],q['mask'],q['hours'],q,model);loss,parts=weak_loss(pred,tg,model.log_var)
                    if split=='train' and torch.is_tensor(loss):
                        opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step()
                tot+=float(loss) if torch.is_tensor(loss) else 0.;n+=1
                for k,v in parts.items():agg[k]=agg.get(k,0.)+v
            avg=tot/max(n,1);history.append({'epoch':ep+1,'split':split,'loss':avg,**{k:v/max(n,1) for k,v in agg.items()}})
            if split=='val' and avg<best:
                best=avg;atomic_torch(path,{'core':{k:v.detach().cpu().clone() for k,v in model.core.state_dict().items()},'seed':seed,'population':label,
                    'validation_loss':best,'stays':int(len(index)),'tasks':['arrival_sepsis','sofa_components_6_12_24h','treatment_events_6h'],
                    'task_weights':torch.exp(-model.log_var).detach().cpu().numpy().tolist(),'warning_labels_used':'none'})
        print(f'WEAK {label} epoch {ep+1} train {history[-2]["loss"]:.4f} val {history[-1]["loss"]:.4f}',flush=True)
    atomic_json(path.with_suffix('.history.json'),history)
    return torch.load(path,map_location='cpu',weights_only=False)['core']

def linear_probe_model(features,cfg,core_state):
    """Zero-shot reading of a pretrained core: the core is frozen and only its prediction head is trained."""
    m=FlatOSTA(features,cfg['small_model'],cfg['dropout']);m.core.load_state_dict(core_state)
    for n,p in m.core.named_parameters():p.requires_grad=n.startswith('prediction_head')
    return m

def subsample_groups(index,frac,seed):
    """A patient-grouped random `frac` of an index (the 10 % target-site fine-tune)."""
    g=index.Group_ID.drop_duplicates().to_numpy();rng=np.random.default_rng(seed);keep=set(rng.choice(g,max(1,int(round(len(g)*frac))),replace=False))
    return index[index.Group_ID.isin(keep)].copy()

# ----------------------------------------------------------------------------- splits beyond partition()
def pooled_partition(index,cfg,datasets):
    """The two databases' own partitions (identical membership to the single-database arms) stacked."""
    return pd.concat([partition(index,ds,cfg) for ds in datasets],ignore_index=True)

def held_out_hospital(h,fraction=.2):
    return int(hashlib.sha256(('sepsis-lho-v1|'+str(h)).encode()).hexdigest()[:8],16)%1000<fraction*1000

def leave_hospital_out(mf,fraction=.2):
    """eICU leave-hospital-out: a hash-selected `fraction` of the development hospitals becomes the test population;
    the remaining hospitals' development patients keep their train/observer_fit/val/calib roles. Hospital grouping is
    deterministic (hash of the hospital id), so the held-out hospitals are fixed before training."""
    e=mf[mf.Dataset.eq('eicu')].copy();held=e.Hospital_ID.map(lambda h:held_out_hospital(h,fraction))
    out=e[held].copy();rest=e[~held&e.split.ne('test')].copy()
    out['split']='test';out['evaluation_scope']='eicu_leave_hospital_out';rest['evaluation_scope']='eicu_leave_hospital_out'
    return pd.concat([rest,out],ignore_index=True)

def temporal_partition(index,cfg,groups_col='AnchorYearGroup',min_test_events=20):
    """MIMIC temporal validation (item 17b): train/val/calib on the earlier anchor-year groups, test on the latest group
    with at least `min_test_events` septic development stays. Protected patients stay sealed."""
    m=index[index.Dataset.eq('miiv')&~index.Group_ID.map(protected_group)&index[groups_col].notna()].copy()
    order=sorted(m[groups_col].unique());test_group=None
    for g in reversed(order):
        if m[m[groups_col].eq(g)].eligible_positive.sum()>=min_test_events and m[m[groups_col].lt(g)].eligible_positive.sum()>=min_test_events:test_group=g;break
    if test_group is None:return None
    test=m[m[groups_col].eq(test_group)].copy();dev=m[m[groups_col].lt(test_group)].copy()
    from sklearn.model_selection import train_test_split
    groups=dev.groupby('Group_ID').eligible_positive.max()
    if groups.nunique()!=2 or groups.value_counts().min()<6:return None
    ids=groups.index.to_numpy();main,hold=train_test_split(ids,test_size=.3,random_state=cfg['split_seed'],stratify=groups.loc[ids])
    val,calib=train_test_split(hold,test_size=.5,random_state=cfg['split_seed'],stratify=groups.loc[hold])
    role={g:s for s,a in [('train',main),('val',val),('calib',calib)] for g in a}
    dev['split']=dev.Group_ID.map(role);test['split']='test'
    out=pd.concat([dev,test],ignore_index=True);out['evaluation_scope']=f'miiv_temporal_test_{test_group}'
    for sp,g in out.groupby('split'):
        if g.eligible_positive.nunique()!=2:return None
    return out

# ----------------------------------------------------------------------------- scoring helpers
def calibration_in_the_large(d):
    """Observed-to-expected ratio and the calibration slope/intercept of the logit (diagnostic only)."""
    y=d.y.to_numpy(float);r=np.clip(d.risk.to_numpy(float),1e-6,1-1e-6);out={'observed_to_expected':float(y.sum()/max(r.sum(),1e-9))}
    if len(np.unique(y))==2:
        from sklearn.linear_model import LogisticRegression
        lg=np.log(r/(1-r)).reshape(-1,1);f=LogisticRegression(C=1e6,solver='lbfgs',max_iter=1000).fit(lg,y)
        out.update({'calibration_slope':float(f.coef_[0,0]),'calibration_intercept':float(f.intercept_[0])})
    return out

def _mk(p):
    p=Path(p);p.mkdir(parents=True,exist_ok=True);return p

def stay_table(tables,key,ds=None):
    """A per-stay mapping {Patient_ID: value} from `tables`, or {} when absent."""
    t=tables.get(key)
    if t is None:return {}
    if isinstance(t,dict) and ds is not None and ds in t:t=t[ds]
    if isinstance(t,dict):return t
    return dict(zip(t.Patient_ID.astype(str),t.iloc[:,-1]))

def sha_frame(df):
    return hashlib.sha256(pd.util.hash_pandas_object(df.reset_index(drop=True),index=False).to_numpy().tobytes()).hexdigest()

# ----------------------------------------------------------------------------- the driver
class Stage2Run:
    """One stage-2 run directory. `tables` (all keyed by Patient_ID; aggregates only are ever printed):
      suspicion_hour      stay -> suspicion-anchored event hour (NaN none)                                 [items 9, 10]
      first_treatment     stay -> first antibiotic or culture hour                                           [item 10d]
      documented          stay -> True/False sepsis documented                                               [items 10c, 10e, 15]
      alt_onsets          {'miiv': {stay: onset, antibiotic-only label}, 'eicu': {stay: onset, culture-paired label}}  [items 10a, 10b]
      abx_starts          stay -> list of antibiotic start hours (dict)                                      [item 3]
      arrival             stay -> 1 arrived septic / 0 not / NaN unknown (dict)                              [item 3]
      anchor_year_group   stay -> MIMIC anchor-year group                                                    [item 17b]
      doc_prior           {'miiv': p, 'eicu': p} documentation prior among operational positives            [item 15]
    cfg keys beyond the stage-1 config: arms (names from ARM_ORDER), seeds, frozen, suspicion_horizon (3), persistence (2),
    operating_point ('quantile'), train_includes_observer_fit (True: the retired observer bank's split joins training),
    shared_physiology (base names), best_non_project_arm, leave_hospital_out, lho_fraction, finetune_fraction, transfer."""
    def __init__(self,index,features,cfg,root,tables,datasets=('miiv','eicu'),corpus=None):
        self.index=index;self.features=list(features);self.cfg=cfg;self.root=_mk(root);self.tables=tables or {};self.datasets=list(datasets);self.corpus=corpus or {}
        self.device=torch.device('cuda' if torch.cuda.is_available() else 'cpu');self.results=[];self.bank=NoBank()
        self.manifest=manifest(self.features);self.mapping,_=organ_mapping(self.features)
        contract={'config':{k:v for k,v in cfg.items() if k!='arms'},'arms':cfg['arms'],'features':self.features,'index_sha':sha_frame(index[['Patient_ID','Group_ID','Dataset']]),
                  'modules':{p.name:sha(p) for p in Path(__file__).parent.glob('v1*_*.py')}}
        key=signature(contract);marker=self.root/'contract.json'
        if marker.exists() and json.loads(marker.read_text())['sha256']!=key:raise ValueError('Run directory contract changed. Select a new RUN_KEY; old results are retained.')
        atomic_json(marker,{'sha256':key,'contract':contract});self.manifest.to_csv(self.root/'two_channel_manifest.csv',index=False)
        self.frozen=bool(cfg.get('frozen',False))
    # ---- seeds and markers
    def seeds(self,arm):
        s=self.cfg['seeds'];return list(s) if (arm in THREE_SEED_ARMS or self.cfg.get('all_arms_all_seeds')) else [s[0]]
    def finish(self,path,records):
        atomic_json(Path(path)/'completed.json',records);self.results+=records
        gc.collect()
        if torch.cuda.is_available():torch.cuda.empty_cache()
    # ---- stores
    def make_store(self,ix,norms,store_cls=Stage2Store,**kw):
        return store_cls(ix,self.features,norms,self.cfg['max_hours'],**kw)
    def stores(self,mf,norms,store_cls=Stage2Store,**kw):
        out={}
        for s in ['train','observer_fit','val','calib','test']:
            ix=mf[mf.split.eq(s)]
            if len(ix):out[s]=self.make_store(ix,norms,store_cls,**kw)
        if 'observer_fit' in out and 'train' in out and self.cfg.get('train_includes_observer_fit',True):
            # stage 2 has no observer bank: its fitting split joins the training split (recorded in the run protocol)
            tr=pd.concat([out['train'].index,out['observer_fit'].index],ignore_index=True);out['train']=self.make_store(tr,norms,store_cls,**kw)
        return out
    def with_suspicion(self,mf):
        sh=stay_table(self.tables,'suspicion_hour');m=mf.copy();m['SuspicionHour']=m.Patient_ID.astype(str).map(sh).astype(float)
        m['OnsetHour']=m.SuspicionHour;m['eligible_positive']=m.SuspicionHour.notna().astype(int)
        m['FirstAntibioticAroundOnset']=np.nan;return m
    def other_dev(self,ds):
        o=self.index[self.index.Dataset.ne(ds)&~self.index.Group_ID.map(protected_group)].copy();return o if len(o) else None
    # ---- prediction + calibration + operating point (shared by every arm)
    def fit_and_score(self,name,target_ds,model_fn,stores,mf,path,seed,target='operational',transfer_store=None,extra_rows=None,utility=True,arm_label=None,feature_set='rich'):
        """Train (or load) a model, calibrate on calib, choose the operating point, score test (sealed unless frozen),
        write predictions and run the scoring passes. `model_fn(path)` returns the trained model (nn.Module or sklearn);
        `extra_rows(model,pred,params,chosen,base,path)` may append rows. Returns the records list."""
        path=_mk(path);done=path/'completed.json'
        if done.is_file():
            recs=json.loads(done.read_text());self.results+=recs;print('Reuse',target_ds,name,flush=True);return recs
        seed_all(seed);model=model_fn(path);cfg=self.cfg;tab=not isinstance(model,nn.Module)
        if tab:
            def pred(store,all_hours=False):return tabular_predict(model,store,all_hours)
        else:
            def pred(store,all_hours=False):return predict(model,self.bank,store,cfg['batch'],self.device,'normal',all_hours)[0]
        cal=pred(stores['calib']);params=calibrate(cal);cal=apply_calibration(cal,params);chosen,sweep=select_threshold(cal,cfg)
        chosen['alarm_fraction']=alarm_fraction(cal,chosen['threshold'])
        vp=pred(stores['val']);vcal=apply_calibration(vp,params);vpanel=validation_panel(vp,cfg)
        full_cal=pred(stores['calib'],all_hours=True);util={}
        if utility and target=='operational':
            full_test=pred(stores['test'],all_hours=True);util=utility_block(full_cal,full_test,params,cfg,seed,path)
            apply_calibration(full_test,params).to_parquet(path/'predictions_allhours.parquet',index=False)
        apply_calibration(full_cal,params).to_parquet(path/'predictions_allhours_calib.parquet',index=False)
        atomic_json(path/'calibration_and_threshold.json',{'platt':params,'chosen':chosen,**vpanel});pd.DataFrame(sweep).to_csv(path/'threshold_sweep.csv',index=False)
        # validation rows (always reported): the policy on the validation split; abstention variants (item 16)
        thr_v,used_v=operating_threshold(vcal,chosen,cfg);mv,_,_=evaluate_v11(vcal,thr_v,cfg,cfg.get('persistence',1),bool(cfg.get('fresh_only',False)))
        base={'target':target_ds,'seed':seed,'arm':name,'base_arm':arm_label or name,'label':target,'feature_set':feature_set,'feature_count':len(stores['train'].features),
              'main_training_stays':len(stores['train']),'alarm_fraction':chosen['alarm_fraction'],'absolute_threshold':chosen['threshold'],**vpanel}
        records=[{**base,'condition':'validation','scope':'validation_split','operating_point_used':used_v,**mv}]
        if cfg.get('abstention_rows',True) and not tab and measured_channels(stores['val'].features):
            vo=ood_scores(stores['val']);co=ood_scores(stores['calib']);s=np.sort(co.ood.to_numpy());n=len(s)
            tau=float(s[min(n-1,int(np.ceil((n+1)*(1-cfg.get('conformal_alpha',.02))))-1)]) if n else 1.
            ar=abstention_rows(vcal,vo,tau,thr_v,cfg,cfg.get('persistence',2));ad=adopt_abstention(ar,'reset');ar=ar.merge(ad,on='abstention');ar.to_csv(path/'abstention_validation.csv',index=False)
            for _,r in ar.iterrows():records.append({**base,'condition':'validation_abstention_'+r.abstention,'scope':'validation_split',**{k:r[k] for k in ar.columns if k!='abstention'}})
        # test split: scored, written, SEALED unless frozen
        d=pred(stores['test']);d=apply_calibration(d,params);d.to_parquet(path/'predictions_normal.parquet',index=False)
        thr_t,used_t=operating_threshold(d,chosen,cfg);m,alarms,points=evaluate_v11(d,thr_t,cfg,cfg.get('persistence',1),bool(cfg.get('fresh_only',False)))
        m.update({'operating_point_used':used_t,'persistence':cfg.get('persistence',1)});m.update(clustered_ci(d,cfg['bootstrap'],seed));m.update(hospital_ci(d,cfg['bootstrap'],seed));m.update(util)
        m.update(antibiotic_lead(d,thr_t,cfg));m.update(calibration_in_the_large(d))
        test_rows=[{**base,'condition':'normal','scope':mf.evaluation_scope.iloc[0],**m}]
        alarms.to_parquet(path/'alarms_normal.parquet',index=False);points.to_csv(path/'calibration_normal.csv',index=False)
        test_rows+=self.scoring_passes(d,thr_t,chosen,base,target_ds,target)
        if transfer_store is not None:
            dt=apply_calibration(pred(transfer_store),params);thr_o,used_o=operating_threshold(dt,chosen,cfg)
            mt,_,_=evaluate_v11(dt,thr_o,cfg,cfg.get('persistence',1),bool(cfg.get('fresh_only',False)));mt.update({'operating_point_used':used_o});mt.update(clustered_ci(dt,cfg['bootstrap'],seed));mt.update(hospital_ci(dt,cfg['bootstrap'],seed))
            mt.update(antibiotic_lead(dt,thr_o,cfg));mt.update(calibration_in_the_large(dt));ot=transfer_store.index.Dataset.iloc[0]
            test_rows.append({**base,'target':f'{ot}_from_{target_ds}','condition':'normal','scope':'development_transfer_other_database_dev_patients',**mt})
            dt.to_parquet(path/'transfer_predictions.parquet',index=False)
            test_rows+=self.scoring_passes(dt,thr_o,chosen,{**base,'target':f'{ot}_from_{target_ds}'},ot,target)
        if extra_rows is not None:test_rows+=extra_rows(model,pred,params,chosen,base,path)
        if self.frozen:records+=test_rows
        else:atomic_json(path/'test_rows_sealed.json',test_rows)
        self.finish(path,records);del model;print('Completed',target_ds,name,flush=True);return records
    def scoring_passes(self,d,thr,chosen,base,ds,target):
        """Protocol 10c.2 items 8, 10, 17 on one saved prediction frame."""
        cfg=self.cfg;rows=[];pers=cfg.get('persistence',1)
        ft=stay_table(self.tables,'first_treatment')
        if ft:
            dp=pre_treatment(d,ft);rows.append({**base,'condition':'pre_treatment_hours','scope':'hours before the first antibiotic or culture',**score(dp,thr,cfg,pers),**pre_treatment_summary(dp,thr,ft,pers)})
        doc=stay_table(self.tables,'documented')
        if doc:
            for k,v in documentation_strata(d,doc).items():rows.append({**base,'condition':f'documentation_{k}','scope':f'{k} positives with all controls',**score(v,thr,cfg,pers)})
        sh=stay_table(self.tables,'suspicion_hour')
        if target=='operational':
            if sh:
                for h in (3,6):rows.append({**base,'condition':f'suspicion_label_{h}h','scope':'primary model scored against the suspicion-anchored label',**score(relabel(d,sh,h),thr,{**cfg,'horizon':h},pers)})
            alt=self.tables.get('alt_onsets',{}).get(ds)
            if alt:rows.append({**base,'condition':'alternative_operational_label','scope':'antibiotic-only (MIMIC) / culture-paired (eICU) sep3 label',**score(relabel(d,alt,cfg['horizon']),thr,cfg,pers)})
        elif sh:
            for _,r in suspicion_readings(d,sh,cfg,{**chosen,'threshold':thr},horizons=(3,6)).iterrows():
                rows.append({**base,'condition':f'suspicion_reading_{int(r.reading_horizon_h)}h','scope':'suspicion target at its own and the 6 h reading',**{k:r[k] for k in r.index if k!='reading_horizon_h'}})
        if ds=='eicu' and d.Hospital_ID.nunique()>1:
            tt,disp=threshold_transport(d,{**chosen,'threshold':thr},cfg,cfg.get('quantile_min_hours',10000),cfg.get('transport_min_stays',20))
            for _,r in disp.iterrows():rows.append({**base,'condition':'threshold_transport_'+r.rule,'scope':'per-hospital dispersion (eICU)','persistence':pers,**{k:r[k] for k in disp.columns if k!='rule'}})
        return rows
    # ---- arms
    def run(self):
        for arm in [a for a in ARM_ORDER if a in self.cfg['arms']]:
            print('==== arm',arm,time.strftime('%H:%M'),flush=True);getattr(self,'arm_'+arm)()
        out=pd.DataFrame(self.results);out.to_csv(self.root/'results.csv',index=False);return out
    def _single(self,ds,seed,name,arm_model,target='operational',feature_set='rich',extra=None,arm_label=None,utility=True,transfer=True,store_cls=Stage2Store,store_kw=None,cfg=None):
        """One database, one seed, one arm: partition, normaliser, stores, training, scoring, transfer row.
        `arm_model(stores,path)` returns an untrained nn.Module (trained here) or a fitted sklearn estimator."""
        kw=store_kw or {};cfg=cfg or self.cfg;saved=self.cfg;self.cfg=cfg
        try:
            mf=partition(self.index,ds,cfg)
            if target=='suspicion':mf=self.with_suspicion(mf)
            fit_ix=mf[mf.split.isin(['train','observer_fit'])]
            norms=fit_norms(fit_ix,self.features,cfg['max_hours'],[ds],store_cls,**kw)
            st=self.stores(mf,norms,store_cls,target=target,horizon=cfg.get('suspicion_horizon',3.),**kw)
            other=None
            if transfer and cfg.get('transfer',True):
                o=self.other_dev(ds)
                if o is not None:
                    if target=='suspicion':o=self.with_suspicion(o)
                    other=store_cls(o,self.features,norms[ds],cfg['max_hours'],target=target,horizon=cfg.get('suspicion_horizon',3.),**kw)   # the target's normaliser, as in stage 1
            path=_mk(self.root/f'seed_{seed}'/ds)/name
            def model_fn(p):
                model=arm_model(st,p)
                if isinstance(model,nn.Module):return train_stage2(model,st['train'],st['val'],cfg,seed,p,self.device,f'{ds}/{name}')
                return model
            return self.fit_and_score(name,ds,model_fn,st,mf,path,seed,target,other,extra,utility,arm_label,feature_set)
        finally:self.cfg=saved
    def arm_project(self):
        for seed in self.seeds('project'):
            for ds in self.datasets:self._single(ds,seed,'flat_osta',lambda st,p:make_model('flat_osta',self.features,self.cfg))
        if 'anchor_year_group' in self.tables:self.temporal_validation(self.seeds('project')[0])   # item 17b on the project model
    def arm_two_channel(self):
        for seed in self.seeds('two_channel'):
            for ds in self.datasets:
                mf=partition(self.index,ds,self.cfg);norms=fit_norms(mf[mf.split.isin(['train','observer_fit'])],self.features,self.cfg['max_hours'],[ds]);st=self.stores(mf,norms)
                o=self.other_dev(ds);ot=self.make_store(o,norms[ds]) if o is not None else None;sd=_mk(self.root/f'seed_{seed}'/ds)
                def extra(model,pred,params,chosen,base,path,st=st,norms=norms,ds=ds):
                    """Item 14 evaluation rows on the SAME trained two-channel model."""
                    rows=[];cfg=self.cfg;test_ix=st['test'].index;scopes={'zero':'practice path zeroed at test time','zscore':'practice path re-standardised on the test population','quantile':'practice path quantile-mapped to the training distribution'}
                    for mode in ('zero','zscore','quantile'):
                        if mode=='zscore' and ds=='eicu':
                            frames=[]   # per hospital where the hospital has enough stays
                            for hosp,g in test_ix.groupby('Hospital_ID'):
                                if g.Patient_ID.nunique()<cfg.get('transport_min_stays',20):continue
                                spec=practice_spec('zscore',self.features,self.manifest,st['train'],self.make_store(g,norms));frames.append(pred(self.make_store(g,norms,practice=spec)))
                            if not frames:continue
                            d=pd.concat(frames,ignore_index=True);scope='practice path z-scored per eICU hospital'
                        else:
                            spec=practice_spec(mode,self.features,self.manifest,st['train'],self.make_store(test_ix,norms));d=pred(self.make_store(test_ix,norms,practice=spec));scope=scopes[mode]
                        d=apply_calibration(d,params);thr,used=operating_threshold(d,chosen,cfg);m,_,_=evaluate_v11(d,thr,cfg,cfg.get('persistence',1));m.update({'operating_point_used':used});m.update(calibration_in_the_large(d))
                        rows.append({**base,'condition':'practice_'+mode,'scope':scope,**m});d.to_parquet(Path(path)/f'predictions_practice_{mode}.parquet',index=False)
                    return rows
                self.fit_and_score('two_channel',ds,lambda p:train_stage2(make_stage2_model('two_channel',self.features,self.cfg,self.manifest),st['train'],st['val'],self.cfg,seed,p,self.device,f'{ds}/two_channel'),st,mf,sd/'two_channel',seed,'operational',ot,extra)
                # practice-only probe (same hours)
                self.fit_and_score('practice_path',ds,lambda p:train_stage2(make_stage2_model('practice_path',self.features,self.cfg,self.manifest),st['train'],st['val'],self.cfg,seed,p,self.device,f'{ds}/practice_path'),st,mf,sd/'practice_path',seed,'operational',ot,None,utility=False)
                # concept-grouped practice path comparator
                cg=concept_grouped_practice(self.features,self.mapping)
                if cg:
                    stc=self.stores(mf,norms,concept=cg);feats=stc['train'].features
                    mc=self.manifest.copy();mc.loc[mc.path.eq('practice'),'path']='dropped'
                    mc=pd.concat([mc,pd.DataFrame({'feature':[c for c,_,_ in cg],'path':'practice','block':'concept_group','availability_dependent':False})],ignore_index=True)
                    otc=self.make_store(o,norms[ds],concept=cg) if o is not None else None
                    self.fit_and_score('two_channel_concept',ds,lambda p:train_stage2(TwoChannelOSTA(feats,self.cfg['small_model'],self.cfg['dropout'],True,mc),stc['train'],stc['val'],self.cfg,seed,p,self.device,f'{ds}/two_channel_concept'),stc,mf,sd/'two_channel_concept',seed,'operational',otc,None,utility=False,feature_set='concept_grouped_practice')
    def arm_pooled(self):
        for seed in self.seeds('pooled'):
            mf=pooled_partition(self.index,self.cfg,self.datasets);norms=fit_norms(mf[mf.split.isin(['train','observer_fit'])],self.features,self.cfg['max_hours'],self.datasets)
            st=self.stores(mf,norms);sd=_mk(self.root/f'seed_{seed}'/'pooled')
            def extra(model,pred,params,chosen,base,path):
                rows=[]
                for ds in self.datasets:   # each database's own test split under the pooled model
                    ix=st['test'].index[st['test'].index.Dataset.eq(ds)]
                    if not len(ix):continue
                    d=apply_calibration(pred(self.make_store(ix,norms)),params);thr,used=operating_threshold(d,chosen,self.cfg)
                    m,_,_=evaluate_v11(d,thr,self.cfg,self.cfg.get('persistence',1));m.update({'operating_point_used':used});m.update(clustered_ci(d,self.cfg['bootstrap'],seed));m.update(hospital_ci(d,self.cfg['bootstrap'],seed));m.update(calibration_in_the_large(d))
                    rows.append({**base,'target':ds,'condition':'pooled_model_own_test','scope':"pooled model on this database's test split",**m})
                    rows+=self.scoring_passes(d,thr,chosen,{**base,'target':ds},ds,'operational');d.to_parquet(Path(path)/f'predictions_{ds}.parquet',index=False)
                return rows
            self.fit_and_score('flat_osta_pooled','pooled',lambda p:train_stage2(make_model('flat_osta',self.features,self.cfg),st['train'],st['val'],self.cfg,seed,p,self.device,'pooled/flat_osta'),st,mf,sd/'flat_osta_pooled',seed,'operational',None,extra,utility=False)
            # eICU leave-hospital-out under pooled training: MIMIC development + the non-held-out eICU hospitals
            if 'eicu' in self.datasets and self.cfg.get('leave_hospital_out',True):
                lho=leave_hospital_out(mf,self.cfg.get('lho_fraction',.2));mm=pd.concat([mf[mf.Dataset.ne('eicu')&mf.split.ne('test')],lho],ignore_index=True)
                if mm[mm.split.eq('test')].eligible_positive.sum()>=11 and mm[mm.split.eq('test')].eligible_positive.nunique()==2:
                    stl=self.stores(mm,norms)
                    self.fit_and_score('flat_osta_pooled_lho','eicu',lambda p:train_stage2(make_model('flat_osta',self.features,self.cfg),stl['train'],stl['val'],self.cfg,seed,p,self.device,'pooled/lho'),stl,mm,sd/'flat_osta_pooled_lho',seed,'operational',None,None,utility=False,arm_label='flat_osta_pooled')
                else:print('Leave-hospital-out: fewer than 11 septic stays in the held-out hospitals; skipped.',flush=True)
    def arm_suspicion(self):
        if not stay_table(self.tables,'suspicion_hour'):print('No suspicion table: the suspicion-anchored arm is skipped.');return
        cfg3={**self.cfg,'horizon':int(self.cfg.get('suspicion_horizon',3))}
        for seed in self.seeds('suspicion'):
            for ds in self.datasets:
                self._single(ds,seed,'flat_osta@suspicion',lambda st,p:make_model('flat_osta',self.features,cfg3),target='suspicion',utility=False,cfg=cfg3)
                if self.cfg.get('best_non_project_arm')=='two_channel':
                    self._single(ds,seed,'two_channel@suspicion',lambda st,p:make_stage2_model('two_channel',self.features,cfg3,self.manifest),target='suspicion',utility=False,cfg=cfg3)
    def arm_pretrained(self):
        """Item 3: weak multi-task pretraining of the pooled core; then (a) full fine-tune at home, (b) zero-shot on the
        other database (frozen core, head trained at home; the transfer row), (c) 10 % target-site fine-tune."""
        for seed in self.seeds('pretrained'):
            mf=pooled_partition(self.index,self.cfg,self.datasets);norms=fit_norms(mf[mf.split.isin(['train','observer_fit'])],self.features,self.cfg['max_hours'],self.datasets)
            weak={'abx_starts':self.tables.get('abx_starts',{}),'arrival':self.tables.get('arrival',{})}
            corpus_ix=[mf[mf.split.isin(['train','observer_fit'])]]+[c for c in self.corpus.values() if c is not None and len(c)]
            cix=pd.concat(corpus_ix,ignore_index=True);cix=cix[~cix.Group_ID.map(protected_group)]
            excluded=set(mf[mf.split.isin(['val','calib','test'])].Group_ID);cix=cix[~cix.Group_ID.isin(excluded)].drop_duplicates('Patient_ID')
            sd=_mk(self.root/f'seed_{seed}');core=pretrain_weak([self.make_store(cix,norms,weak=weak)],self.features,self.cfg,seed,sd/'weak_core_pooled.pt',self.device)
            atomic_json(sd/'weak_core_corpus.json',{'stays':int(len(cix)),'per_dataset':{k:int(v) for k,v in cix.groupby('Dataset').size().items()},'excluded_val_calib_test_groups':int(len(excluded))})
            for ds in self.datasets:
                def warm(st,p,core=core):
                    m=make_model('flat_osta',self.features,self.cfg);m.core.load_state_dict(core);return m
                self._single(ds,seed,'flat_osta_weakpre',warm,arm_label='flat_osta_weakpre')
                self._single(ds,seed,'flat_osta_weakpre_zeroshot',lambda st,p,core=core:linear_probe_model(self.features,self.cfg,core),arm_label='flat_osta_weakpre',utility=False)
                others=[d for d in self.datasets if d!=ds]
                if others:
                    o=others[0];mo=partition(self.index,o,self.cfg);no=fit_norms(mo[mo.split.isin(['train','observer_fit'])],self.features,self.cfg['max_hours'],[o]);sto=self.stores(mo,no)
                    sto['train']=self.make_store(subsample_groups(sto['train'].index,self.cfg.get('finetune_fraction',.1),seed),no)
                    home=self.root/f'seed_{seed}'/ds/'flat_osta_weakpre'/'best.pt';name=f'flat_osta_weakpre_finetune10_from_{ds}'
                    def ft10(p,home=home,sto=sto,o=o,ds=ds):
                        m=make_model('flat_osta',self.features,self.cfg)
                        if home.is_file():m.load_state_dict(torch.load(home,map_location='cpu',weights_only=False)['state'])
                        return train_stage2(m,sto['train'],sto['val'],{**self.cfg,'learning_rate':self.cfg['learning_rate']/3},seed,p,self.device,f'{o}/finetune10_from_{ds}')
                    self.fit_and_score(name,o,ft10,sto,mo,self.root/f'seed_{seed}'/o/name,seed,'operational',None,None,utility=False,arm_label='flat_osta_weakpre',feature_set=f'finetune_{int(round(self.cfg.get("finetune_fraction",.1)*100))}pct_target_site')
    def arm_predictor_sets(self):
        """Item 2: (a) the physiology path with the host block; (c) the same without masks and ages is the physiology path
        itself (masks and ages are practice columns), so (a) is reported with and without the host block; (b) the shared
        physiology set (cfg['shared_physiology'] base names, value+mask+age). Item 7: baseline-relative, absolute same
        channels, both."""
        shared=self.cfg.get('shared_physiology',[]);small=self.cfg['small_model'];drop=self.cfg['dropout']
        for seed in self.seeds('predictor_sets'):
            for ds in self.datasets:
                self._single(ds,seed,'physiology_path',lambda st,p:make_stage2_model('physiology_path',self.features,self.cfg,self.manifest),feature_set='physiology_with_host',utility=False)
                self._single(ds,seed,'physiology_path_nohost',lambda st,p:make_stage2_model('physiology_path_nohost',self.features,self.cfg,self.manifest),feature_set='physiology_without_host',utility=False)
                if shared:
                    idx=[i for i,f in enumerate(self.features) if base_name(f) in shared]
                    if idx:self._single(ds,seed,'shared_physiology',lambda st,p,idx=idx:SubsetFlatOSTA(self.features,idx,small,drop),feature_set=f'shared_physiology_{len(idx)}_columns',utility=False)
                for mode in ('relative','absolute','both'):
                    self._single(ds,seed,'baseline_'+mode,lambda st,p:make_model('flat_osta',st['train'].features,self.cfg),feature_set='baseline_'+mode,utility=False,store_cls=BaselineStore,store_kw={'mode':mode})
    def arm_label_stratified(self):
        doc=stay_table(self.tables,'documented')
        if not doc:print('No documentation table: the label-stratified arm is skipped.');return
        prior=self.tables.get('doc_prior',{})
        for seed in self.seeds('label_stratified'):
            for ds in self.datasets:
                mf=partition(self.index,ds,self.cfg);norms=fit_norms(mf[mf.split.isin(['train','observer_fit'])],self.features,self.cfg['max_hours'],[ds])
                pos=mf.OnsetHour.notna();isdoc=mf.Patient_ID.astype(str).map(doc).fillna(False).astype(bool);p=float(prior.get(ds,np.nan))
                variants={'documented':{'StayWeight':np.where(pos&~isdoc,0.,1.)},'pu_soft':{'StayValue':np.where(pos&~isdoc,p if np.isfinite(p) else 1.,1.)}}
                for name,cols in variants.items():
                    m=mf.copy()
                    for k,v in cols.items():m[k]=v
                    st=self.stores(m,norms)
                    def extra(model,pred,params,chosen,base,path,st=st):
                        d=apply_calibration(pred(st['test']),params);thr,used=operating_threshold(d,chosen,self.cfg)   # cross-evaluation: documented-and-operational label
                        return [{**base,'condition':'eval_label_documented_and_operational','scope':'documented positives + all controls','operating_point_used':used,**score(documentation_strata(d,doc)['documented'],thr,self.cfg,self.cfg.get('persistence',1))}]
                    self.fit_and_score('flat_osta@'+name,ds,lambda p,st=st,name=name:train_stage2(make_model('flat_osta',self.features,self.cfg),st['train'],st['val'],self.cfg,seed,p,self.device,f'{ds}/{name}'),st,m,self.root/f'seed_{seed}'/ds/('flat_osta@'+name),seed,'operational',None,extra,utility=False,arm_label='flat_osta')
    def arm_benchmarks(self):
        for seed in self.seeds('benchmarks'):
            for ds in self.datasets:
                for arm in ('grud','tcn'):self._single(ds,seed,arm,lambda st,p,arm=arm:make_model(arm,self.features,self.cfg),utility=False)
                for arm in ('logistic','boosted_tree'):self._single(ds,seed,arm,lambda st,p,arm=arm:fit_tabular_v11(arm,st['train'],st['val'],self.cfg,seed,p),utility=False,transfer=bool(self.cfg.get('tabular_transfer',False)))
    def arm_exploratory(self):
        if not self.corpus:print('No unlabelled corpus: the exploratory SSL pair is skipped.');return
        from v9_models import ObserverBank
        for seed in self.seeds('exploratory'):
            for ds in self.datasets:
                mf=partition(self.index,ds,self.cfg);norms=fit_norms(mf[mf.split.isin(['train','observer_fit'])],self.features,self.cfg['max_hours'],[ds])
                parts=[SequenceStore(c,self.features,norms[ds],self.cfg['max_hours']) for c in self.corpus.values() if c is not None and len(c)]
                enc=pretrain(parts,self.features,self.cfg,seed,self.root/f'seed_{seed}'/ds/'ssl_encoder_pooled.pt',self.device,'pooled')
                bank=ObserverBank(self.features,hidden=self.cfg.get('observer_hidden',32)).to(self.device).eval().requires_grad_(False)
                for arm in ('ssl_cnn_flat_pooled','ssl_cnn_osta_pooled'):
                    self._single(ds,seed,arm,lambda st,p,arm=arm:build_model(arm,self.features,bank,self.cfg,enc),utility=False)
    def temporal_validation(self,seed):
        ayg=stay_table(self.tables,'anchor_year_group');ix=self.index[self.index.Dataset.eq('miiv')].copy();ix['AnchorYearGroup']=ix.Patient_ID.astype(str).map(ayg)
        mf=temporal_partition(ix,self.cfg,min_test_events=self.cfg.get('temporal_min_events',20))
        if mf is None:print('Temporal validation: no anchor-year group with enough events; skipped.',flush=True);return
        norms=fit_norms(mf[mf.split.eq('train')],self.features,self.cfg['max_hours'],['miiv']);st=self.stores(mf,norms)
        def extra(model,pred,params,chosen,base,path):
            d=apply_calibration(pred(st['test']),params);rows=[]
            for rule in ('absolute','quantile'):
                thr=chosen['threshold'] if rule=='absolute' else (quantile_threshold(d,chosen['alarm_fraction'],self.cfg.get('quantile_min_hours',10000)) or chosen['threshold'])
                m,_,_=evaluate_v11(d,thr,self.cfg,self.cfg.get('persistence',1));m.update(calibration_in_the_large(d));m['realised_alarm_fraction']=alarm_fraction(d,thr)
                rows.append({**base,'condition':'temporal_'+rule,'scope':mf.evaluation_scope.iloc[0],**m})
            return rows
        self.fit_and_score('flat_osta_temporal','miiv',lambda p:train_stage2(make_model('flat_osta',self.features,self.cfg),st['train'],st['val'],self.cfg,seed,p,self.device,'miiv/temporal'),st,mf,self.root/f'seed_{seed}'/'miiv'/'flat_osta_temporal',seed,'operational',None,extra,utility=False,arm_label='flat_osta')

def run_stage2(index,features,cfg,root,tables=None,datasets=('miiv','eicu'),corpus=None):
    return Stage2Run(index,features,cfg,root,tables,datasets,corpus).run()
