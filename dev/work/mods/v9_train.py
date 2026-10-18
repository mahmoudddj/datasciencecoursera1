"""Common prospective training/evaluation for every v9 comparison arm."""
from pathlib import Path
from collections import OrderedDict
import json, os, random, math, gc, hashlib, time
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import Dataset,DataLoader,Sampler
from sklearn.model_selection import train_test_split
from sklearn.metrics import average_precision_score,roc_auc_score,brier_score_loss
from sklearn.linear_model import LogisticRegression
from v9_models import ObserverBank,ExperimentModel,perturb_guidance

OSTA_FAMILY=['osta','observer_features','output_fusion','gated_attention','ungated_attention']
AGE_SCALE=24.

def osta_original_loss(output,targets,masks,organ_consistency_weight=.1,organ_diversity_weight=.05,early_alpha=.3,focal_gamma=2.,
                       alpha_pos=.75,alpha_neg=.25,post_weight=1.5):
    """Port of legacy_osta_original.osta_loss (the loss the original OSTA was trained with), with the
    per-row time-weight loop vectorised; the optional rank loss (off by default there) is not included.
    Terms: focal BCE (gamma 2, alpha 0.75/0.25) x time weights (exp(-0.3*(t_first_pos - t)) before the first
    positive hour, 1.5 from it on) averaged over masked hours; + 0.1 x mean organ BCE; + 0.05 x -log var(organ weights)."""
    logits=output['logits'];B,T=targets.shape
    bce=nn.functional.binary_cross_entropy_with_logits(logits,targets,reduction='none')
    probs=torch.sigmoid(logits);pt=torch.where(targets==1,probs,1-probs)
    alpha_t=torch.where(targets==1,torch.tensor(alpha_pos,device=logits.device),torch.tensor(alpha_neg,device=logits.device))
    focal=alpha_t*(1-pt)**focal_gamma*bce
    pos=(targets==1);has=pos.any(1);first=torch.argmax(pos.int(),dim=1)
    t=torch.arange(T,device=logits.device).unsqueeze(0).float();f=first.unsqueeze(1).float()
    tw=torch.where(t<f,torch.exp(-early_alpha*(f-t)),torch.full_like(t.expand(B,T),post_weight))
    tw=torch.where(has.unsqueeze(1),tw,torch.ones_like(tw))
    loss=(focal*tw*masks).sum()/(masks.sum()+1e-8)
    if 'organ_risks' in output and output['organ_risks']:
        organ=sum((nn.functional.binary_cross_entropy_with_logits(r,targets,reduction='none')*masks).sum()/(masks.sum()+1e-8)
                  for r in output['organ_risks'].values())/len(output['organ_risks'])
        loss=loss+organ_consistency_weight*organ
    if 'organ_risk_weights' in output:
        loss=loss+organ_diversity_weight*(-torch.log(output['organ_risk_weights'].var()+1e-8))
    return loss

def seed_all(seed):
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    if torch.cuda.is_available():torch.cuda.manual_seed_all(seed)

def atomic_json(path,data):
    path=Path(path);tmp=path.with_suffix('.partial.json')
    tmp.write_text(json.dumps(data,indent=2,default=str));os.replace(tmp,path)

def atomic_torch(path,data):
    path=Path(path);tmp=path.with_suffix('.partial.pt');torch.save(data,tmp);os.replace(tmp,path)

def grouped_manifest(index,heldout,seed=42):
    dev=index[index.Dataset.ne(heldout)].copy();test=index[index.Dataset.eq(heldout)].copy()
    groups=dev.groupby('Group_ID').eligible_positive.max()
    if groups.value_counts().min()<10:raise ValueError('Too few positive/negative patient groups for observer/train/validation/calibration splits; increase smoke sample.')
    def split(ids,fraction):
        return train_test_split(ids,test_size=fraction,random_state=seed,stratify=groups.loc[ids])
    # Same main training rows for A/B/C/D; observers use disjoint development patients.
    main,hold=split(groups.index.to_numpy(),.4)
    observer,vc=split(hold,.5)
    val,calib=split(vc,.5)
    role={g:sp for sp,ids in [('train',main),('observer_fit',observer),('val',val),('calib',calib)] for g in ids}
    dev['split']=dev.Group_ID.map(role);test['split']='test';mf=pd.concat([dev,test],ignore_index=True)
    assert mf.groupby('Group_ID').split.nunique().max()==1
    for sp,g in mf.groupby('split'):
        if g.eligible_positive.nunique()!=2:raise ValueError(f'{heldout}/{sp}: both outcome classes are required.')
    return mf

