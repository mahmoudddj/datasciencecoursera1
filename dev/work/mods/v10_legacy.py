"""Legacy PhysioNet-model validation: frozen historical bundles or a labelled source reproduction.

Original model classes, BatchNorm, feature generation and normalisation are executed from
the supplied archive (AST extraction of named definitions only; the old top-level training
scripts are never run). Nothing is fitted, calibrated or thresholded on target data.

Bundle format 'legacy-bundle-v2' (manifest.json):
  arm, provenance, base_features, feature_order, model_kwargs, max_hours,
  source_representation ('sparse_hourly' | 'patient_forward_filled'), source_units,
  members [{file, sha256, format}], ensemble {combine, weights|coef/intercept},
  normalization (normalization.npz, normalizer_sha256), threshold (on the raw ensemble
  probability), policy == threshold_selection_policy, calibration (source-only Platt used
  only for the reported 'risk'; identity for historical models), source_sha256.
"""
from pathlib import Path
from functools import lru_cache
import ast,types,math,time,contextlib,io,json,os,shutil
import numpy as np
import pandas as pd
import torch
from torch import nn
import torch.nn.functional as F
from torch.utils.data import Dataset
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score,average_precision_score
from v9_train import atomic_json,atomic_torch,seed_all,calibrate,apply_calibration
from v9_data import sha,signature
from v10_evaluation import normalized_utility,challenge_event_metrics,alarm_policy

BUNDLE_FORMAT='legacy-bundle-v2'
CLINICAL=['HR','O2Sat','Temp','SBP','MAP','DBP','Resp','EtCO2','BaseExcess','HCO3','FiO2','pH','PaCO2','SaO2','AST','BUN','Alkalinephos','Calcium','Chloride','Creatinine','Bilirubin_direct','Glucose','Lactate','Magnesium','Phosphate','Potassium','Bilirubin_total','TroponinI','Hct','Hgb','PTT','WBC','Fibrinogen','Platelets']
SOURCE_FEATURES=CLINICAL+['Age','Gender','Unit1','Unit2','HospAdmTime','ICULOS']
# Channels the MIMIC-IV/eICU adapter cannot supply. They stay missing (never surrogates:
# TroponinT is not TroponinI, PaO2 is not SaO2). Reported in every result row.
TARGET_UNSUPPORTED=['EtCO2','SaO2','TroponinI','Hct','Unit1','Unit2']
# Exactly the original scripts' exclusion list (OSTA main() and Paper1 __main__).
ORIGINAL_EXCLUDED=['Unnamed: 0','...1','datetime','ICULOS','Unit1','Unit2','Apache_II_Score','SOFA_Score','SIRS',
                   'Incomplete_qSOFA_Score','NEWS_Score','Shock_Index','BUN_Creatinine_Ratio','Bilirubin_Creatinine_Ratio']
DEFAULT_BASE=['HR','O2Sat','Temp','SBP','MAP','DBP','Resp','Creatinine','BUN','Platelets','Bilirubin_total','WBC','Age','Gender']
ORIGINAL_KWARGS={'osta':{'d_organ':64,'d_global':256,'n_heads_organ':4,'n_heads_inter':4,'n_layers_organ':2,'n_layers_global':2,'dropout':.15,'mc_samples':30},
                 'cnn':{'d_model':256,'n_heads':8,'num_layers':4,'dim_feedforward':512,'dropout':.2,'use_cnn':True,'use_continuous_time':True}}
SMOKE_KWARGS={'osta':{'d_organ':16,'d_global':32,'n_heads_organ':4,'n_heads_inter':4,'n_layers_organ':1,'n_layers_global':1,'dropout':.15,'mc_samples':1},
              'cnn':{'d_model':32,'n_heads':4,'num_layers':1,'dim_feedforward':64,'dropout':.2,'use_cnn':True,'use_continuous_time':True}}
# Original recipe constants (OSTA v5 main / Paper1 run_enhanced_sepsis_prediction).
ORIGINAL_RECIPE={'osta':{'epochs':50,'patience':10,'batch':256,'lr':5e-4,'weight_decay':1e-4,'seeds':[42,7,123]},
                 'cnn':{'epochs':30,'patience':7,'batch':256,'lr':5e-4,'weight_decay':1e-4,'seeds':[42]}}
THRESHOLD_GRID=np.arange(0.05,0.951,0.01)   # original validation utility sweep grid
HOURLY_POLICY={'persistence':1,'min_rise':0.,'latch':False}
FRESH_TOLERANCE_HOURS=1e-3

def source_file(arm):return Path(__file__).parent/('legacy_osta_original.py' if arm=='osta' else 'legacy_cnn_original.py')

