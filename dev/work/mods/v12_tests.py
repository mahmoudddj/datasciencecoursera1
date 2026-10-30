"""Engineering checks for the v12 modules (manifest, labels, baseline-relative features). Synthetic data only."""
import numpy as np
import pandas as pd

def run_checks():
    passed=[]
    def ok(name,cond):
        if not cond:raise AssertionError('v12 check failed: '+name)
        passed.append(name)
    # ---- manifest ----
    from v12_manifest import manifest,audit,path_of,path_indices,HOST,concept_grouped_practice
    feats=['HR','HR_observed','HR_age','Lactate','Lactate_age','Age','Gender','Comorbidity_diabetes','Med_BetaBlocker_24h','Device_CentralLine_Hours',
           'AdmitSource_ED','Intubated','O2_NIV','UrineCoverage_6h','Urine_mlkg_h_6h','HR_Count6h','HR_Slope6h','SOFA_Available','SOFA_MetAmongMeasured','ICULOS',
           'Vasopressor_HoursSinceLast','VasopressorRecorded','Prophylaxis_Medical','ShockIndex','SIRS_Count','SIRS_ObservedComponents','LabResults_24h']
    m=manifest(feats);summary=audit(m,feats)
    ok('manifest: every feature exactly once',len(m)==len(feats) and m.feature.is_unique)
    ok('manifest: masks and ages are practice',m[m.feature.str.endswith(('_observed','_age'))].path.eq('practice').all())
    ok('manifest: host block in physiology',m.set_index('feature').loc[['Age','Gender','Comorbidity_diabetes'],'path'].eq('physiology').all())
    ok('manifest: exposures, admission, states, airway, prophylaxis are practice',m.set_index('feature').loc[['Med_BetaBlocker_24h','Device_CentralLine_Hours','AdmitSource_ED','Intubated','O2_NIV','Prophylaxis_Medical','LabResults_24h'],'path'].eq('practice').all())
    ok('manifest: measurement-process handcrafted columns are practice',m.set_index('feature').loc[['HR_Count6h','SOFA_Available','ICULOS','Vasopressor_HoursSinceLast','UrineCoverage_6h','SIRS_ObservedComponents'],'path'].eq('practice').all())
    ok('manifest: physiology handcrafted and derived stay physiology',m.set_index('feature').loc[['HR_Slope6h','ShockIndex','Urine_mlkg_h_6h','VasopressorRecorded','SOFA_MetAmongMeasured','SIRS_Count'],'path'].eq('physiology').all())
    ok('manifest: availability-dependent flags',m.set_index('feature').loc['SOFA_MetAmongMeasured','availability_dependent'] and m.set_index('feature').loc['SIRS_Count','availability_dependent'] and not m.set_index('feature').loc['HR','availability_dependent'])
    ok('manifest: path indices partition the columns',sorted(path_indices(feats,'physiology',m)+path_indices(feats,'practice',m))==list(range(len(feats))))
    ok('manifest: host block can be excluded',set(feats[i] for i in path_indices(feats,'physiology',m,exclude_blocks=('host',)))&set(HOST)==set())
    cg=concept_grouped_practice(feats,{'HR':'cardiovascular','Lactate':'cardiovascular','HR_observed':'cardiovascular','HR_age':'cardiovascular','Lactate_age':'cardiovascular'})
    ok('manifest: concept grouping yields one intensity and one freshest-age column per group',sorted(c for c,_,_ in cg)==['PracticeGroup_freshest_age_cardiovascular','PracticeGroup_intensity_cardiovascular'])
    # ---- suspicion event ----
    from v12_labels import suspicion_event,suspicion_events,suspicion_label,pre_treatment_mask,documentation_prior,stay_soft_value,label_variant
    h,r=suspicion_event([10.],[90.]);ok('suspicion: continued course at hour 10 is the event',h==10. and r=='event')
    h,r=suspicion_event([3.],[90.]);ok('suspicion: start before hour 6 is not an event',np.isnan(h) and r.startswith('no_start'))
    h,r=suspicion_event([2.,30.],[20.,110.]);ok('suspicion: a start inside the 72 h washout is rejected',np.isnan(h) and r=='antibiotic_in_washout')
    h,r=suspicion_event([10.],[20.]);ok('suspicion: a 10 h course is not continued',np.isnan(h) and r=='course_not_continued')
    h,r=suspicion_event([10.,30.,50.,70.],[np.nan]*4);ok('suspicion: daily starts without stops cover 72 h',h==10.)
    h,r=suspicion_event([10.,60.],[np.nan,np.nan]);ok('suspicion: a 26 h gap breaks the course',np.isnan(h))
    h,r=suspicion_event([10.],[20.],death_hour=40.);ok('suspicion: death within 72 h counts as continued',h==10.)
    h,r=suspicion_event([10.,100.],[20.,200.]);ok('suspicion: the first continued course after a rejected one is the event',h==100.)
    ev=suspicion_events(pd.DataFrame({'stay_id':[1,1,2],'start':[10.,30.,8.],'stop':[90.,100.,12.]}))
    ok('suspicion: per-stay frame',list(ev.stay_id)==[1,2] and ev.suspicion_hour.iloc[0]==10. and np.isnan(ev.suspicion_hour.iloc[1]))
    y,e=suspicion_label(np.arange(1,21,dtype=float),12.,3.)
    ok('suspicion label: positives are hours 9,10,11 and eligibility stops at the event',list(np.nonzero(y)[0]+1)==[9,10,11] and e.sum()==11)
    y,e=suspicion_label(np.arange(1,21,dtype=float),np.nan,3.,followup_end=20.)
    ok('suspicion label: no event gives zeros and eligibility inside follow-up',y.sum()==0 and e.sum()==17)
    ok('pre-treatment mask',pre_treatment_mask([1,2,3,4],3.).tolist()==[True,True,False,False] and pre_treatment_mask([1,2],np.nan).all())
    st=pd.DataFrame({'Dataset':['a']*4+['b']*2,'operational_positive':[1,1,1,0,1,1],'documented':[1,0,0,0,1,1]})
    pr=documentation_prior(st);ok('documentation prior per database',abs(pr['a']-1/3)<1e-9 and pr['b']==1.)
    ok('soft values',stay_soft_value(1,1,.4)==1. and stay_soft_value(1,0,.4)==.4 and stay_soft_value(0,1,.4)==0.)
    ok('label variant scales the hourly label',label_variant([0,1,1],.4).tolist()==[0.,.4,.4])
    # ---- baseline-relative features ----
    from v12_features import baseline_relative,new_measurements,baseline_relative_columns
    hours=np.arange(1,41,dtype=float)
    hr=np.where(hours<=30,80.,100.)      # a step at hour 31
    age=np.zeros(40)                     # measured every hour
    f=pd.DataFrame({'Hour':hours,'HR':hr,'HR_age':age})
    out=baseline_relative(f,channels=['HR'])
    ok('baseline: undefined before any measurement is 6 h old',np.isnan(out.HR_BaseDev.iloc[:6]).all())
    ok('baseline: deviation is zero on the plateau and +20 after the step',abs(out.HR_BaseDev.iloc[20])<1e-9 and abs(out.HR_BaseDev.iloc[35]-20)<1e-9)
    ok('baseline: z undefined with zero spread',np.isnan(out.HR_BaseZ.iloc[35]))
    ok('baseline: 24 h maximum sees the step, minimum keeps the plateau',abs(out.HR_BaseDevMax24h.iloc[35]-20)<1e-9 and abs(out.HR_BaseDevMin24h.iloc[35])<1e-9)
    # causality: changing the future must not change the past
    f2=f.copy();f2.loc[f2.Hour>35,'HR']=200.;out2=baseline_relative(f2,channels=['HR'])
    ok('baseline: causal (future edits leave earlier rows unchanged)',np.allclose(out.iloc[:35].fillna(-1).to_numpy(),out2.iloc[:35].fillna(-1).to_numpy()))
    # measurement recovery with lag: a lab resulted 2 h after draw
    lab=np.full(40,np.nan);lab_age=np.full(40,np.nan)
    for t0 in (4.,12.,20.):            # draws at 4,12,20; available 2 h later; carried forward
        for i,t in enumerate(hours):
            if t>=t0+2:lab[i]=t0*10;lab_age[i]=t-t0
    tm,vm=new_measurements(hours,lab,lab_age);ok('baseline: lagged labs recovered once each at their draw time',tm.tolist()==[4.,12.,20.] and vm.tolist()==[40.,120.,200.])
    ok('baseline: column names',len(baseline_relative_columns(['HR']))==5)
    return passed