class SequenceStore(Dataset):
    def __init__(self,index,features,norm=None,max_hours=120):
        self.index=index.reset_index(drop=True);self.features=features;self.norm=norm;self.max_hours=max_hours;self.cache=OrderedDict()
    def __len__(self):return len(self.index)
    def frame(self,i):
        r=self.index.iloc[i];file=r['file']
        if file not in self.cache:
            self.cache[file]=pd.read_parquet(file)
            while len(self.cache)>1:self.cache.popitem(last=False)
        self.cache.move_to_end(file)
        return self.cache[file].iloc[int(r.offset):int(r.offset+r.length)]
    def __getitem__(self,i):
        d=self.frame(i);n=min(len(d),self.max_hours)
        x=d[self.features].iloc[:n].to_numpy(dtype=np.float32)
        if self.norm is not None:
            x=(x-self.norm['mean'])/self.norm['std'];x=np.nan_to_num(x,nan=0.,posinf=0.,neginf=0.)
            x=np.clip(x,-20,20)
        else:x=np.nan_to_num(x,nan=0.,posinf=0.,neginf=0.)
        padded=np.zeros((self.max_hours,len(self.features)),np.float32);padded[:n]=x
        y=np.zeros(self.max_hours,np.float32);y[:n]=d.SepsisLabel.iloc[:n]
        eligible=np.zeros(self.max_hours,np.float32);eligible[:n]=d.Eligible.iloc[:n]
        mask=np.zeros(self.max_hours,np.float32);mask[:n]=1
        hours=np.zeros(self.max_hours,np.float32);hours[:n]=d.Hour.iloc[:n]
        return {'x':padded,'y':y,'eligible':eligible,'mask':mask,'hours':hours,'idx':i}

def fit_normalizer(store):
    total=np.zeros(len(store.features));sq=total.copy();count=total.copy()
    for i in range(len(store)):
        x=store.frame(i)[store.features].to_numpy(dtype=float);valid=np.isfinite(x)
        v=np.where(valid,x,0.);total+=v.sum(0);sq+=(v*v).sum(0);count+=valid.sum(0)
    mean=np.divide(total,count,out=np.zeros_like(total),where=count>0)
    var=np.divide(sq,count,out=np.ones_like(total),where=count>0)-mean**2
    std=np.sqrt(np.maximum(var,1e-6));std[count==0]=1
    for j,f in enumerate(store.features):
        if f.endswith('_observed'):mean[j]=0.;std[j]=1.
        elif f.endswith('_age'):mean[j]=0.;std[j]=AGE_SCALE   # v11: hours -> days, so 'fresh' is age*24 < 1
    return {'mean':mean.astype(np.float32),'std':std.astype(np.float32),'count':count.astype(int)}

class ShardBatches(Sampler):
    def __init__(self,index,batch,shuffle,seed):self.groups=[g.index.to_numpy() for _,g in index.reset_index(drop=True).groupby('file',sort=False)];self.batch=batch;self.shuffle=shuffle;self.seed=seed;self.epoch=0
    def __len__(self):return sum(math.ceil(len(g)/self.batch) for g in self.groups)
    def __iter__(self):
        rng=np.random.default_rng(self.seed+self.epoch);self.epoch+=1;order=np.arange(len(self.groups))
        if self.shuffle:rng.shuffle(order)
        for k in order:
            ix=self.groups[k].copy()
            if self.shuffle:rng.shuffle(ix)
            for start in range(0,len(ix),self.batch):yield ix[start:start+self.batch].tolist()

def loader(store,batch,shuffle=False,seed=42):
    # Shard-local batches avoid rereading hundreds of Drive Parquets per random batch.
    return DataLoader(store,batch_sampler=ShardBatches(store.index,batch,shuffle,seed),num_workers=0,pin_memory=torch.cuda.is_available())