@lru_cache(None)
def definitions(arm):
    path=source_file(arm);tree=ast.parse(path.read_text())
    common={'engineer_temporal_features','EnhancedSepsisPreprocessor','ContinuousTimeEncoding','_causal_attn_mask','compute_prediction_utility','compute_normalized_utility'}
    names=common|({'build_feature_to_organ_mapping','OrganEncoder','InterOrganAttention','OSTATransformer','osta_loss'} if arm=='osta'
                  else {'FixedPositionalEncoding','CausalCNNBlock','MultiScaleTemporalCNN','EnhancedSepsisTransformer','improved_sepsis_loss'})
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
    if arm=='osta':nodes=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ORGAN_SYSTEM_FEATURES' for t in n.targets)]+nodes
    env=dict(np=np,pd=pd,torch=torch,nn=nn,F=F,math=math,time=time,Dataset=Dataset,os=os)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),env)
    missing=names-set(env)
    if missing:raise RuntimeError('Original definitions not found: '+str(sorted(missing)))
    return types.SimpleNamespace(**env)

def architecture(arm,features,kwargs):
    m=definitions(arm)
    with contextlib.redirect_stdout(io.StringIO()):
        return m.OSTATransformer(features,**kwargs) if arm=='osta' else m.EnhancedSepsisTransformer(len(features),**kwargs)

def feature_names(arm,base):
    """Exact original feature order for a base schema (engineered + missingness)."""
    h=np.arange(1,4,dtype=float);d=pd.DataFrame({'Patient_ID':'x','Hour':h,'SepsisLabel':0})
    for f in base:d[f]=1.
    return raw_arrays(d,{'arm':arm,'base_features':list(base),'max_hours':4})[4]

def original_feature_rule(columns):
    return [c for c in columns if c not in ['Patient_ID','SepsisLabel','Hour']+ORIGINAL_EXCLUDED]

def raw_arrays(frame,meta):
    """Original engineer_temporal_features + EnhancedSepsisPreprocessor on ONE contiguous stay."""
    arm=meta['arm'];base=list(meta['base_features']);m=definitions(arm)
    if not set(base)<=set(frame):raise ValueError('Input lacks source schema columns: '+str(sorted(set(base)-set(frame))))
    z=frame[['Patient_ID','Hour','SepsisLabel']+base].sort_values(['Patient_ID','Hour']).copy()
    if z.Patient_ID.nunique()!=1 or z.duplicated(['Patient_ID','Hour']).any() or (np.diff(z.Hour)!=1).any():raise ValueError('Legacy adapter requires one contiguous hourly stay')
    with contextlib.redirect_stdout(io.StringIO()):
        eng,new=m.engineer_temporal_features(z,base)
        pre=m.EnhancedSepsisPreprocessor(eng,base+new,max_hours=meta['max_hours'],use_missingness=True)
        arrays=pre.prepare_sequences()
    names=base+new+[f'{c}_missing' for c in pre.miss_cols]
    if meta.get('feature_order') and names!=list(meta['feature_order']):raise ValueError('Original feature order mismatch; cannot guess source preprocessing')
    x,y,mask,_,_,hours=arrays[:6]
    return x[0].astype(np.float32),y[0].astype(np.float32),mask[0].astype(np.float32),hours[0].astype(np.float32),names

def original_normalize(x,norm):
    """EnhancedSepsisPreprocessor.normalize, byte-for-byte semantics (inf->0 before scaling)."""
    x=np.nan_to_num(np.asarray(x,dtype=np.float64),nan=0.,posinf=0.,neginf=0.)
    z=(x-norm['mean'])/norm['std']
    return np.nan_to_num(z,nan=0.,posinf=3.,neginf=-3.).astype(np.float32)

def _logits(model,x,mask,h,device='cpu'):
    with torch.no_grad():
        z=model(torch.tensor(x,device=device),torch.tensor(mask,device=device),hours=torch.tensor(h,device=device))
        return (z['logits'] if isinstance(z,dict) else z).float().cpu().numpy()

def combine(probs,ensemble):
    """probs: (members, T) raw probabilities -> ensemble probability (original rules)."""
    probs=np.asarray(probs,float)
    if ensemble['combine']=='mean_probability':
        w=np.asarray(ensemble.get('weights') or np.ones(len(probs)),float);return np.average(probs,axis=0,weights=w/w.sum())
    if ensemble['combine']=='stack_logit':
        p=np.clip(probs,1e-6,1-1e-6);x=np.log(p/(1-p));s=np.dot(np.asarray(ensemble['coef'],float),x)+float(ensemble['intercept'])
        return 1/(1+np.exp(-s))
    raise ValueError('Unknown ensemble rule')

def predict_frame(models,frame,meta,norm,device='cpu'):
    """Frozen inference: per-member sigmoid -> ensemble probability ('score') -> reported risk."""
    if not isinstance(models,(list,tuple)):models=[models]
    x,y,mask,h,names=raw_arrays(frame,meta)
    xn=original_normalize(x,norm)[None];keep=mask.astype(bool)
    probs=[1/(1+np.exp(-_logits(mo,xn,mask[None],h[None],device)[0][keep].astype(float))) for mo in models]
    score=combine(probs,meta.get('ensemble',{'combine':'mean_probability'}))
    out=frame.sort_values('Hour').iloc[:int(keep.sum())][['Patient_ID','Hour','SepsisLabel']].rename(columns={'SepsisLabel':'StepLabel'}).copy()
    out['score']=score.astype(np.float32);p=np.clip(score,1e-7,1-1e-7);out['logit']=np.log(p/(1-p))
    return apply_calibration(out,meta['calibration'])