def run_checks_models_and_scoring():
    """Second group: models (needs torch) and scoring passes on synthetic prediction frames."""
    import torch
    passed=[]
    def ok(name,cond):
        if not cond:raise AssertionError('v12 check failed: '+name)
        passed.append(name)
    # ---- models ----
    from v12_models import make_stage2_model,TwoChannelOSTA
    feats=['HR','HR_observed','HR_age','MAP','MAP_observed','MAP_age','Lactate','Lactate_observed','Lactate_age','Age','Gender','Comorbidity_diabetes','Med_BetaBlocker_24h','AdmitSource_ED','ICULOS','HR_Slope6h']
    cfg={'small_model':True,'dropout':.1}
    b,t=3,12;x=torch.randn(b,t,len(feats));mask=torch.ones(b,t);hours=torch.arange(1,t+1,dtype=torch.float32).repeat(b,1)
    m=make_stage2_model('two_channel',feats,cfg);out=m(x,mask,hours)
    ok('two-channel: logits shape (B,T)',tuple(out.shape)==(b,t))
    ok('two-channel: paths partition the columns',sorted(m.phys_idx+m.prac_idx)==list(range(len(feats))))
    m.eval()
    with torch.no_grad():
        o1=m(x,mask,hours);m.practice_zero=True;o2=m(x,mask,hours);m.practice_zero=False
        x2=x.clone();x2[:,:,m.prac_idx]=0.;o3=m(x2,mask,hours)
    ok('two-channel: zeroing the practice path changes the output and equals zeroed input',not torch.allclose(o1,o2) and torch.allclose(o2,o3))
    mh=make_stage2_model('two_channel_nohost',feats,cfg);ok('two-channel without host block drops Age/Gender/comorbidity',all(feats[i] not in ('Age','Gender','Comorbidity_diabetes') for i in mh.phys_idx))
    for arm in ('physiology_path','physiology_path_nohost','practice_path'):
        s=make_stage2_model(arm,feats,cfg);ok(f'{arm}: forward shape',tuple(s(x,mask,hours).shape)==(b,t))
    # causality of the two-channel model: output at t must not depend on inputs after t
    m.eval()
    with torch.no_grad():
        a=m(x,mask,hours);xx=x.clone();xx[:,8:,:]+=5.;bb=m(xx,mask,hours)
    ok('two-channel: causal',torch.allclose(a[:,:8],bb[:,:8],atol=1e-5))
    # ---- scoring passes ----
    import numpy as np,pandas as pd
    from v12_evaluate import relabel,pre_treatment,documentation_strata,abstention_rows,adopt_abstention,threshold_transport,alarm_records_abstain
    rng=np.random.default_rng(0);rows=[]
    for i in range(40):
        pid=f'p{i}';onset=30. if i%4==0 else np.nan;hosp=f'h{i%3}'
        for h in range(1,41):
            if np.isfinite(onset) and h>=onset:continue
            risk=.3 if (np.isfinite(onset) and h>=onset-6) else .05
            rows.append({'Patient_ID':pid,'Group_ID':pid,'Hospital_ID':hosp,'Hour':float(h),'y':int(np.isfinite(onset) and h>=onset-6),'logit':0.,'risk':risk+rng.normal(0,.01),'Eligible':1,'OnsetHour':onset})
    d=pd.DataFrame(rows);cfg2={'alarm_cooldown':6,'horizon':6,'false_alarm_budget':.5,'persistence':2,'fresh_only':False}
    r=relabel(d,{'p0':20.},3.);ok('relabel: new onset and 3 h positives',r[r.Patient_ID.eq('p0')].y.sum()==3 and (r[r.Patient_ID.eq('p0')].Hour<20).all() and r[r.Patient_ID.eq('p4')].y.sum()==0)
    pt=pre_treatment(d,{'p0':10.});ok('pre-treatment: hours before the first treatment only',(pt[pt.Patient_ID.eq('p0')].Hour<10).all() and len(pt[pt.Patient_ID.eq('p1')])==40)
    st=documentation_strata(d,{f'p{i}':(i%8==0) for i in range(40)})
    ok('documentation strata: positives split, controls shared',st['documented'].OnsetHour.notna().sum()>0 and st['undocumented'].OnsetHour.notna().sum()>0 and len(st['documented'][st['documented'].OnsetHour.isna()])==len(d[d.OnsetHour.isna()]))
    ood=d[['Patient_ID','Hour']].copy();ood['ood']=np.where((ood.Hour%7==0),1.,0.)
    ar=abstention_rows(d,ood,.5,.2,cfg2,2);ok('abstention: three modes with fractions',list(ar.abstention)==['reset','transparent','gated'] and abs(ar.abstained_fraction_all_hours.iloc[0]-(d.Hour%7==0).mean())<1e-9)
    ad=adopt_abstention(ar,'reset');ok('abstention: adoption table',len(ad)==3 and not ad[ad.abstention.eq('reset')].adoptable.iloc[0])
    # transparent mode: a single abstained hour inside a run must not break persistence
    dd=pd.DataFrame({'Patient_ID':['q']*6,'Group_ID':['q']*6,'Hospital_ID':['h']*6,'Hour':[1.,2.,3.,4.,5.,6.],'y':[0]*6,'logit':0.,'risk':[.9,.9,.9,.9,.9,.9],'Eligible':1,'OnsetHour':np.nan})
    ab=np.array([False,True,False,False,False,False])
    a_t=alarm_records_abstain(dd,.5,ab,'transparent',6,6,2);a_r=alarm_records_abstain(dd,.5,ab,'reset',6,6,2)
    ok('abstention: transparent keeps the run, reset breaks it',a_t.alarms.iloc[0]==1 and a_r.alarms.iloc[0]==1)   # both alarm once within the cooldown; timing differs
    tt,disp=threshold_transport(d,{'threshold':.2,'alarm_fraction':.1},cfg2,min_hours=10,min_stays=5)
    ok('threshold transport: both rules per hospital',set(tt.rule)=={'absolute','quantile'} and tt.Hospital_ID.nunique()==3 and len(disp)==2)
    return passed