def batch_to(b,device):return {k:(v.to(device) if torch.is_tensor(v) else v) for k,v in b.items()}

def train_observers(store,features,cfg,seed,path,device):
    seed_all(seed);bank=ObserverBank(features,hidden=cfg.get('observer_hidden',32)).to(device)
    if Path(path).is_file():bank.load_state_dict(torch.load(path,map_location=device,weights_only=False)['state']);return bank.eval().requires_grad_(False)
    opt=torch.optim.AdamW(bank.parameters(),lr=cfg['learning_rate'],weight_decay=1e-4)
    last=Path(path).with_suffix('.last.pt');start=0
    if last.is_file():
        state=torch.load(last,map_location=device,weights_only=False)
        bank.load_state_dict(state['state']);opt.load_state_dict(state['optimizer']);start=state['epoch']+1
    ld=loader(store,cfg['batch'],True,seed);ld.batch_sampler.epoch=start
    for ep in range(start,cfg['observer_epochs']):
        seed_all(seed+ep)
        bank.train();losses=[]
        for b in ld:
            b=batch_to(b,device);z=bank(b['x']);valid=b['eligible'].unsqueeze(-1)*z['active']
            if valid.sum()==0:continue
            target=b['y'].unsqueeze(-1).expand_as(z['logit'])
            loss=(nn.functional.binary_cross_entropy_with_logits(z['logit'],target,reduction='none')*valid).sum()/valid.sum()
            opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(bank.parameters(),1.);opt.step();losses.append(float(loss.detach()))
        atomic_torch(last,{'state':bank.state_dict(),'optimizer':opt.state_dict(),'epoch':ep})
        print('observer epoch',ep+1,'loss',np.mean(losses) if losses else np.nan,flush=True)
    atomic_torch(path,{'state':bank.state_dict(),'features':features,'seed':seed})
    return bank.eval().requires_grad_(False)

@torch.no_grad()
def predict(model,bank,store,batch,device,condition='normal',all_hours=False):
    """all_hours=True exports every observed hour (Eligible flag included) for trajectory scoring."""
    model.eval();bank.eval();parts=[];gate_sum=None;gate_n=0
    patient_categories=store.index.Patient_ID.astype(str).to_numpy()
    group_cat=pd.Categorical(store.index.Group_ID.astype(str));hospital_cat=pd.Categorical(store.index.Hospital_ID.astype(str))
    onsets=store.index.OnsetHour.to_numpy(dtype=np.float32)
    for b in loader(store,batch):
        b=batch_to(b,device)
        z=perturb_guidance(bank(b['x']),condition) if model.arm not in ['osta','cnn'] else None
        logits=model(b['x'],b['mask'],b['hours'],z)
        if not torch.isfinite(logits[b['mask'].bool()]).all():raise FloatingPointError('Nonfinite prediction')
        elig=b['eligible'].cpu().numpy().astype(bool).ravel()
        ok=b['mask'].cpu().numpy().astype(bool).ravel() if all_hours else elig
        code=np.repeat(b['idx'].cpu().numpy(),logits.size(1))[ok].astype(np.int32)
        # Compact numeric arrays avoid hundreds of thousands of small DataFrames
        # and repeated copies of patient/hospital identifier strings.
        parts.append({'code':code,'Hour':b['hours'].cpu().numpy().ravel()[ok],
            'y':b['y'].cpu().numpy().ravel()[ok].astype(np.int8),
            'logit':logits.cpu().numpy().ravel()[ok].astype(np.float32),'Eligible':elig[ok].astype(np.int8)})
        if model.last_gates is not None:
            eligible_tensor=b['eligible'].unsqueeze(-1);summed=(model.last_gates*eligible_tensor).sum((0,1)).cpu().numpy()
            gate_sum=summed if gate_sum is None else gate_sum+summed;gate_n+=float(eligible_tensor.sum())
    if not parts:raise ValueError('No eligible prediction hours')
    arrays={k:np.concatenate([part[k] for part in parts]) for k in parts[0]};del parts
    code=arrays.pop('code');d=pd.DataFrame(arrays)
    d['Patient_ID']=pd.Categorical.from_codes(code,patient_categories)
    d['Group_ID']=pd.Categorical.from_codes(group_cat.codes[code],group_cat.categories)
    d['Hospital_ID']=pd.Categorical.from_codes(hospital_cat.codes[code],hospital_cat.categories)
    d['OnsetHour']=onsets[code]
    if 'FirstAntibioticAroundOnset' in store.index:d['FirstAntibioticAroundOnset']=store.index.FirstAntibioticAroundOnset.to_numpy(dtype=np.float32)[code]
    return d,({g:float(v/max(gate_n,1)) for g,v in zip(bank.names,gate_sum)} if gate_sum is not None else {})