# ---------------------------------------------------------------------------
# Bundles
# ---------------------------------------------------------------------------
def _torch_load(path):
    try:return torch.load(path,map_location='cpu',weights_only=True)
    except Exception:
        allowed=[]
        for mod in ['numpy._core.multiarray','numpy.core.multiarray']:
            try:allowed.append(__import__(mod,fromlist=['scalar']).scalar)
            except Exception:pass
        allowed+= [np.dtype]+[type(np.dtype(t)) for t in ['float64','float32','int64']]
        with torch.serialization.safe_globals(allowed):
            return torch.load(path,map_location='cpu',weights_only=True)

def _state(obj):
    if isinstance(obj,dict) and 'model_state_dict' in obj:return obj['model_state_dict']
    return obj

def load_bundle(root,arm,mode='smoke'):
    root=Path(root);p=root/'manifest.json'
    if not p.exists():raise FileNotFoundError(f'{arm}: missing {p}. Provide a complete bundle (or import original outputs) before target extraction.')
    m=json.loads(p.read_text())
    required={'bundle_format','arm','provenance','base_features','feature_order','model_kwargs','max_hours','calibration','threshold',
              'policy','threshold_selection_policy','members','ensemble','normalizer_sha256','source_sha256','source_representation'}
    if not required<=m.keys() or m['arm']!=arm or m['bundle_format']!=BUNDLE_FORMAT:
        raise ValueError(f'{arm}: incomplete or outdated bundle manifest; missing {sorted(required-set(m))}')
    if m['source_sha256']!=sha(source_file(arm)):raise ValueError('Checkpoint source differs from supplied archive; adapt explicitly')
    if m['policy']!=m['threshold_selection_policy']:raise ValueError('Alarm policy differs from the policy used to select the source threshold; refusing.')
    if m['source_representation'] not in ['sparse_hourly','patient_forward_filled']:raise ValueError('Undeclared source representation')
    if 'FiO2' in m['base_features'] and m.get('source_units',{}).get('FiO2') not in ['percent','fraction']:
        raise ValueError('Historical FiO2 needs an explicit source_units declaration: percent or fraction')
    unknown=[f for f in m['base_features'] if f not in SOURCE_FEATURES]
    if unknown:raise ValueError('Base features without a validated target adapter: '+str(unknown))
    if mode=='full' and m['provenance'] not in ['verified_historical','physionet_source_reproduction_full']:
        raise ValueError('Full external evaluation cannot load a synthetic or smoke-source checkpoint')
    if sha(root/'normalization.npz')!=m['normalizer_sha256']:raise ValueError('Source bundle hash mismatch: normalization.npz')
    n=dict(np.load(root/'normalization.npz',allow_pickle=False))
    if len(n['mean'])!=len(m['feature_order']) or n['mean'].shape!=n['std'].shape or not np.isfinite(n['mean']).all() or not np.isfinite(n['std']).all() or (n['std']<=0).any():raise ValueError('Invalid frozen scaler')
    if feature_names(arm,m['base_features'])!=list(m['feature_order']):raise ValueError('Feature order does not follow the original generator')
    models=[]
    for member in m['members']:
        f=Path(member['file']);f=f if f.is_absolute() else root/f
        if sha(f)!=member['sha256']:raise ValueError('Source bundle hash mismatch: '+str(f))
        obj=_torch_load(f)
        if isinstance(obj,dict) and 'feature_cols' in obj:
            expected=m['feature_order'] if arm=='osta' else m['base_features']
            if list(obj['feature_cols'])!=list(expected):raise ValueError('Checkpoint feature_cols differ from manifest')
            if obj.get('checkpoint_format')!='causal-v1':raise ValueError('Original checkpoint predates causal-v1')
        model=architecture(arm,m['feature_order'],m['model_kwargs'])
        model.load_state_dict(_state(obj),strict=True);model.eval();models.append(model)
    if m['ensemble']['combine']=='mean_probability' and m['ensemble'].get('weights') and len(m['ensemble']['weights'])!=len(models):raise ValueError('Ensemble weights/member mismatch')
    return models,m,n

def detect_representation(frames,features):
    """Evidence for how the SOURCE stored repeated values: within-stay missingness after the
    first observation (sparse PSV ~ high; patient-forward-filled CSV ~ 0) and leading gaps."""
    after=total=lead=lead_total=0
    for g in frames:
        for f in [c for c in features if c in g and c in CLINICAL]:
            v=g[f].to_numpy(float);ok=np.isfinite(v)
            if not ok.any():continue
            first=int(np.argmax(ok));after+=int((~ok[first:]).sum());total+=len(v)-first
            lead+=first;lead_total+=1
    frac=after/total if total else np.nan
    rep='patient_forward_filled' if frac<0.01 else 'sparse_hourly' if frac>0.2 else 'ambiguous'
    return rep,{'post_first_missing_fraction':frac,'mean_leading_missing_hours':lead/max(lead_total,1)}

