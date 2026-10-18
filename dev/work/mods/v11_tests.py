"""V11 engineering checks (nonclinical): losses, survival head, signatures, conformal policy,
lead-time metric, label-free pretraining, causality of every new arm, prophylaxis rule, corpus
selection, parallel shard building. Appended to v10_tests.run_checks."""
from pathlib import Path
import tempfile,json,contextlib,io
import numpy as np
import pandas as pd
import torch

def run_v11_checks():
    from v9_train import AGE_SCALE,SequenceStore,fit_normalizer
    from v11_models import make_model,Pretrainer,measured_channels,HAZARD_EDGES
    from v11_train import (targets_and_weights,hazard_nll,SignatureStore,ssl_targets,ssl_loss,antibiotic_lead,conformal_policy,
                           dense_hours,ood_scores,utility_gap_weight)
    from v11_data import SupplementExtractor,unlabelled_stays
    from v9_data import build_shards,build_sequence,normalize_events,RawExtractor
    from v10_protocol import protected_group
    checks={}
    def check(name,ok):
        if not ok:raise AssertionError('v11:'+name)
        checks[name]='pass'
    # ---- losses ----
    hours=torch.arange(1,25).float().view(1,-1);y=torch.zeros(1,24);y[0,13:19]=1   # onset 20: positives at 14..19
    elig=torch.ones(1,24);elig[0,19:]=0;mask=torch.ones(1,24)
    b={'y':y,'eligible':elig,'mask':mask,'hours':hours};on=torch.tensor([20.])
    t,w=targets_and_weights(b,on,'utility_weighted_bce')
    check('utility_weights_post_onset_positives',bool(t[0,19:23].eq(1).all()) and bool(w[0,19:23].gt(0).all()) and bool(w[0,23]==0))
    pos=t[0]>.5;check('utility_weights_mean_one_and_increasing',abs(float(w[0][pos].mean())-1)<1e-5 and bool((torch.diff(w[0][pos])>0).all()))
    check('utility_gap_shape',abs(float(utility_gap_weight(torch.tensor(-6.)))-1.)<1e-6 and abs(float(utility_gap_weight(torch.tensor(3.)))-2.)<1e-6)
    t2,w2=targets_and_weights(b,on,'tls');check('tls_soft_ramp',bool(t2[0,13:19].eq(1).all()) and 0<float(t2[0,12])<.5 and float(t2[0,0])==0 and bool(w2.eq(elig).all()))
    t3,w3=targets_and_weights(b,torch.tensor([float('nan')]),'utility_weighted_bce');check('nonseptic_unchanged',bool(t3.eq(y).all()) and bool(w3.eq(elig).all()))
    hz=torch.full((1,24,len(HAZARD_EDGES)-1),.1);nll=hazard_nll(hz,b,on);hz2=hz.clone();hz2[0,:,2]=.9
    check('hazard_nll_finite_and_sensitive',torch.isfinite(nll) and float(hazard_nll(hz2,b,on))!=float(nll))
    # ---- signatures: straight line has zero Levy area; increments exact ----
    P=np.stack([np.arange(5.),2*np.arange(5.)],1);l1,l2=SignatureStore.signatures(P)
    check('signature_increments',np.allclose(l1,[4.,8.]));S=l2.reshape(2,2);check('signature_levy_area_zero_for_line',abs(S[0,1]-S[1,0])<1e-9 and abs(S[0,0]-8.)<1e-9)
    # ---- fixture-based checks ----
    from v10_fixture import make_fixture
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);INDEX,FEATURES=make_fixture(td/'fx',n=24);mi=INDEX[INDEX.Dataset.eq('miiv')].copy()
        norm=fit_normalizer(SequenceStore(mi,FEATURES,max_hours=24));store=SequenceStore(mi,FEATURES,norm,24)
        j=FEATURES.index('HR_age');check('age_channel_in_days',abs(norm['std'][j]-AGE_SCALE)<1e-9 and norm['mean'][j]==0)
        sig=SignatureStore(mi,FEATURES,norm,24);it=sig[0];check('signature_store_width',it['x'].shape[1]==len(sig.features)==len(FEATURES)+2*(8+64))
        dh=dense_hours(store);check('dense_hours_causal_flag',set(dh.columns)=={'Patient_ID','Hour','dense'} and dh.dense.dtype==bool)
        oo=ood_scores(store);check('ood_scores_in_unit_interval',oo.ood.between(0,1).all())
        # pretraining targets use no labels: compare on a batch with y shuffled
        with contextlib.redirect_stdout(io.StringIO()):pt=Pretrainer(FEATURES,depth=2)
        it0=store[0];x=torch.tensor(it0['x']).unsqueeze(0);m=torch.tensor(it0['mask']).unsqueeze(0)
        tg=ssl_targets(x,m,pt);tot,parts=ssl_loss(pt(x),tg)
        check('ssl_targets_label_free',set(tg)>={'forecast','measured'} and torch.is_tensor(tot) and torch.isfinite(tot))
        # causality of every v11 arm on real feature layout
        cfg={'small_model':True,'dropout':0.,'cnn_depth':2,'event_lookback':24}
        xb=torch.stack([torch.tensor(store[i]['x']) for i in range(2)]);mb=torch.stack([torch.tensor(store[i]['mask']) for i in range(2)]);hb=torch.stack([torch.tensor(store[i]['hours']) for i in range(2)])
        for arm in ['flat_osta','grud','tcn','cnn_osta','ssl_cnn_flat','event_osta','hazard_ssl_cnn_osta']:
            with contextlib.redirect_stdout(io.StringIO()):model=make_model(arm,FEATURES,cfg).eval()
            with torch.no_grad():
                a=model(xb,mb,hb);x2=xb.clone();x2[:,10:]=torch.randn_like(x2[:,10:]);bq=model(x2,mb,hb)
            check(f'{arm}_future_invariance',float((a[:,:10]-bq[:,:10]).abs().max())<1e-5)
        with contextlib.redirect_stdout(io.StringIO()):hm=make_model('hazard_ssl_cnn_osta',FEATURES,cfg).eval()
        with torch.no_grad():hm(xb,mb,hb)
        check('hazard_probabilities_bounded',bool((hm.last_hazards>0).all()) and bool((hm.last_hazards<1).all()))
        # conformal policy and antibiotic lead on synthetic predictions
        pred=pd.DataFrame({'Patient_ID':['a']*10+['b']*10,'Group_ID':['a']*10+['b']*10,'Hospital_ID':['h']*20,'Hour':list(range(1,11))*2,
            'y':[0]*4+[1]*6+[0]*10,'risk':np.r_[np.linspace(.1,.9,10),np.linspace(.05,.3,10)],'OnsetHour':[11.]*10+[np.nan]*10,
            'FirstAntibioticAroundOnset':[9.]*10+[np.nan]*10})
        cfgp={'false_alarm_budget':.5,'horizon':6,'alarm_cooldown':6}
        lead=antibiotic_lead(pred,.5,cfgp);check('antibiotic_lead_metric',lead['antibiotic_lead_n']==1 and lead['median_lead_vs_first_antibiotic_hours']==3. and lead['fraction_alarm_before_first_antibiotic']==1.)
        ood=pd.DataFrame({'Patient_ID':pred.Patient_ID,'Hour':pred.Hour,'ood':np.r_[np.zeros(19),[1.]]})
        tc,info=conformal_policy(pred,pred,ood,ood,cfgp,alpha=.1)
        check('conformal_abstains_outlier_and_bounds_threshold',info['conformal_abstained_fraction']>0 and tc.risk.iloc[-1]==0 and 0<info['conformal_threshold']<=1)
        # parallel == sequential shard building (same records, index, schema)
        from v9_data import build_shards as bs
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);root=td/'miiv';(root/'icu').mkdir(parents=True);(root/'hosp').mkdir()
        T=lambda h:str(pd.Timestamp('2100-01-01')+pd.Timedelta(hours=h));ids=[1,2,3,4,5,6]
        pd.DataFrame({'stay_id':ids,'hadm_id':[i+10 for i in ids],'subject_id':[i+100 for i in ids],'intime':[T(0)]*6,'outtime':[T(30)]*6}).to_csv(root/'icu/icustays.csv',index=False)
        pd.DataFrame({'subject_id':[i+100 for i in ids],'anchor_age':[50+i for i in ids],'gender':['M','F']*3}).to_csv(root/'hosp/patients.csv',index=False)
        rows=[{'stay_id':i,'itemid':220045,'charttime':T(h),'storetime':T(h),'valuenum':80+i+h%3,'value':'x','valueuom':'bpm'} for i in ids for h in range(0,12)]
        pd.DataFrame(rows).to_csv(root/'icu/chartevents.csv',index=False)
        pd.DataFrame({'stay_id':ids,'itemid':[226559]*6,'charttime':[T(1)]*6,'storetime':[T(1)]*6,'value':[50.]*6,'valueuom':['mL']*6}).to_csv(root/'icu/outputevents.csv',index=False)
        sel,static=unlabelled_stays('miiv',root,[1],protected_group,max_hours=12)
        check('unlabelled_corpus_excludes_cohort_and_protected',1 not in set(sel.stay_id) and len(sel)>=1 and not sel.stay_id.map(lambda i:protected_group('miiv|'+str(i+100))).any())
        with contextlib.redirect_stdout(io.StringIO()):
            RawExtractor('miiv',root,sel,td/'st',12).extract()
            ix1,s1=bs('miiv',td/'st',None,td/'seq',12,6,batch=2,static=static,workers=1)
            ix2,s2=bs('miiv',td/'st',None,td/'par',12,6,batch=2,static=static,workers=2)
        a=pd.read_parquet(ix1.file.iloc[0]);bq=pd.read_parquet(ix2.file.iloc[0])
        check('parallel_shards_identical',s1==s2 and len(ix1)==len(ix2) and a.drop(columns='Patient_ID').equals(bq.drop(columns='Patient_ID')) and ix1.FirstAntibioticAroundOnset.isna().all())
        # supplementary stage -> prophylaxis features in the sequence; antibiotic metadata in the index
        sel2=pd.DataFrame({'stay_id':[1,2],'first_hour':[0.,0.],'followup_end':[24.,24.],'first_positive':[np.nan,np.nan],'OnsetHour':[np.nan,8.],'Outcome':[0,1]})
        pd.DataFrame({'subject_id':[101,102],'hadm_id':[11,12],'admittime':[T(-30)]*2,'dischtime':[T(60)]*2,'admission_type':['SURGICAL SAME DAY ADMISSION','EW EMER.'],'admission_location':['PHYSICIAN REFERRAL','EMERGENCY ROOM']}).to_csv(root/'hosp/admissions.csv',index=False)
        pd.DataFrame({'subject_id':[101],'hadm_id':[11],'transfer_id':[1],'eventtype':['transfer'],'careunit':['PACU'],'intime':[T(-1)]}).to_csv(root/'hosp/transfers.csv',index=False)
        pd.DataFrame({'subject_id':[101,101,102],'hadm_id':[11,11,12],'drug':['Cefazolin','Sulfamethoxazole-Trimethoprim','Piperacillin-Tazobactam'],'starttime':[T(-3),T(5),T(7)],'stoptime':[T(-2),T(100),T(120)],
            'doses_per_24_hrs':[1,1,3],'dose_val_rx':[2,1,4.5],'route':['IV','PO','IV']}).to_csv(root/'hosp/prescriptions.csv',index=False)
        pd.DataFrame({'subject_id':[102],'hadm_id':[12],'charttime':[T(6)],'spec_type_desc':['BLOOD CULTURE'],'org_name':[None]}).to_csv(root/'hosp/microbiologyevents.csv',index=False)
        with contextlib.redirect_stdout(io.StringIO()):
            SupplementExtractor('miiv',root,sel2,td/'supp',12).supplement()
            RawExtractor('miiv',root,sel2,td/'st2',12).extract()
            ix3,_=bs('miiv',td/'st2',None,td/'seq3',12,6,batch=4,static=pd.DataFrame({'stay_id':[1,2],'Age':[60.,70.],'Gender':[1.,0.]}),supplement=td/'supp',workers=1)
        f=pd.read_parquet(ix3.file.iloc[0]);s1_=f[f.Patient_ID.eq('miiv|1')];s2_=f[f.Patient_ID.eq('miiv|2')]
        check('prophylaxis_features_causal',s1_.Prophylaxis_Surgical_24h.iloc[0]==1 and s1_.Prophylaxis_Medical.iloc[:4].eq(0).all() and s1_.Prophylaxis_Medical.iloc[5]==1 and s2_.Prophylaxis_Surgical_24h.eq(0).all())
        check('first_antibiotic_metadata_for_septic_stay',float(ix3.set_index('stay_id').FirstAntibioticAroundOnset[2])==7. and np.isnan(ix3.set_index('stay_id').FirstAntibioticAroundOnset[1]))
    print('V11 engineering checks:',len(checks),'PASS')
    return checks