def train_arm(arm,train,val,bank,features,cfg,seed,path,device):
    seed_all(seed);model=ExperimentModel(features,arm,bank.names,small=cfg['small_model'],dropout=cfg['dropout']).to(device)
    path=Path(path);best_path=path/'best.pt';last_path=path/'last.pt';path.mkdir(parents=True,exist_ok=True)
    opt=torch.optim.AdamW(model.parameters(),lr=cfg['learning_rate'],weight_decay=1e-4)
    best=-1.;wait=0;start=0;history=[]
    if last_path.is_file():
        state=torch.load(last_path,map_location=device,weights_only=False);model.load_state_dict(state['model']);opt.load_state_dict(state['optimizer'])
        start=state['epoch']+1;best=state['best'];wait=state['wait'];history=state['history']
    ld=loader(train,cfg['batch'],True,seed);ld.batch_sampler.epoch=start
    for ep in range(start,cfg['epochs']):
        if wait>=cfg['patience']:break
        seed_all(seed+ep);model.train();bank.eval();loss_sum=0.;nb=0
        for b in ld:
            b=batch_to(b,device)
            with torch.no_grad():z=bank(b['x']) if arm not in ['osta','cnn'] else None
            logits=model(b['x'],b['mask'],b['hours'],z);valid=b['eligible']
            if valid.sum()==0:continue
            if cfg.get('loss','bce')=='osta_original' and arm in OSTA_FAMILY:
                core=model.last_core_output
                loss=osta_original_loss({'logits':logits,'organ_risks':core['organ_risks'],'organ_risk_weights':core['organ_risk_weights']},b['y'],valid)
            elif cfg.get('loss','bce') in ('bce','osta_original'):
                loss=(nn.functional.binary_cross_entropy_with_logits(logits,b['y'],reduction='none')*valid).sum()/valid.sum()
            else:raise ValueError('Unknown loss: '+str(cfg.get('loss')))
            if not torch.isfinite(loss):raise FloatingPointError(f'{arm}: nonfinite training loss')
            opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step();loss_sum+=float(loss.detach());nb+=1
        pred,_=predict(model,bank,val,cfg['batch'],device)
        score=average_precision_score(pred.y,pred.logit) if pred.y.nunique()==2 else float('nan')
        if not np.isfinite(score):raise ValueError('Validation target has fewer than two classes')
        if score>best:
            best=score;wait=0;atomic_torch(best_path,{'state':model.state_dict(),'epoch':ep,'val_AUPRC':best})
        else:wait+=1
        history.append({'epoch':ep+1,'loss':loss_sum/max(nb,1),'val_hourly_AUPRC':score})
        atomic_torch(last_path,{'model':model.state_dict(),'optimizer':opt.state_dict(),'epoch':ep,'best':best,'wait':wait,'history':history})
        print(arm,'epoch',ep+1,'loss',round(loss_sum/max(nb,1),5),'validation AUPRC',round(score,5),flush=True)
    model.load_state_dict(torch.load(best_path,map_location=device,weights_only=False)['state'])
    atomic_json(path/'training_history.json',history);return model.eval()