def detect_units(frames):
    v=pd.concat([g['FiO2'] for g in frames if 'FiO2' in g]).dropna() if any('FiO2' in g for g in frames) else pd.Series(dtype=float)
    if v.empty:return {}
    med=float(v.median())
    if med<=1.5:return {'FiO2':'fraction'}
    if med>=15:return {'FiO2':'percent'}
    raise ValueError('FiO2 source units are ambiguous; declare them explicitly')

def import_original_outputs(arm,output_dir,dest,representation,source_units=None,ensemble=None,seeds=None,mode='smoke'):
    """Package the ORIGINAL scripts' saved outputs into a frozen bundle without retraining.
    OSTA: v5_seed{s}_model.pt (+ v5_preprocessed_cache.npz scaler, v5_validation_utility_sweep.csv).
    CNN : sepsis_enhanced_transformer.pt (+ preprocessed_data_cache_paper1.npz, paper1_validation_utility_sweep.csv).
    Threshold = first maximum of the saved validation utility sweep (original rule, per-hour policy).
    """
    out=Path(output_dir);dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    if representation not in ['sparse_hourly','patient_forward_filled']:raise ValueError('Declare how the source CSV stored repeated values (see detect_representation)')
    if arm=='osta':
        seeds=seeds or ORIGINAL_RECIPE['osta']['seeds'];files=[out/f'v5_seed{s}_model.pt' for s in seeds]
        cache=out/'v5_preprocessed_cache.npz';sweep=out/'v5_validation_utility_sweep.csv'
    else:
        files=[out/'sepsis_enhanced_transformer.pt'];cache=out/'preprocessed_data_cache_paper1.npz';sweep=out/'paper1_validation_utility_sweep.csv'
    missing=[str(p) for p in files+[cache,sweep] if not p.is_file()]
    if missing:raise FileNotFoundError(f'{arm}: original outputs missing: {missing}. Without the source-fitted scaler and threshold the historical model cannot be evaluated.')
    first=_torch_load(files[0])
    if arm=='osta':
        order=list(first['feature_cols']);base=next((order[:k] for k in range(1,len(order)+1) if feature_names('osta',order[:k])==order),None)
        if base is None:raise ValueError('Checkpoint feature_cols are not generated by the original feature rule')
    else:
        base=list(first['feature_cols']);order=feature_names('cnn',base)
    if feature_names(arm,base)!=order:raise ValueError('Checkpoint feature order is not reproduced by the original generator')
    if 'FiO2' in base and (source_units or {}).get('FiO2') not in ['fraction','percent']:raise ValueError('Declare source FiO2 units')
    with np.load(cache,allow_pickle=False) as c:mean=np.asarray(c['feature_means'],np.float32);std=np.asarray(c['feature_stds'],np.float32)
    if len(mean)!=len(order):raise ValueError('Cached scaler length differs from feature order')
    np.savez(dest/'normalization.npz',mean=mean,std=std)
    s=pd.read_csv(sweep);thr=float(s.threshold.iloc[int(np.argmax(s.normalized_utility.to_numpy()))])
    kwargs=dict(ORIGINAL_KWARGS[arm])
    meta={'bundle_format':BUNDLE_FORMAT,'arm':arm,'provenance':'verified_historical','base_features':base,'feature_order':order,
          'model_kwargs':kwargs,'max_hours':120,'source_representation':representation,'source_units':source_units or {},
          'members':[{'file':str(p.resolve()),'sha256':sha(p),'format':'original_checkpoint'} for p in files],
          'ensemble':ensemble or {'combine':'mean_probability','weights':None},
          'calibration':{'intercept':0.,'slope':1.},'calibration_note':'identity: the original scripts did not calibrate; reported risk = ensemble step probability',
          'threshold':thr,'threshold_origin':str(sweep),'policy':HOURLY_POLICY,'threshold_selection_policy':HOURLY_POLICY,
          'original_test_policy_note':'original test-time evaluation latched from a (backdated) first alarm; not reused',
          'normalizer_sha256':sha(dest/'normalization.npz'),'normalizer_origin':{'file':str(cache),'bytes':cache.stat().st_size},
          'source_sha256':sha(source_file(arm)),'target_unsupported':[f for f in base if f in TARGET_UNSUPPORTED]}
    atomic_json(dest/'manifest.json',meta)
    return load_bundle(dest,arm,mode)

