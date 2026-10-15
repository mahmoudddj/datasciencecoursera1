"""Bounded nonclinical checks for the legacy validation path (synthetic data only)."""
from pathlib import Path
import tempfile,json,contextlib,io
import numpy as np
import pandas as pd
import torch
from v10_evaluation import *
from v10_legacy import (definitions,architecture,raw_arrays,predict_frame,original_normalize,feature_names,adapt_target,
    import_original_outputs,load_bundle,DEFAULT_BASE,HOURLY_POLICY,ORIGINAL_KWARGS,detect_representation,combine,source_preflight)

def run_legacy_checks():
    checks=[]
    def check(n,v):
        if not bool(v):raise AssertionError(n)
        checks.append({'check':n,'passed':True})
    rng=np.random.default_rng(1)
    cases=[(np.zeros(10,int),np.ones(10,int)),(np.ones(10,int),np.zeros(10,int)),(np.ones(10,int),np.ones(10,int)),
           ((np.arange(30)>=5).astype(int),(np.arange(30)>=2).astype(int)),((np.arange(5)>=4).astype(int),np.r_[0,0,0,1,1])]
    for i in range(40):
        n=int(rng.integers(8,100));onset=int(rng.integers(0,n+12))
        cases.append(((np.arange(n)>=onset).astype(int) if i%2 else np.zeros(n,int),rng.integers(0,2,n)))
    for arm in ['osta','cnn']:
        m=definitions(arm)
        ok=all(np.isclose(m.compute_prediction_utility(y,p),official_utility(y,p),atol=1e-12) for y,p in cases)
        check(arm+'_original_utility_equals_official_on_%d_cases'%len(cases),ok)
        frames=[pd.DataFrame({'Hour':np.arange(1,len(y)+1),'StepLabel':y,'risk':p.astype(float)}) for y,p in cases[5:25]]
        ours=normalized_utility(frames,.5)['normalized_utility']
        orig=m.compute_normalized_utility([f.StepLabel.to_numpy() for f in frames],[f.risk.to_numpy().astype(int) for f in frames])[0]
        check(arm+'_normalized_utility_equals_original',np.isclose(ours,orig))
    # Labels already begin 6 h before onset: the scorer's onset is argmax+6 (no second shift).
    onset=20.;h=np.arange(1,40);y=(h>=onset-6).astype(int)
    check('step_label_single_shift',h[np.argmax(y)]+6==onset)
    check('persistence_confirmation_not_backdated',np.array_equal(alarm_policy([.1,.8,.9],[1,2,3],.5,persistence=2),[0,0,1]))
    check('persistence_gap_resets',not alarm_policy([.8,.9],[1,3],.5,persistence=2).any())
    check('latched_policy_stays_latched',np.array_equal(alarm_policy([.1,.8,.2],[1,2,3],.5,latch=True),[0,1,1]))
    try:normalized_utility([pd.DataFrame({'Hour':[1,3],'StepLabel':[0,0],'risk':[.1,.2]})],.5);raise AssertionError('gap accepted')
    except ValueError:check('no_compressed_time_utility',True)
    g=pd.DataFrame({'Patient_ID':'a','Group_ID':'a','Hour':np.arange(1,13.),'risk':[0]*3+[.9]+[0]*8,'OnsetHour':12.})
    em,_=challenge_event_metrics([g],.5,HOURLY_POLICY)
    check('excessively_early_alarm_classified',em['early_alarm_episodes']==1 and em['event_sensitivity']==0)
    # Exact original normalisation semantics, including inf handling.
    pre=definitions('osta').EnhancedSepsisPreprocessor(pd.DataFrame({'Patient_ID':[],'Hour':[],'SepsisLabel':[],'HR':[]}),['HR'])
    x=rng.normal(size=(3,5,4));x[0,0,0]=np.inf;x[1,1,1]=np.nan;x[2,2,2]=-np.inf
    pre.feature_cols=['a','b','c'];pre.use_missingness=True
    pre.feature_means=rng.normal(size=4);pre.feature_stds=np.abs(rng.normal(size=4))+.1
    check('normalization_matches_original',np.allclose(original_normalize(x,{'mean':pre.feature_means,'std':pre.feature_stds}),pre.normalize(x),atol=1e-6))
    check('ensemble_uniform_mean',np.allclose(combine([[.2,.4],[.4,.8]],{'combine':'mean_probability','weights':None}),[.3,.6]))
    from v10_fixture import make_legacy_fixture
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);index,target=make_legacy_fixture(td,nsource=24,ntarget=4)
        frame=pd.read_parquet(index.file.iloc[1])
        pf=source_preflight(index)
        check('sparse_source_detected',pf['source_representation']=='sparse_hourly' and pf['base_features']==DEFAULT_BASE)
        ff=[pd.read_parquet(f).assign(**{c:lambda d,c=c:d[c].ffill() for c in DEFAULT_BASE}) for f in index.file.iloc[:6]]
        check('forward_filled_source_detected',detect_representation(ff,DEFAULT_BASE)[0]=='patient_forward_filled')
        # Target adapter: carried TTL repeats stripped (float32-safe); forward-filled representation refilled.
        t=pd.read_parquet(target.file.iloc[0]).iloc[:int(target.length.iloc[0])]
        meta={'base_features':DEFAULT_BASE,'source_representation':'sparse_hourly'}
        sp,miss=adapt_target(t,meta)
        lab_rows=int(sp.Creatinine.notna().sum())
        check('adapter_strips_carried_lab_values',0<lab_rows<=4 and t.Creatinine.notna().sum()>lab_rows)
        fill,_=adapt_target(t,{**meta,'source_representation':'patient_forward_filled'})
        first=int(np.argmax(sp.Creatinine.notna()))
        check('adapter_forward_fill_representation',fill.Creatinine.iloc[first:].notna().all() and fill.Creatinine.iloc[:first].isna().all())
        check('adapter_unsupported_stay_missing',adapt_target(t.assign(TroponinI=5.),{'base_features':DEFAULT_BASE+['TroponinI'],'source_representation':'sparse_hourly'})[1]==['TroponinI'])
        for arm in ['osta','cnn']:
            meta={'arm':arm,'base_features':DEFAULT_BASE,'max_hours':120,'calibration':{'intercept':0.,'slope':1.}}
            x,y,mask,h,names=raw_arrays(frame,meta);meta['feature_order']=names
            check(arm+'_feature_order_generator',feature_names(arm,DEFAULT_BASE)==names)
            kwargs={'d_organ':16,'d_global':32,'n_layers_organ':1,'n_layers_global':1,'dropout':0.,'mc_samples':1} if arm=='osta' else {'d_model':32,'n_heads':4,'num_layers':1,'dim_feedforward':64,'dropout':0.}
            model=architecture(arm,names,kwargs).eval();norm={'mean':np.zeros(len(names)),'std':np.ones(len(names))}
            p=predict_frame(model,frame,meta,norm);prefix=predict_frame(model,frame.iloc[:12],meta,norm)
            check(arm+'_frozen_eval_prefix',np.allclose(p.logit.iloc[:12],prefix.logit,atol=1e-5,rtol=1e-5))
            if arm=='cnn':check('legacy_batchnorm_preserved',any(isinstance(m,torch.nn.BatchNorm1d) for m in model.modules()))
            # ---- historical import round trip: ORIGINAL output files -> frozen bundle ----
            out=td/f'orig_{arm}';out.mkdir()
            torch.manual_seed(3);seeds=[42,7] if arm=='osta' else [42]
            members=[architecture(arm,names,ORIGINAL_KWARGS[arm]).eval() for _ in seeds]
            for mdl,s in zip(members,seeds):
                ck={'checkpoint_format':'causal-v1','model_state_dict':mdl.state_dict(),'feature_cols':names if arm=='osta' else DEFAULT_BASE,
                    'threshold':np.float64(.37),'best_val_auc':np.float64(.8)}
                torch.save(ck,out/(f'v5_seed{s}_model.pt' if arm=='osta' else 'sepsis_enhanced_transformer.pt'))
            means=rng.normal(size=len(names));stds=np.abs(rng.normal(size=len(names)))+.5
            nb=sum(not f.endswith('_missing') for f in names);means[nb:]=0;stds[nb:]=1
            np.savez_compressed(out/('v5_preprocessed_cache.npz' if arm=='osta' else 'preprocessed_data_cache_paper1.npz'),
                feature_means=means,feature_stds=stds,p_tr=np.array(['a'],dtype=object))
            pd.DataFrame({'threshold':[.05,.06,.07],'normalized_utility':[.1,.3,.3]}).to_csv(out/('v5_validation_utility_sweep.csv' if arm=='osta' else 'paper1_validation_utility_sweep.csv'),index=False)
            ms,man,nrm=import_original_outputs(arm,out,td/f'bundle_{arm}','sparse_hourly',seeds=seeds)
            check(arm+'_historical_threshold_first_max',np.isclose(man['threshold'],.06))
            # Reference: the original preprocessor/normalize/forward exactly as the old scripts ran them.
            mdef=definitions(arm)
            with contextlib.redirect_stdout(io.StringIO()):
                eng,new=mdef.engineer_temporal_features(frame.copy(),DEFAULT_BASE)
                pp=mdef.EnhancedSepsisPreprocessor(eng,DEFAULT_BASE+new,max_hours=120,use_missingness=True)
                X,Y,M,_,_,H=pp.prepare_sequences()[:6]
            pp.feature_means=means;pp.feature_stds=stds;Xn=torch.FloatTensor(pp.normalize(X))
            with torch.no_grad():
                ref=np.mean([torch.sigmoid((lambda o:o['logits'] if isinstance(o,dict) else o)(mm(Xn,torch.FloatTensor(M),hours=torch.FloatTensor(H)))).numpy()[0][:24] for mm in members],axis=0)
            got=predict_frame(ms,frame,man,nrm).score.to_numpy()
            check(arm+'_historical_import_reproduces_original_pipeline',np.allclose(got,ref,atol=1e-5))
            bad=json.loads((td/f'bundle_{arm}'/'manifest.json').read_text());bad['policy']={**HOURLY_POLICY,'latch':True}
            (td/f'bundle_{arm}'/'manifest.json').write_text(json.dumps(bad))
            try:load_bundle(td/f'bundle_{arm}',arm);raise AssertionError('policy mismatch accepted')
            except ValueError:check(arm+'_policy_mismatch_refused',True)
            bad['policy']=HOURLY_POLICY;bad['members'][0]['sha256']='0'*64;(td/f'bundle_{arm}'/'manifest.json').write_text(json.dumps(bad))
            try:load_bundle(td/f'bundle_{arm}',arm);raise AssertionError('tampered weights accepted')
            except ValueError:check(arm+'_weight_hash_enforced',True)
        # Full-size ORIGINAL architectures: forward/backward with the ORIGINAL losses on a tiny batch.
        from v10_legacy import _loss,ORIGINAL_RECIPE,SMOKE_KWARGS
        for arm in ['osta','cnn']:
            meta={'arm':arm,'base_features':DEFAULT_BASE,'max_hours':120}
            x,y,mask,h,names=raw_arrays(frame,meta)
            torch.manual_seed(0);mdl=architecture(arm,names,ORIGINAL_KWARGS[arm]).train()
            X=torch.tensor(np.stack([x,x]));Y=torch.tensor(np.stack([y,y]));M=torch.tensor(np.stack([mask,mask]));H=torch.tensor(np.stack([h,h]))
            out=mdl(X,M,hours=H,return_interpretability=True) if arm=='osta' else mdl(X,M,hours=H,return_aux=True)
            loss=_loss(arm,mdl,out,Y,M,torch.zeros_like(Y) if arm=='cnn' else None);loss.backward()
            check(arm+'_full_size_original_loss_backward',torch.isfinite(loss) and all(torch.isfinite(q.grad).all() for q in mdl.parameters() if q.grad is not None))
        check('full_mode_resolution',ORIGINAL_KWARGS['osta']['d_global']==256 and ORIGINAL_KWARGS['cnn']['num_layers']==4
              and ORIGINAL_RECIPE['osta']['seeds']==[42,7,123] and ORIGINAL_RECIPE['osta']['epochs']==50 and ORIGINAL_RECIPE['cnn']['epochs']==30
              and SMOKE_KWARGS['osta']['d_global']<ORIGINAL_KWARGS['osta']['d_global'])
    # ---- clinical-path dry run on schema-shaped synthetic raw tables (both databases) ----
    from v10_fixture import make_raw_schema_fixture
    from v10_clinical import legacy_target
    from v9_data import cohort_index,RawExtractor,build_shards
    from v9_train import atomic_json
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);fx,onset=make_raw_schema_fixture(td)
        for ds,(raw,coh) in fx.items():
            sel=cohort_index(coh,None,42)
            got=sel.set_index('stay_id').OnsetHour
            check(ds+'_onset_from_unwindowed_events',len(got)==len(onset) and all((np.isnan(a) and np.isnan(onset[k])) or a==onset[k] for k,a in got.items()))
            stage=td/'stage'/ds;RawExtractor(ds,raw,sel,stage,120).extract();atomic_json(stage/'raw_complete.json',{})
            ix,schema=build_shards(ds,stage,coh,td/'shards'/ds,120,6,4)
            check(ds+'_main_shards_built',len(ix)>0 and 'HR_Slope3h' in schema and ix.Group_ID.str.startswith(ds+'|').all())
            t1=legacy_target(ds,raw,coh,td/'t1'/ds,120,'smoke',False)
            t2=legacy_target(ds,raw,coh,td/'t2'/ds,120,'smoke',False,reuse_stage=stage)
            d=pd.read_parquet(t1.file.iloc[0])
            check(ds+'_legacy_target_hospadmtime',np.allclose(d.HospAdmTime.dropna(),-5.) and d.HospAdmTime.notna().all())
            check(ds+'_legacy_followup_to_discharge',t1.length.max()==30)
            from v10_protocol import protected_group
            persons=pd.read_parquet(stage/'metadata.parquet').set_index('stay_id').person
            expect={k for k,v in onset.items() if v<7 and not protected_group(ds+'|'+str(persons[k]))}
            ex=set(pd.read_parquet(td/'t1'/ds/'excluded_clipped_onsets.parquet').stay_id)
            check(ds+'_legacy_early_onset_excluded',ex==expect and not (t1.OnsetHour<7).any())
            check(ds+'_legacy_protected_patients_sealed',not t1.Group_ID.map(protected_group).any())
            r=t1[t1.OnsetHour.notna()].iloc[0] if t1.OnsetHour.notna().any() else None
            if r is not None:
                g=pd.read_parquet(r.file).iloc[int(r.offset):int(r.offset+r.length)]
                check(ds+'_legacy_step_label_onset_minus6',g.Hour[g.StepLabel.eq(1)].min()==r.OnsetHour-6)
            a=pd.concat([pd.read_parquet(f) for f in sorted(set(t1.file))]);b=pd.concat([pd.read_parquet(f) for f in sorted(set(t2.file))])
            check(ds+'_legacy_stage_reuse_identical',json.loads((td/'t2'/ds/'complete.json').read_text())['reused_raw_stage'] is not None and a.reset_index(drop=True).equals(b.reset_index(drop=True)))
    return checks