def calibrate(cal):
    if cal.y.nunique()!=2:raise ValueError('Calibration set requires both classes')
    # Fit on an independent development partition, never on external test labels.
    sample=cal.sample(min(len(cal),250000),random_state=42)
    fit=LogisticRegression(C=1e6,solver='lbfgs',max_iter=1000).fit(sample[['logit']],sample.y)
    slope=float(fit.coef_[0,0])
    if slope>0:return {'intercept':float(fit.intercept_[0]),'slope':slope}
    # A non-positive Platt slope would REVERSE the model's ranking on every later dataset (seen on a small
    # eICU calibration split). Calibration must be monotone increasing, so keep the ranking and
    # recalibrate the intercept only (slope fixed at 1). The fitted slope is recorded for reporting.
    from scipy.optimize import minimize_scalar
    z=sample.logit.to_numpy(dtype=float);y=sample.y.to_numpy(dtype=float)
    def loss(b):
        s=np.clip(b+z,-30,30);return float(np.mean(np.logaddexp(0,s)-y*s))
    b=float(minimize_scalar(loss,bounds=(-30,30),method='bounded').x)
    return {'intercept':b,'slope':1.0,'fallback':'intercept_only_nonpositive_platt_slope','fitted_slope':slope}

def apply_calibration(d,params):
    d=d.copy();x=np.clip(params['intercept']+params['slope']*d.logit.to_numpy(),-30,30);d['risk']=(1/(1+np.exp(-x))).astype(np.float32);return d

def alarm_records(d,threshold,cooldown=6,horizon=6):
    rows=[]
    for pid,g in d.groupby('Patient_ID',sort=False,observed=True):
        g=g.sort_values('Hour');onset=g.OnsetHour.iloc[0];last=-np.inf;false=0;leads=[];total=0
        for h,p in zip(g.Hour,g.risk):
            if p>=threshold and h-last>=cooldown:
                last=h;total+=1
                if pd.notna(onset) and 0<onset-h<=horizon:leads.append(onset-h)
                else:false+=1
        evaluable=bool((g.y==1).any())
        rows.append({'Patient_ID':pid,'Group_ID':g.Group_ID.iloc[0],'event_evaluable':evaluable,'detected':bool(leads),
          'warning_hours':max(leads) if leads else np.nan,'false_alarms':false,'alarms':total,'at_risk_hours':len(g)})
    return pd.DataFrame(rows)

def select_threshold(cal,cfg):
    candidates=np.unique(np.r_[1.0000001,np.quantile(cal.risk,np.linspace(0,1,101))]);records=[]
    for threshold in candidates:
        a=alarm_records(cal,float(threshold),cfg['alarm_cooldown'],cfg['horizon'])
        burden=a.false_alarms.sum()/a.at_risk_hours.sum()*24
        ev=a[a.event_evaluable];sens=ev.detected.mean() if len(ev) else np.nan
        records.append({'threshold':float(threshold),'false_alarms_per_day':float(burden),'event_sensitivity':float(sens)})
    ok=[r for r in records if r['false_alarms_per_day']<=cfg['false_alarm_budget']]
    best=max(ok,key=lambda r:(r['event_sensitivity'] if np.isfinite(r['event_sensitivity']) else -1,r['threshold']))
    return best,records

def evaluate(d,threshold,cfg):
    y=d.y.to_numpy();p=d.risk.to_numpy();two=len(np.unique(y))==2
    a=alarm_records(d,threshold,cfg['alarm_cooldown'],cfg['horizon']);ev=a[a.event_evaluable]
    out={'hourly_AUPRC':float(average_precision_score(y,p)) if two else np.nan,
      'hourly_AUROC':float(roc_auc_score(y,p)) if two else np.nan,'hourly_Brier':float(np.mean((p-y)**2)),
      'eligible_hours':len(d),'stays':d.Patient_ID.nunique(),'positive_hours':int(y.sum()),'prevalence':float(y.mean()),'alarm_PPV':float((a.alarms-a.false_alarms).sum()/a.alarms.sum()) if a.alarms.sum() else np.nan,'threshold':float(threshold),
      'event_evaluable_stays':len(ev),'event_sensitivity':float(ev.detected.mean()) if len(ev) else np.nan,
      'missed_events':int((~ev.detected).sum()),'false_alarms_per_patient_day':float(a.false_alarms.sum()/a.at_risk_hours.sum()*24),
      'detected_event_denominator':int(ev.detected.sum()),'warning_hours_q25':float(ev.warning_hours.quantile(.25)) if ev.warning_hours.notna().any() else np.nan,'warning_hours_q75':float(ev.warning_hours.quantile(.75)) if ev.warning_hours.notna().any() else np.nan,'median_warning_hours_detected':float(ev.warning_hours.median()) if ev.warning_hours.notna().any() else np.nan}
    bins=pd.cut(d.risk,np.linspace(0,1,11),include_lowest=True)
    points=d.groupby(bins,observed=True).agg(mean_risk=('risk','mean'),event_fraction=('y','mean'),n=('y','size')).reset_index(drop=True)
    out['ECE_10bin']=float(((points.mean_risk-points.event_fraction).abs()*points.n).sum()/len(d))
    # Diagnostic slope/intercept only; this fit never modifies external predictions.
    if two:
        try:
            diagnostic=LogisticRegression(C=1e6,max_iter=1000).fit(np.log(np.clip(p,1e-6,1-1e-6)/(1-np.clip(p,1e-6,1-1e-6))).reshape(-1,1),y)
            out['calibration_intercept']=float(diagnostic.intercept_[0]);out['calibration_slope']=float(diagnostic.coef_[0,0])
        except Exception:out['calibration_intercept']=out['calibration_slope']=np.nan
    return out,a,points