# ---------------------------------------------------------------------------
# Source staging and reproduction
# ---------------------------------------------------------------------------
def source_files(source,stage,mode,cap=None):
    """Official PSV folders or a patient-contiguous cleaned CSV. Stage one stay/file.
    CSV fails if a patient returns after a different patient; no silent split."""
    source=Path(source);stage=Path(stage);stage.mkdir(parents=True,exist_ok=True)
    cap=cap if cap is not None else (1600 if mode=='smoke' else None);rows=[]
    def write(g,identity):
        if 'Hour' not in g:g=g.assign(Hour=g.ICULOS.to_numpy(float) if 'ICULOS' in g else np.arange(1,len(g)+1))
        g=g.assign(Patient_ID=str(identity)).sort_values('Hour').iloc[:120]
        if not g.SepsisLabel.isin([0,1]).all() or (np.diff(g.SepsisLabel)<0).any():raise ValueError('Source must retain official step labels, without a second shift')
        if (np.diff(g.Hour)!=1).any():raise ValueError(f'{identity}: non-contiguous source hours')
        key=signature(str(identity))[:24];p=stage/(key+'.parquet');g.to_parquet(p,index=False)
        rows.append({'Patient_ID':str(identity),'file':str(p),'Outcome':int(g.SepsisLabel.max())})
    if source.is_dir():
        files=sorted(source.rglob('*.psv'))
        if cap and len(files)>cap:files=sorted(np.random.default_rng(42).choice(files,cap,replace=False))
        for p in files:write(pd.read_csv(p,sep='|'),str(p.relative_to(source)))
    elif source.is_file() and source.suffix.lower()=='.csv':
        carry=None;seen=set()
        for part in pd.read_csv(source,chunksize=200000,low_memory=False):
            if not {'Patient_ID','SepsisLabel'}<=set(part):raise ValueError('Cleaned CSV needs Patient_ID and SepsisLabel')
            d=pd.concat([carry,part],ignore_index=True) if carry is not None else part
            last=d.Patient_ID.iloc[-1];carry=d[d.Patient_ID.eq(last)].copy()
            for pid,g in d[d.Patient_ID.ne(last)].groupby('Patient_ID',sort=False):
                if pid in seen:raise ValueError('CSV must contain contiguous patient groups; sort by Patient_ID, Hour first')
                seen.add(pid);write(g,pid)
                if cap and len(rows)>=cap:break
            if cap and len(rows)>=cap:break
        else:
            if carry is not None:
                pid=carry.Patient_ID.iloc[0]
                if pid in seen:raise ValueError('Noncontiguous source patient')
                write(carry,pid)
    else:raise FileNotFoundError('Set PHYSIONET_SOURCE to official .psv folder or patient-contiguous CSV')
    z=pd.DataFrame(rows)
    if len(z)==0:raise ValueError('No source patient files')
    if z.Outcome.nunique()!=2 or z.Outcome.value_counts().min()<12:raise ValueError('Source smoke needs >=12 positive and negative stays. Increase source cap explicitly; no automatic full training.')
    z.to_parquet(stage/'source_index.parquet',index=False);return z

def source_preflight(index,policy='original_rule'):
    """Decide the base schema, representation and units BEFORE any training or target work."""
    sample=[pd.read_parquet(f) for f in index.file.iloc[:min(len(index),400)]]
    cols=list(sample[0].columns)
    base=original_feature_rule(cols) if policy=='original_rule' else list(DEFAULT_BASE)
    unknown=[f for f in base if f not in SOURCE_FEATURES]
    if unknown:raise ValueError(f'Source columns {unknown} have no validated MIMIC-IV/eICU adapter. Remove them from the source or use LEGACY_FEATURE_POLICY="common_core". Nothing was trained.')
    absent=[f for f in base if f not in cols]
    if absent:raise ValueError('Source lacks base columns: '+str(absent))
    rep,evidence=detect_representation(sample,base)
    if rep=='ambiguous':raise ValueError(f'Source representation ambiguous ({evidence}); inspect the CSV before training.')
    if evidence['mean_leading_missing_hours']==0 and rep=='patient_forward_filled':
        raise ValueError('Source has no leading missingness at all (likely backward-filled); a causal target equivalent cannot be built.')
    return {'base_features':base,'feature_policy':policy,'source_representation':rep,'representation_evidence':evidence,
            'source_units':detect_units(sample),'target_unsupported':[f for f in base if f in TARGET_UNSUPPORTED]}

def _original_split(index):
    """Same rule as the original scripts: 17.5% test, then 12.5% (of all) validation, seed 42."""
    pids=index.Patient_ID.to_numpy();y=index.set_index('Patient_ID').Outcome
    tv,te=train_test_split(pids,test_size=0.175,random_state=42,stratify=y.loc[pids].values)
    tr,va=train_test_split(tv,test_size=0.125/(1-0.175),random_state=42,stratify=y.loc[tv].values)
    return {**{p:'train' for p in tr},**{p:'val' for p in va},**{p:'test' for p in te}}

def _loss(arm,model,out,y,mask,sofa=None):
    m=definitions(arm)
    if arm=='osta':return m.osta_loss(out,y,mask)
    return m.improved_sepsis_loss(out[0],y,mask,utility_lambda=0.15,aux_lambda=0.20,sofa_pred=out[1] if sofa is not None else None,sofa_targets=sofa)

