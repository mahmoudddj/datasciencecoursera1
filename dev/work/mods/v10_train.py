"""Common v10 experiment driver with protected patients and all eight arms."""
from pathlib import Path
import json,os,gc,pickle
import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from v9_train import (SequenceStore,fit_normalizer,train_arm,train_observers,predict,
    calibrate,apply_calibration,select_threshold,evaluate,clustered_ci,paired_difference,
    atomic_json,seed_all)
from v9_models import ObserverBank
from v9_data import signature,sha
from v10_protocol import partition

BASELINES=['osta','cnn','logistic','boosted_tree']

def tabular_arrays(store,budget):
    n=sum(int(store.frame(i).Eligible.sum()) for i in range(len(store)))
    # Conservative budget for dense matrix plus estimator copies.
    need=n*(len(store.features)*4+24)*4
    if need>budget:raise MemoryError(f'Tabular fit needs approximately {need/1024**3:.1f} GB; configured cap {budget/1024**3:.1f} GB. Use a higher-RAM runtime or prespecify a common smaller development cohort for ALL arms.')
    x=np.empty((n,len(store.features)),np.float32);y=np.empty(n,np.int8);j=0
    for i in range(len(store)):
        b=store[i];ok=b['eligible'].astype(bool);k=int(ok.sum());x[j:j+k]=b['x'][ok];y[j:j+k]=b['y'][ok];j+=k
    return x,y

def tabular_predict(model,store):
    parts=[]
    for i in range(len(store)):
        b=store[i];ok=b['eligible'].astype(bool);row=store.index.iloc[i]
        if not ok.any():continue
        p=np.clip(model.predict_proba(b['x'][ok])[:,1],1e-7,1-1e-7)
        parts.append(pd.DataFrame({'Patient_ID':row.Patient_ID,'Group_ID':row.Group_ID,
          'Hospital_ID':row.Hospital_ID,'OnsetHour':row.OnsetHour,'Hour':b['hours'][ok],
          'y':b['y'][ok],'logit':np.log(p/(1-p))}))
    return pd.concat(parts,ignore_index=True)

def fit_tabular(arm,store,cfg,seed,path):
    p=path/'estimator.pkl'
    if p.is_file():
        with p.open('rb') as f:return pickle.load(f) # own locally written checkpoint only
    x,y=tabular_arrays(store,cfg['tabular_max_bytes'])
    model=(LogisticRegression(C=1.,solver='lbfgs',max_iter=1000,random_state=seed)
      if arm=='logistic' else HistGradientBoostingClassifier(max_iter=cfg['tree_iterations'],
          max_leaf_nodes=31,l2_regularization=1.,learning_rate=.05,early_stopping=False,random_state=seed))
    model.fit(x,y);tmp=p.with_suffix('.partial.pkl')
    with tmp.open('wb') as f:pickle.dump(model,f)
    os.replace(tmp,p);return model

def hospital_ci(d,n_boot=200,seed=42):
    # Hospitals outermost; all repeats of a patient stay together within their hospital.
    # If patients cross hospitals, do not pretend hospitals are independent clusters.
    if d.groupby('Group_ID',observed=True).Hospital_ID.nunique().max()>1:return {'hospital_CI_status':'cross_hospital_patients_not_nested'}
    if d.Hospital_ID.nunique()<5:return {'hospital_CI_status':'fewer_than_5_hospitals'}
    q=d.copy();q['Group_ID']=q.Hospital_ID
    out=clustered_ci(q,n_boot,seed)
    return {'hospital_CI_status':'hospital_cluster_bootstrap',**{'hospital_'+k:v for k,v in out.items()}}