def ap_plan(y,p):
    order=np.argsort(-np.asarray(p),kind='stable');ys=np.asarray(y)[order]
    ps=np.asarray(p)[order];ends=np.r_[np.flatnonzero(np.diff(ps)),len(ps)-1]
    def weighted_ap(weights):
        w=weights[order];tp=np.cumsum(w*ys,dtype=float)[ends];fp=np.cumsum(w*(1-ys),dtype=float)[ends]
        total=tp[-1]
        if total<=0:return np.nan
        return float(np.sum(np.diff(np.r_[0.,tp])/total*np.divide(tp,tp+fp,out=np.zeros_like(tp),where=tp+fp>0)))
    return weighted_ap

def clustered_ci(d,n_boot=200,seed=42):
    # Sample patient clusters; multiplicities become weights on their hourly observations.
    idx,groups=pd.factorize(d.Group_ID,sort=True);rng=np.random.default_rng(seed);vals=[]
    if len(groups)<10:return {}
    y=d.y.to_numpy();p=d.risk.to_numpy();weighted_ap=ap_plan(y,p)
    for _ in range(n_boot):
        counts=rng.multinomial(len(groups),np.repeat(1/len(groups),len(groups)));w=counts[idx]
        if w[y==1].sum()==0 or w[y==0].sum()==0:continue
        vals.append([weighted_ap(w),np.average((p-y)**2,weights=w)])
    if not vals:return {}
    ci=np.quantile(vals,[.025,.975],axis=0)
    return {'AUPRC_CI_low':float(ci[0,0]),'AUPRC_CI_high':float(ci[1,0]),'Brier_CI_low':float(ci[0,1]),'Brier_CI_high':float(ci[1,1])}

def paired_difference(a,b,n_boot=200,seed=42):
    # Both models must predict exactly the same at-risk patient-hours.
    z=a[['Patient_ID','Hour','Group_ID','y','risk']].merge(b[['Patient_ID','Hour','y','risk']],on=['Patient_ID','Hour'],suffixes=('_a','_b'),validate='one_to_one')
    assert len(z)==len(a)==len(b) and np.array_equal(z.y_a,z.y_b)
    ix,groups=pd.factorize(z.Group_ID,sort=True);rng=np.random.default_rng(seed);v=[]
    ap_a=ap_plan(z.y_a,z.risk_a);ap_b=ap_plan(z.y_b,z.risk_b)
    for _ in range(n_boot):
        w=rng.multinomial(len(groups),np.repeat(1/len(groups),len(groups)))[ix]
        if w[z.y_a.eq(1)].sum()==0 or w[z.y_a.eq(0)].sum()==0:continue
        v.append(ap_a(w)-ap_b(w))
    point=average_precision_score(z.y_a,z.risk_a)-average_precision_score(z.y_b,z.risk_b)
    ci=np.quantile(v,[.025,.975]) if v else [np.nan,np.nan]
    return {'AUPRC_difference':float(point),'CI_low':float(ci[0]),'CI_high':float(ci[1])}