def reproduce(index,arm,root,mode='smoke',synthetic=False,preflight=None,device='cpu'):
    """Labelled PhysioNet-source reproduction using the ORIGINAL definitions, feature rule,
    split rule, losses, optimiser/schedule, model selection (validation patient AUROC every
    two epochs) and validation utility threshold grid. It is a re-training, never the
    historical fitted weights; smoke uses tiny models/epochs and tests the pipeline only.
    """
    root=Path(root);root.mkdir(parents=True,exist_ok=True);small=mode=='smoke'
    pf=preflight or source_preflight(index)
    recipe=dict(ORIGINAL_RECIPE[arm]);kwargs=dict(SMOKE_KWARGS[arm] if small else ORIGINAL_KWARGS[arm])
    if small:recipe.update(epochs=2,patience=2,batch=16,seeds=[42])
    membership=_original_split(index)
    meta={'bundle_format':BUNDLE_FORMAT,'arm':arm,'base_features':pf['base_features'],'max_hours':120,'model_kwargs':kwargs,
          'feature_policy':pf['feature_policy'],'source_representation':pf['source_representation'],'representation_evidence':pf['representation_evidence'],
          'source_units':pf['source_units'],'target_unsupported':pf['target_unsupported'],'recipe':recipe,
          'provenance':'synthetic_engineering' if synthetic else ('physionet_source_reproduction_smoke' if small else 'physionet_source_reproduction_full'),
          'recipe_note':'original definitions/losses/split/selection/threshold grid; re-trained here; not the historical weights; not bitwise identical (data loader order, hardware)',
          'policy':HOURLY_POLICY,'threshold_selection_policy':HOURLY_POLICY,'ensemble':{'combine':'mean_probability','weights':None}}
    meta['feature_order']=feature_names(arm,meta['base_features'])
    source_hashes={r.Patient_ID:sha(r.file) for r in index.itertuples()}
    contract=signature({'meta':meta,'source':source_hashes,'membership':membership,'module':sha(__file__),'source_code':sha(source_file(arm))})
    c=root/'contract.json'
    if c.exists() and json.loads(c.read_text())['sha256']!=contract:raise ValueError('Source reproduction contract changed; use a new bundle directory')
    atomic_json(c,{'sha256':contract,'membership':membership,'source_hashes':source_hashes})
    if (root/'manifest.json').exists() and json.loads((root/'manifest.json').read_text()).get('contract')==contract:
        return load_bundle(root,arm,mode)
    cache=root/'source_arrays';cache.mkdir(exist_ok=True);items={};total=sq=None;count=0
    has_sofa=arm=='cnn'
    for r in index.itertuples():
        p=cache/(signature(r.Patient_ID)[:24]+'.npz')
        if not p.exists():
            frame=pd.read_parquet(r.file)
            x,y,mask,h,names=raw_arrays(frame,meta)
            sofa=np.zeros(len(y),np.float32)
            if 'SOFA_Score' in frame:s=np.nan_to_num(frame.sort_values('Hour').SOFA_Score.to_numpy(float)[:120]);sofa[:len(s)]=s
            else:has_sofa=False
            tmp=p.with_suffix('.partial.npz');np.savez_compressed(tmp,x=x,y=y,mask=mask,h=h,sofa=sofa);os.replace(tmp,p)
        items[r.Patient_ID]=p
        if membership[r.Patient_ID]=='train':
            x=np.load(p)['x'].astype(float);a=np.nan_to_num(x[np.abs(x).sum(axis=1)>0],nan=0.,posinf=0.,neginf=0.)
            total=a.sum(0) if total is None else total+a.sum(0);sq=(a*a).sum(0) if sq is None else sq+(a*a).sum(0);count+=len(a)
    mean=np.nan_to_num(total/count);std=np.nan_to_num(np.sqrt(np.maximum(sq/count-mean**2,0)),nan=1.)+1e-8
    nb=sum(not f.endswith('_missing') for f in meta['feature_order'])
    mean[nb:]=0.;std[nb:]=1.   # original: trailing missingness indicators unscaled
    norm={'mean':mean.astype(np.float32),'std':std.astype(np.float32)};np.savez(root/'normalization.npz',**norm)
    ids={s:[p for p,v in membership.items() if v==s] for s in ['train','val','test']}
    def batch(pids):
        a=[dict(np.load(items[p])) for p in pids]
        return (torch.tensor(np.stack([original_normalize(d['x'],norm) for d in a]),device=device),torch.tensor(np.stack([d['y'] for d in a]),device=device),
                torch.tensor(np.stack([d['mask'] for d in a]),device=device),torch.tensor(np.stack([d['h'] for d in a]),device=device),
                torch.tensor(np.stack([d['sofa'] for d in a]),device=device))
    def patient_auroc(model):
        model.eval();ps=[];ys=[]
        for k in range(0,len(ids['val']),64):
            x,y,mask,h,_=batch(ids['val'][k:k+64]);z=_logits(model,x.cpu().numpy(),mask.cpu().numpy(),h.cpu().numpy(),device)
            pr=1/(1+np.exp(-z));mk=mask.cpu().numpy().astype(bool)
            ps+= [pr[i][mk[i]].max() for i in range(len(pr))];ys+= [y.cpu().numpy()[i][mk[i]].max() for i in range(len(pr))]
        return float(roc_auc_score(ys,ps)) if len(set(ys))==2 else float('nan')
    members=[]
    for seed in recipe['seeds']:
        wpath=root/f'member_seed{seed}.pt';done=root/f'member_seed{seed}.done.json'
        if done.exists():members.append(wpath);continue
        seed_all(seed);model=architecture(arm,meta['feature_order'],kwargs).to(device)
        opt=torch.optim.AdamW(model.parameters(),lr=recipe['lr'],weight_decay=recipe['weight_decay'])
        sched=torch.optim.lr_scheduler.CosineAnnealingLR(opt,T_max=recipe['epochs'])
        last=root/f'last_seed{seed}.pt';start=0;best=0.;wait=0
        if last.exists():
            s=torch.load(last,map_location=device,weights_only=True);model.load_state_dict(s['model']);opt.load_state_dict(s['optimizer']);sched.load_state_dict(s['scheduler'])
            start=int(s['epoch'])+1;best=float(s['best']);wait=int(s['wait'])
        for ep in range(start,recipe['epochs']):
            seed_all(seed*1000+ep);model.train();order=np.random.permutation(ids['train'])
            for k in range(0,len(order),recipe['batch']):
                x,y,mask,h,sofa=batch(order[k:k+recipe['batch']])
                out=model(x,mask,hours=h,return_interpretability=True) if arm=='osta' else model(x,mask,hours=h,return_aux=True)
                loss=_loss(arm,model,out,y,mask,sofa if has_sofa else None)
                if not torch.isfinite(loss):raise FloatingPointError('Source loss nonfinite')
                opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step()
            sched.step()
            if (ep+1)%2==0 or ep+1==recipe['epochs']:
                auc=patient_auroc(model)
                if auc>best or not (root/f'best_seed{seed}.pt').exists():best=max(best,auc if np.isfinite(auc) else 0.);wait=0;atomic_torch(root/f'best_seed{seed}.pt',model.state_dict())
                else:wait+=1
            atomic_torch(last,{'model':model.state_dict(),'optimizer':opt.state_dict(),'scheduler':sched.state_dict(),'epoch':ep,'best':best,'wait':wait})
            print('Source reproduction',arm,'seed',seed,'epoch',ep+1,'of',recipe['epochs'],flush=True)
            if wait>=recipe['patience']:break
        shutil.copyfile(root/f'best_seed{seed}.pt',wpath);atomic_json(done,{'seed':seed,'best_val_patient_auroc':best})
        members.append(wpath)
    meta['members']=[{'file':p.name,'sha256':sha(p),'format':'state_dict'} for p in members]
    meta['normalizer_sha256']=sha(root/'normalization.npz');meta['source_sha256']=sha(source_file(arm))
    meta['calibration']={'intercept':0.,'slope':1.};meta['threshold']=0.5;meta['contract']=contract
    models=[architecture(arm,meta['feature_order'],kwargs) for _ in members]
    for mo,p in zip(models,members):mo.load_state_dict(torch.load(p,map_location='cpu',weights_only=True));mo.eval()
    def predict_split(split):
        return pd.concat([predict_frame(models,pd.read_parquet(index.set_index('Patient_ID').file[p]),meta,norm) for p in ids[split]],ignore_index=True)
    pv=predict_split('val');frames=[g for _,g in pv.groupby('Patient_ID',sort=False)]
    sweep=[];best_t,best_u=0.5,-np.inf
    for t in THRESHOLD_GRID:
        u=normalized_utility([g.assign(risk=g.score) for g in frames],float(t),HOURLY_POLICY)['normalized_utility']
        sweep.append({'threshold':round(float(t),2),'normalized_utility':u})
        if np.isfinite(u) and u>best_u:best_u,best_t=u,round(float(t),2)
    meta['threshold']=best_t;meta['threshold_origin']='source validation split, original grid, hourly policy'
    meta['calibration']=calibrate(pv.rename(columns={'StepLabel':'y'}))
    meta['calibration_note']='source-validation Platt for reported risk only; alarms use the raw ensemble probability'
    pd.DataFrame(sweep).to_csv(root/'source_threshold_sweep.csv',index=False)
    # Source internal test: fidelity check against historically reported results, never used for tuning.
    pt=predict_split('test');ft=[g.assign(risk=g.score) for _,g in pt.groupby('Patient_ID',sort=False)]
    ut=normalized_utility(ft,best_t,HOURLY_POLICY)
    meta['source_internal_test']={'normalized_utility':ut['normalized_utility'],'stays':len(ft),
        'step_AUROC':float(roc_auc_score(pt.StepLabel,pt.score)) if pt.StepLabel.nunique()==2 else None}
    atomic_json(root/'manifest.json',meta)
    return load_bundle(root,arm,mode)