def run_fold(index,features,target,cfg,root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    mf=partition(index,target,cfg)
    # Bind to content hashes, not merely shard paths. Configuration/schema/code changes
    # cannot silently load an old model even when a caller reuses a run directory.
    contract={'config':cfg,'features':features,'membership':mf[['Patient_ID','Group_ID','split']].to_dict('list'),
      'shards':{f:sha(f) for f in sorted(mf.file.unique())},
      'modules':{p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}}
    key=signature(contract);marker=root/'contract.json'
    if marker.exists() and json.loads(marker.read_text())['sha256']!=key:
        raise ValueError('Run directory contract changed. Select a new RUN_KEY; old results are retained.')
    atomic_json(marker,{'sha256':key,'contract':contract})
    mf.to_parquet(root/'manifest.parquet',index=False)
    fit=SequenceStore(mf[mf.split.isin(['train','observer_fit'])],features,max_hours=cfg['max_hours'])
    norm=fit_normalizer(fit);np.savez(root/'normalization.npz',**norm);del fit
    stores={s:SequenceStore(mf[mf.split.eq(s)],features,norm,cfg['max_hours']) for s in ['train','observer_fit','val','calib','test']}
    if cfg.get('baseline_full_development'):
        if not set(cfg['arms'])<=set(BASELINES):raise ValueError('80% baseline cannot train observers on overlapping labels')
        stores['train']=SequenceStore(mf[mf.split.isin(['train','observer_fit'])],features,norm,cfg['max_hours'])
    stores['train'].index[['Patient_ID','Group_ID','split']].to_parquet(root/'main_training_membership.parquet',index=False)
    atomic_json(root/'feature_schema.json',features)
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu');results=[]
    for seed in cfg['seeds']:
        sd=root/f'seed_{seed}';sd.mkdir(exist_ok=True)
        seed_all(seed)
        bank=(train_observers(stores['observer_fit'],features,cfg,seed,sd/'observers.pt',device)
            if any(a not in BASELINES for a in cfg['arms'])
            else ObserverBank(features,hidden=cfg['observer_hidden']).to(device).eval().requires_grad_(False))
        for arm in cfg['arms']:
            path=sd/arm;path.mkdir(exist_ok=True);done=path/'completed.json'
            if done.is_file():results+=json.loads(done.read_text());print('Reuse',target,arm);continue
            tab=arm in ['logistic','boosted_tree']
            model=fit_tabular(arm,stores['train'],cfg,seed,path) if tab else train_arm(arm,stores['train'],stores['val'],bank,features,cfg,seed,path,device)
            def pred(store,condition='normal'):
                return (tabular_predict(model,store),{}) if tab else predict(model,bank,store,cfg['batch'],device,condition)
            cal,_=pred(stores['calib']);params=calibrate(cal);cal=apply_calibration(cal,params)
            chosen,sweep=select_threshold(cal,cfg)
            atomic_json(path/'calibration_and_threshold.json',{'platt':params,'chosen':chosen})
            pd.DataFrame(sweep).to_csv(path/'threshold_sweep.csv',index=False)
            records=[]
            for condition in ['normal']+(cfg['stress_conditions'] if arm not in BASELINES else []):
                d,gates=pred(stores['test'],condition);d=apply_calibration(d,params)
                m,alarms,points=evaluate(d,chosen['threshold'],cfg)
                if condition=='normal':m.update(clustered_ci(d,cfg['bootstrap'],seed));m.update(hospital_ci(d,cfg['bootstrap'],seed))
                row={'target':target,'seed':seed,'arm':arm,'condition':condition,'scope':mf.evaluation_scope.iloc[0],
                  'feature_count':len(features),'main_training_stays':len(stores['train']),
                  'observer_fit_stays':len(stores['observer_fit']) if arm not in BASELINES else 0,**m}
                records.append(row);results.append(row)
                d.to_parquet(path/f'predictions_{condition}.parquet',index=False)
                alarms.to_parquet(path/f'alarms_{condition}.parquet',index=False)
                points.to_csv(path/f'calibration_{condition}.csv',index=False)
                atomic_json(path/f'gates_{condition}.json',gates)
            atomic_json(done,records);del model;gc.collect()
            if torch.cuda.is_available():torch.cuda.empty_cache()
            print('Completed',target,arm,'(smoke scores are not clinical evidence)' if cfg['mode']=='smoke' else '')
        comparisons=[]
        p=sd/'gated_attention/predictions_normal.parquet'
        for arm in ['osta','observer_features','output_fusion','ungated_attention','cnn','logistic','boosted_tree']:
            q=sd/arm/'predictions_normal.parquet'
            if p.exists() and q.exists():comparisons.append({'comparison':'gated_attention minus '+arm,**paired_difference(pd.read_parquet(p),pd.read_parquet(q),cfg['bootstrap'],seed)})
        pd.DataFrame(comparisons).to_csv(sd/'paired_comparisons.csv',index=False)
    out=pd.DataFrame(results);out.to_csv(root/'results.csv',index=False);return out