def run_fold(index,features,heldout,cfg,root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    mf=grouped_manifest(index,heldout,cfg['split_seed']);mf.to_parquet(root/'manifest.parquet',index=False)
    fit=SequenceStore(mf[mf.split.isin(['train','observer_fit'])],features,max_hours=cfg['max_hours'])
    norm=fit_normalizer(fit);del fit;np.savez(root/'normalization.npz',**norm)
    stores={sp:SequenceStore(mf[mf.split.eq(sp)],features,norm,cfg['max_hours']) for sp in ['observer_fit','train','val','calib','test']}
    main_membership=mf[mf.split.eq('train')]
    if cfg.get('baseline_full_development',False):
        assert set(cfg['arms'])<=set(['osta','cnn'])
        main_membership=mf[mf.split.isin(['train','observer_fit'])]
        stores['train']=SequenceStore(main_membership,features,norm,cfg['max_hours'])
    main_membership[['Patient_ID','Group_ID','split']].to_parquet(root/'main_training_membership.parquet',index=False)
    atomic_json(root/'feature_schema.json',features)
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu');results=[]
    for seed in cfg['seeds']:
        seed_dir=root/f'seed_{seed}';seed_dir.mkdir(exist_ok=True)
        if any(a not in ['osta','cnn'] for a in cfg['arms']):
            bank=train_observers(stores['observer_fit'],features,cfg,seed,seed_dir/'observers.pt',device)
        else:
            bank=ObserverBank(features,hidden=cfg.get('observer_hidden',32)).to(device).eval().requires_grad_(False)
        for arm in cfg['arms']:
            path=seed_dir/arm;path.mkdir(exist_ok=True);done=path/'completed.json'
            if done.is_file():results.extend(json.loads(done.read_text()));print('Reuse completed',heldout,seed,arm);continue
            model=train_arm(arm,stores['train'],stores['val'],bank,features,cfg,seed,path,device)
            cal,_=predict(model,bank,stores['calib'],cfg['batch'],device)
            params=calibrate(cal);cal=apply_calibration(cal,params);chosen,sweep=select_threshold(cal,cfg)
            atomic_json(path/'calibration_and_threshold.json',{'platt':params,'chosen':chosen,'budget':cfg['false_alarm_budget']})
            pd.DataFrame(sweep).to_csv(path/'threshold_sweep.csv',index=False)
            conditions=['normal']+(cfg['stress_conditions'] if arm not in ['osta','cnn'] else [])
            records=[]
            for condition in conditions:
                test,gates=predict(model,bank,stores['test'],cfg['batch'],device,condition)
                test=apply_calibration(test,params);metrics,alarms,points=evaluate(test,chosen['threshold'],cfg)
                if condition=='normal':metrics.update(clustered_ci(test,cfg['bootstrap'],seed))
                row={'heldout':heldout,'seed':seed,'arm':arm,'condition':condition,'parameters':sum(p.numel() for p in model.parameters()),
                     'observer_parameters':sum(p.numel() for p in bank.parameters()) if arm not in ['osta','cnn'] else 0,**metrics}
                records.append(row);results.append(row)
                test.to_parquet(path/f'predictions_{condition}.parquet',index=False)
                alarms.to_parquet(path/f'alarms_{condition}.parquet',index=False)
                points.to_csv(path/f'calibration_{condition}.csv',index=False)
                atomic_json(path/f'gates_{condition}.json',gates)
                print(heldout,seed,arm,condition,'AUPRC',round(metrics['hourly_AUPRC'],4),'sensitivity',round(metrics['event_sensitivity'],4),'false alarms/day',round(metrics['false_alarms_per_patient_day'],4),flush=True)
            atomic_json(done,records);del model;gc.collect()
            if torch.cuda.is_available():torch.cuda.empty_cache()
        # Paired method comparisons, no selection on these external results.
        comparisons=[]
        for control in ['osta','observer_features','output_fusion']:
            p=seed_dir/'gated_attention'/'predictions_normal.parquet';c=seed_dir/control/'predictions_normal.parquet'
            if p.is_file() and c.is_file():
                comparisons.append({'heldout':heldout,'seed':seed,'comparison':'gated_attention minus '+control,**paired_difference(pd.read_parquet(p),pd.read_parquet(c),cfg['bootstrap'],seed)})
        pd.DataFrame(comparisons).to_csv(seed_dir/'paired_comparisons.csv',index=False)
        del bank
    pd.DataFrame(results).to_csv(root/'results.csv',index=False)
    return pd.DataFrame(results)