# ---------------------------------------------------------------------------
# Target adapter and scoring
# ---------------------------------------------------------------------------
def adapt_target(frame,meta):
    """Frozen source schema only. Unsupported PhysioNet channels stay missing (reported).
    V9 hourly values carry an availability TTL; carried repetitions are stripped with the
    measurement-age channels (float32-safe tolerance). Then the SOURCE representation is
    reproduced: sparse hourly (official PSV) or indefinite within-stay forward fill (cleaned
    CSV 'previous values'). The original preprocessor then applies its own ffill/zero-fill.
    """
    z=frame[['Patient_ID','Hour','StepLabel']].rename(columns={'StepLabel':'SepsisLabel'}).copy();missing=[]
    rep=meta.get('source_representation','sparse_hourly')
    for f in meta['base_features']:
        if f not in SOURCE_FEATURES:raise ValueError('Custom historical base feature needs an explicit validated adapter: '+f)
        if f=='ICULOS':z[f]=frame.Hour.to_numpy(float);continue
        if f not in frame or f in TARGET_UNSUPPORTED:z[f]=np.nan;missing.append(f);continue
        v=frame[f].astype(float)
        if f+'_age' in frame:
            event=(frame.Hour.astype(float)-frame[f+'_age'].astype(float)).to_numpy()
            fresh=np.zeros(len(v),bool);last=-np.inf
            for i,(e,val) in enumerate(zip(event,v.to_numpy())):
                if np.isfinite(e) and np.isfinite(val) and e>last+FRESH_TOLERANCE_HOURS:fresh[i]=True;last=e
            v=v.where(fresh)
            if rep=='patient_forward_filled':v=v.ffill()
        if f=='FiO2' and meta.get('source_units',{}).get('FiO2')=='fraction':v=v/100.
        z[f]=v.to_numpy()
    return z,missing

def score_target(index,bundles,root,n_boot=None):
    from v9_train import clustered_ci,paired_difference
    root=Path(root);root.mkdir(parents=True,exist_ok=True);results=[]
    for ds,ix in index.groupby('Dataset'):
        for arm,(models,meta,norm) in bundles.items():
            parts=[];missing=set()
            for r in ix.itertuples():
                d=pd.read_parquet(r.file).iloc[int(r.offset):int(r.offset+r.length)].copy()
                if 'StepLabel' not in d:raise ValueError('Legacy validation requires full challenge trajectory shards, not pre-onset v10 training shards')
                mapped,unknown=adapt_target(d,meta);missing.update(unknown)
                q=predict_frame(models,mapped,meta,norm);q['Group_ID']=r.Group_ID;q['Hospital_ID']=r.Hospital_ID;q['OnsetHour']=r.OnsetHour;parts.append(q)
            pred=pd.concat(parts,ignore_index=True);frames=[g.assign(risk=g.score) for _,g in pred.groupby('Patient_ID',sort=False)]
            u=normalized_utility(frames,meta['threshold'],meta['policy']);event,alarms=challenge_event_metrics(frames,meta['threshold'],meta['policy'])
            y=pred.StepLabel;p=pred.risk;two=y.nunique()==2
            boot=n_boot or (5 if any(k in meta['provenance'] for k in ['smoke','synthetic']) else 200)
            result={'Dataset':ds,'arm':arm,'provenance':meta['provenance'],'members':len(models),'threshold':meta['threshold'],
              'policy':json.dumps(meta['policy']),'source_representation':meta['source_representation'],'prevalence_step':float(y.mean()),
              'hourly_AUPRC_step':float(average_precision_score(y,p)) if two else np.nan,
              'hourly_AUROC_step':float(roc_auc_score(y,p)) if two else np.nan,'Brier_step':float(np.mean((p-y)**2)),
              'unsupported_channels':','.join(sorted(missing)),'probability_meaning':'PhysioNet step-label probability (label from onset-6h onward); not a calibrated incident 6-hour risk',**u,**event}
            result.update(clustered_ci(pred.rename(columns={'StepLabel':'y'}),boot))
            bins=pd.cut(pred.risk,np.linspace(0,1,11),include_lowest=True)
            points=pred.groupby(bins,observed=True).agg(mean_risk=('risk','mean'),event_fraction=('StepLabel','mean'),n=('risk','size'))
            result['ECE_10bin_step']=float(((points.mean_risk-points.event_fraction).abs()*points.n).sum()/len(pred))
            if two:
                from sklearn.linear_model import LogisticRegression
                diag=LogisticRegression(C=1e6,max_iter=1000).fit(np.log(np.clip(p,1e-6,1-1e-6)/(1-np.clip(p,1e-6,1-1e-6))).to_numpy().reshape(-1,1),y)
                result['calibration_intercept_step']=float(diag.intercept_[0]);result['calibration_slope_step']=float(diag.coef_[0,0])
            points.to_csv(root/f'{ds}_{arm}_calibration.csv',index=False)
            pred.to_parquet(root/f'{ds}_{arm}_predictions.parquet',index=False);alarms.to_parquet(root/f'{ds}_{arm}_alarms.parquet',index=False);results.append(result)
    paired=[]
    for ds in index.Dataset.unique():
        a=root/f'{ds}_osta_predictions.parquet';b=root/f'{ds}_cnn_predictions.parquet'
        if a.exists() and b.exists():
            pa=pd.read_parquet(a).rename(columns={'StepLabel':'y'});pb=pd.read_parquet(b).rename(columns={'StepLabel':'y'})
            prov=bundles['osta'][1]['provenance']
            paired.append({'Dataset':ds,'comparison':'OSTA minus CNN step AUPRC',**paired_difference(pa,pb,5 if ('synthetic' in prov or 'smoke' in prov) else 200)})
    pd.DataFrame(paired).to_csv(root/'paired_comparisons.csv',index=False)
    out=pd.DataFrame(results);out.to_csv(root/'legacy_results.csv',index=False);return out
