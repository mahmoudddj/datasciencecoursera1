# %% MD
## 7. Pathophysiology study (protocol section 10c.1; revised design of 29 Oct 2026, under the partner's review)
Descriptive only; no model is trained. **Training-split and non-cohort patients only**: validation, test and protected patients are never read.

Four septic strata and controls: *incident* (ICU-acquired, onset at or after the sixth ICU hour; cohort, train and observer-fit splits), *septic on arrival* (onset at or before ICU hour 0), *early ICU onset* (onset in hours 0 to 6; both from the stays excluded by YAIB exclusion 7, hourly features from the unlabelled corpus, onset from the label batches), *controls* (no onset; a seeded sample). Every septic stay also carries a **course**: deteriorating, improving or indeterminate, from hospital mortality (raw admission tables) and the paired change of SOFA components and vasopressor dose from onset to onset + 48 h (72 h as sensitivity). Controls receive a **pseudo-onset** drawn from the incident onset distribution, so that every onset-relative comparison is matched on time since admission.

Only *fresh* measurements are used for values: each newly available measurement once, placed at its own measurement time (so laboratory results are not lost to their result lag, and carried-forward values never manufacture a trajectory); measurement frequency is reported separately as the practice signal. Beyond the prespecified comparisons the study lets the data speak: when each sign departs, the order of signs within patients, data-driven phenotypes at onset, compensation states, therapy-stratified reads, selection checks and hospital heterogeneity. Every output is aggregate; counts under 11 are masked (-1).
# %% CODE
# 7a. Strata, onset times, outcomes from the raw tables, and the stay manifest
from v10_protocol import partition,protected_group
import duckdb
PATHO_KEY=signature({'data':DATA_KEY,'ssl':globals().get('SSL_KEY','fixture'),'cohort':globals().get('COHORT_KEY','fixture'),'protocol':'10c-1-rev2'})[:16]
PATHO_ROOT=VALIDATION_ROOT/'pathophysiology'/PATHO_KEY;PATHO_ROOT.mkdir(parents=True,exist_ok=True)
SMALL_CELL=11
FIXTURE=DATA_SOURCE!='clinical'
COURSE_HORIZONS=[48,72] if not FIXTURE else [6]     # hours after onset at which the course is read (primary first)
PRIMARY_COURSE_H=COURSE_HORIZONS[0]
DET_PRESSOR_MIN=0.1        # norepinephrine-equivalent dose (mcg/kg/min) at the course hour that counts as escalation when above the onset dose
CONTROL_CAP=3000           # controls read per database (seeded sample); every septic stay is read
PRE_WINDOW=48;POST_WINDOW=max(COURSE_HORIZONS)+2
STRATA=['incident','septic_on_arrival','early_icu_onset','control']
def _hours(v):
    if pd.api.types.is_timedelta64_dtype(v):return v.dt.total_seconds()/3600.0
    return pd.to_numeric(v,errors='coerce')
def candidate_onsets(ds):
    """Operational onset (hours from ICU admission) of EVERY sampled candidate with a sep3_alt event, from the cached
    unwindowed label batches (the same source as resolve_onsets): the event hour is the `time` column of rows whose
    sep3_alt is not missing. Negative hours = onset before ICU admission."""
    if FIXTURE:
        z=INDEX[INDEX.Dataset.eq(ds)];return pd.DataFrame({'Patient_ID':z.Patient_ID,'onset_h':z.OnsetHour.astype(float)})
    parts=[]
    for p in sorted((COHORT_ROOT/ds/'batches').rglob('labels.parquet')):
        d=pd.read_parquet(p)
        if not {'stay_id','time','sep3_alt'}<=set(d.columns):continue
        d=d[d.sep3_alt.notna()]
        if len(d):parts.append(pd.DataFrame({'stay_id':d.stay_id.astype('int64'),'onset_h':_hours(d.time)}))
    if not parts:return pd.DataFrame(columns=['Patient_ID','onset_h'])
    on=pd.concat(parts,ignore_index=True).groupby('stay_id',as_index=False).onset_h.min()
    on['Patient_ID']=ds+'|'+on.stay_id.astype(str);return on[['Patient_ID','onset_h']]
def raw_outcomes(ds,ids):
    """Hospital and ICU mortality, discharge timing and sepsis documentation for the manifest stays, from the SMALL raw
    tables only (icustays/admissions/diagnoses_icd; patient/diagnosis). Retrospective: used to describe, never to predict."""
    ids=list(ids)
    if FIXTURE:
        rng=np.random.default_rng(7);n=len(ids)
        return pd.DataFrame({'Patient_ID':ids,'hospital_death':(rng.random(n)<.2).astype(float),'icu_death':0.,'death_hour':np.nan,'icu_los_h':24.,
                             'hospital_los_h':48.,'admitted_for_sepsis_dx':(rng.random(n)<.3).astype(float),'sepsis_documented':(rng.random(n)<.4).astype(float),'source':'FIXTURE synthetic outcomes'})
    from v9_data import csv_scan,table,q
    root=Path(resolved_raw[ds]);con=duckdb.connect();con.execute("SET memory_limit='4GB'")
    sid=pd.DataFrame({'stay_id':[int(str(p).split('|')[1]) for p in ids],'Patient_ID':ids});con.register('chosen',sid[['stay_id']])
    try:
        if ds=='miiv':
            icu=csv_scan(table(root,'icu/icustays',True),True);adm=csv_scan(table(root,'hosp/admissions',True),True)
            d=con.execute(f'''SELECT CAST(x.stay_id AS BIGINT) AS "stay_id",TRY_CAST(a.hospital_expire_flag AS DOUBLE) AS "hospital_death",
                 epoch(TRY_CAST(a.deathtime AS TIMESTAMP)-TRY_CAST(x.intime AS TIMESTAMP))/3600.0 AS "death_hour",
                 epoch(TRY_CAST(x.outtime AS TIMESTAMP)-TRY_CAST(x.intime AS TIMESTAMP))/3600.0 AS "icu_los_h",
                 epoch(TRY_CAST(a.dischtime AS TIMESTAMP)-TRY_CAST(x.intime AS TIMESTAMP))/3600.0 AS "hospital_los_h"
                 FROM {icu} x JOIN chosen c ON TRY_CAST(x.stay_id AS BIGINT)=c.stay_id LEFT JOIN {adm} a ON a.hadm_id=x.hadm_id''').df()
            d['icu_death']=(d.death_hour.notna()&(d.death_hour<=d.icu_los_h+1)).astype(float)
            d['admitted_for_sepsis_dx']=np.nan   # MIMIC-IV records no admission diagnosis at ICU entry
            dx=table(root,'hosp/diagnoses_icd')
            if dx:
                z=con.execute(f'''SELECT DISTINCT CAST(x.stay_id AS BIGINT) AS "stay_id" FROM {icu} x JOIN chosen c ON TRY_CAST(x.stay_id AS BIGINT)=c.stay_id
                     JOIN {csv_scan(dx,True)} g ON g.hadm_id=x.hadm_id
                     WHERE regexp_matches(upper(replace(coalesce(g.icd_code,''),'.','')),'^(A4[01]|R652|038|99591|99592|78552)')''').df()
                d['sepsis_documented']=d.stay_id.isin(set(z.stay_id)).astype(float)   # sepsis coded for the hospital admission (discharge coding)
            else:d['sepsis_documented']=np.nan
        else:
            pt=csv_scan(table(root,'patient',True),True)
            d=con.execute(f'''SELECT CAST(x.patientunitstayid AS BIGINT) AS "stay_id",
                 CASE lower(coalesce(x.hospitaldischargestatus,'')) WHEN 'expired' THEN 1.0 WHEN 'alive' THEN 0.0 END AS "hospital_death",
                 CASE lower(coalesce(x.unitdischargestatus,'')) WHEN 'expired' THEN 1.0 WHEN 'alive' THEN 0.0 END AS "icu_death",
                 TRY_CAST(x.unitdischargeoffset AS DOUBLE)/60 AS "icu_los_h",TRY_CAST(x.hospitaldischargeoffset AS DOUBLE)/60 AS "hospital_los_h",
                 CASE WHEN lower(coalesce(x.apacheadmissiondx,'')) LIKE '%sepsis%' THEN 1.0 ELSE 0.0 END AS "admitted_for_sepsis_dx"
                 FROM {pt} x JOIN chosen c ON TRY_CAST(x.patientunitstayid AS BIGINT)=c.stay_id''').df()
            d['death_hour']=np.where(d.icu_death.eq(1),d.icu_los_h,np.where(d.hospital_death.eq(1),d.hospital_los_h,np.nan))
            dg=table(root,'diagnosis')
            if dg:
                z=con.execute(f'''SELECT DISTINCT TRY_CAST(g.patientunitstayid AS BIGINT) AS "stay_id" FROM {csv_scan(dg,True)} g JOIN chosen c ON TRY_CAST(g.patientunitstayid AS BIGINT)=c.stay_id
                     WHERE lower(coalesce(g.diagnosisstring,'')) LIKE '%sepsis%' OR lower(coalesce(g.diagnosisstring,'')) LIKE '%septic%' ''').df()
                d['sepsis_documented']=d.stay_id.isin(set(z.stay_id)).astype(float)   # sepsis in the ICU diagnosis list (any time of the stay)
            else:d['sepsis_documented']=np.nan
    finally:con.close()
    d=sid.merge(d,on='stay_id',how='left');d['source']='raw tables';return d.drop(columns='stay_id')
RNG=np.random.default_rng(RANDOM_STATE);GROUPS={};COVER=[]
for ds in DATASETS:
    mf=partition(INDEX,ds,TRAIN_CONFIG);dev=mf[mf.split.isin(['train','observer_fit'])].copy()   # never validation, test or protected
    inc=dev[dev.eligible_positive.eq(1)&dev.OnsetHour.ge(6)].copy();inc['stratum']='incident';inc['onset_h']=inc.OnsetHour.astype(float)
    ctl=dev[dev.OnsetHour.isna()].copy();ctl['stratum']='control';ctl['onset_h']=np.nan
    n_ctl_all=len(ctl)
    if len(ctl)>CONTROL_CAP:ctl=ctl.sample(CONTROL_CAP,random_state=RANDOM_STATE)
    on=candidate_onsets(ds);early=on[on.onset_h.notna()&(on.onset_h<6)].copy()
    corp=CORPUS.get(ds)
    if FIXTURE and corp is not None:   # engineering only: synthetic early onsets on non-development fixture stays, to exercise every code path
        pool=corp[~corp.Patient_ID.isin(set(dev.Patient_ID))]
        early=pd.DataFrame({'Patient_ID':pool.Patient_ID.to_numpy(),'onset_h':RNG.choice([-30.,-4.,0.,2.,4.5],len(pool))})
        print(ds,'FIXTURE: synthetic early onsets assigned to',len(early),'non-development stays (engineering only, no clinical meaning)')
    arrived=pd.DataFrame(columns=list(inc.columns))
    if corp is not None and len(corp) and len(early):
        prev=corp[corp.Patient_ID.isin(set(early.Patient_ID))&~corp.Patient_ID.isin(set(dev.Patient_ID))].copy()
        prev=prev[~prev.Group_ID.map(protected_group)]   # the corpus already excludes protected patients; keep the guard
        prev=prev.merge(early,on='Patient_ID',how='left');prev['stratum']=np.where(prev.onset_h<=0,'septic_on_arrival','early_icu_onset');arrived=prev
    g=pd.concat([inc,arrived,ctl],ignore_index=True);g['Dataset']=ds
    # Pseudo-onset for controls: drawn from the incident onset distribution of the same database, inside the control's follow-up.
    g['pseudo_onset']=np.nan;io=inc.onset_h.to_numpy(float);cm=g.stratum.eq('control').to_numpy()
    if len(io) and cm.any():
        fe=g.loc[cm,'followup_end'].to_numpy(float);draw=RNG.choice(io,cm.sum())
        for _ in range(20):
            bad=draw>fe
            if not bad.any():break
            draw[bad]=RNG.choice(io,int(bad.sum()))
        g.loc[cm,'pseudo_onset']=np.minimum(draw,fe)
    g['anchor']=g.onset_h.where(g.stratum.ne('control'),g.pseudo_onset)
    g=g.merge(raw_outcomes(ds,g.Patient_ID),on='Patient_ID',how='left')
    GROUPS[ds]=g
    found=int(len(arrived));cnt=g.groupby('stratum').size().to_dict()
    COVER.append({'Dataset':ds,'incident':cnt.get('incident',0),'septic_on_arrival':cnt.get('septic_on_arrival',0),'early_icu_onset':cnt.get('early_icu_onset',0),
                  'controls_read':cnt.get('control',0),'controls_available':n_ctl_all,'candidates_with_onset_before_6h':int(len(early)),
                  'of_which_in_corpus':found,'outcome_source':g.source.dropna().iloc[0] if g.source.notna().any() else 'none'})
COVER=pd.DataFrame(COVER);display(COVER.set_index('Dataset').T)
MANIFEST=pd.concat(GROUPS.values(),ignore_index=True);MANIFEST['stay']=np.arange(len(MANIFEST))
if not FIXTURE and (MANIFEST.loc[MANIFEST.stratum.ne('control'),'onset_h'].isna().any()):raise AssertionError('Septic stay without onset hour')
pub=MANIFEST[['stay','Dataset','stratum','onset_h','pseudo_onset','hospital_death','icu_death','admitted_for_sepsis_dx','sepsis_documented']].copy()
pub.to_parquet(PATHO_ROOT/'manifest_no_ids.parquet',index=False)   # no stay ids, no file paths
sep=MANIFEST[MANIFEST.stratum.ne('control')]
def _frac(s):return float(s.mean()) if s.notna().sum()>=SMALL_CELL else np.nan
print('\nSepsis documentation versus the operational onset (fractions; masked when fewer than 11 stays):')
display(sep.groupby(['Dataset','stratum']).agg(stays=('stay','size'),hospital_mortality=('hospital_death',_frac),icu_mortality=('icu_death',_frac),
    admitted_for_sepsis_dx=('admitted_for_sepsis_dx',_frac),sepsis_documented=('sepsis_documented',_frac),onset_h_median=('onset_h','median')).round(3))
print('Control hospital mortality:',MANIFEST[MANIFEST.stratum.eq('control')].groupby('Dataset').hospital_death.apply(_frac).round(3).to_dict())
# %% CODE
# 7b. One pass over the hourly shards (grouped by file): fresh (newly available) values at their measurement time, hourly states, static context, onset state, course
VALUE_CH=[c for c in ['HR','Temp','Resp','SBP','DBP','MAP','O2Sat','GCS','Lactate','WBC','Bands','Neutrophils','Lymphocytes','Platelets','Creatinine','BUN','Bilirubin_total',
                      'pH','HCO3','BaseExcess','AnionGap','PaO2','PaCO2','FiO2','Glucose','Hgb','Sodium','Potassium','Chloride','CRP','Procalcitonin','INR','PTT','Fibrinogen','DDimer','Albumin','AST','ALT','Troponin'] if c in FEATURES and c+'_age' in FEATURES]
WINDOW_CH=[c for c in ['UrineOutput_6h','Urine_mlkg_h_6h','UrineCoverage_6h','Oliguria6h','FluidIn_6h','FluidIn_24h','NetBalance_24h','Temp_Max24h','Temp_Min24h','HR_Variance6h','HR_Slope6h','Resp_Slope6h',
                       'Platelets_DeltaBaseline','Creatinine_DeltaBaseline','Lactate_DeltaPrev','ShockIndex','PulsePressure','SF_Ratio','PF_Ratio','NLR','GCS_Below15','SupplementalO2','AKI_Stage'] if c in FEATURES]
SOFA_COMP=[c for c in ['SOFA_Resp','SOFAproxy_Coag','SOFAproxy_Liver','SOFA_CV','SOFAproxy_CNS','SOFA_Renal'] if c in FEATURES]
SOFA_CH=SOFA_COMP+[c for c in ['SOFA_Total','SOFA_MetAmongMeasured','SOFA_Available','SOFA_Delta','qSOFA_MetAmongMeasured','NEWS2_MetAmongMeasured'] if c in FEATURES]
THERAPY_CH=[c for c in ['VasopressorRecorded','VasopressorDose_NEeq','InotropeRecorded','Intubated','O2_NIV','O2_HighFlow','RASS','Delirium','Transfusion_24h','Procedure_RRT_24h','Imaging_24h','LabResults_24h',
                        'Med_Corticosteroid_24h','Med_Hydrocortisone_24h','Med_BetaBlocker_24h','Med_Antipyretic_24h','Med_Sedative_24h','Med_Opioid_24h','Med_Diuretic_24h','Med_Insulin_24h','Med_Anticoagulant_24h',
                        'Nutrition_TPN_24h','Nutrition_Enteral_24h','Device_CentralLine','Device_UrinaryCatheter','Device_ArterialLine','IntubatedHours','Device_CentralLine_Hours'] if c in FEATURES]
CARRIED_CH=[c for c in ['HR','Resp','MAP','SBP','Temp','GCS','O2Sat'] if c in FEATURES]   # last-known values for hourly states
STATIC_CH=[c for c in ['Age','Gender','Weight','HospitalHoursBeforeICU','AdmitSource_ED','AdmitSource_OR','AdmitSource_Ward','AdmitSource_OtherHospital','ICUType_Medical','ICUType_Surgical','ICUType_Cardiac','ICUType_Neuro',
                       'AdmitDx_Infection','AdmitDx_Operative','PriorAntibiotics_90d','PriorPositiveCulture_1y'] if c in FEATURES]
COMORB_CH=[c for c in FEATURES if c.startswith('Comorbidity_')]
STATE_CH=VALUE_CH+[c for c in ['Urine_mlkg_h_6h','VasopressorDose_NEeq','VasopressorRecorded','ShockIndex','PulsePressure','SF_Ratio','NLR','Platelets_DeltaBaseline','Creatinine_DeltaBaseline','SOFA_MetAmongMeasured','SOFA_Available'] if c in FEATURES]
NEED=sorted(set(['Hour']+VALUE_CH+[c+'_age' for c in VALUE_CH]+WINDOW_CH+SOFA_CH+THERAPY_CH+CARRIED_CH+STATIC_CH+COMORB_CH))
FR=[];HO=[];ST=[];OS=[]
t0=time.time()
for file,grp in MANIFEST.groupby('file'):
    d=pd.read_parquet(file,columns=NEED)
    for k,row in grp.iterrows():
        s=d.iloc[int(row.offset):int(row.offset+row.length)]
        if s.empty:continue
        a=float(row.anchor) if pd.notna(row.anchor) else np.nan
        rel=s.Hour.to_numpy(float)-a if np.isfinite(a) else np.full(len(s),np.nan)
        keep=(s.Hour.to_numpy(float)<=30)|((rel>=-PRE_WINDOW)&(rel<=POST_WINDOW)) if np.isfinite(a) else (s.Hour.to_numpy(float)<=30)
        # static context (first hour) and comorbidity documentation (any hour)
        st={'stay':row.stay,**{c:float(s[c].iloc[0]) for c in STATIC_CH}};st.update({c:float(np.nanmax(s[c].to_numpy(float))) if s[c].notna().any() else np.nan for c in COMORB_CH});ST.append(st)
        # onset state: last-known values over hours [a-2, a] (hours 1-3 when onset is at or before admission)
        if np.isfinite(a):
            lo,hi=(1,3) if a<=0 else (max(1.,np.floor(a)-2),np.floor(a))
            w=s[(s.Hour>=lo)&(s.Hour<=hi)]
            if len(w):
                last=w[STATE_CH].ffill().iloc[-1].to_dict();last['stay']=row.stay;OS.append(last)
        s=s[keep];rel=rel[keep]
        if s.empty:continue
        h=s[['Hour']+CARRIED_CH+SOFA_CH+THERAPY_CH+WINDOW_CH].copy();h['rel']=rel;h['stay']=row.stay;HO.append(h)
        # A measurement is NEW at hour t when its age did not simply grow by one hour since t-1 (first appearance or a reset);
        # it is placed at its own measurement time (t - age), so laboratory values are not lost to their result lag.
        full=d.iloc[int(row.offset):int(row.offset+row.length)];full_vals=full[VALUE_CH].to_numpy(float);full_ages=full[[c+'_age' for c in VALUE_CH]].to_numpy(float)
        prev=np.vstack([np.full((1,full_ages.shape[1]),np.nan),full_ages[:-1]])
        new_meas=np.isfinite(full_ages)&np.isfinite(full_vals)&(~np.isfinite(prev)|(full_ages<prev+1-1e-3))
        new_meas=new_meas[keep];vals=full_vals[keep];ages=full_ages[keep];ri,ci=np.nonzero(new_meas)
        if len(ri):
            mh=s.Hour.to_numpy(float)[ri]-ages[ri,ci]
            FR.append(pd.DataFrame({'stay':row.stay,'channel':np.array(VALUE_CH,dtype=object)[ci],'Hour':mh,'rel':(mh-a) if np.isfinite(a) else np.nan,'value':vals[ri,ci]}))
FRESH=pd.concat(FR,ignore_index=True) if FR else pd.DataFrame(columns=['stay','channel','Hour','rel','value']);del FR
HOURLY=pd.concat(HO,ignore_index=True) if HO else pd.DataFrame(columns=['stay','Hour','rel']);del HO
STATIC=pd.DataFrame(ST).set_index('stay') if ST else pd.DataFrame();ONSET_STATE=pd.DataFrame(OS).set_index('stay') if OS else pd.DataFrame()
KEYS=MANIFEST.set_index('stay')[['Dataset','stratum','anchor','onset_h','followup_end','hospital_death','icu_death','icu_los_h','death_hour']]
for T in (FRESH,HOURLY):
    for c in ['Dataset','stratum']:T[c]=T.stay.map(KEYS[c])
print(f'Read {MANIFEST.file.nunique()} shard files in {time.time()-t0:.0f} s | hourly rows {len(HOURLY):,} | fresh values {len(FRESH):,} | stays with onset state {len(ONSET_STATE):,}')
# ---- course: paired SOFA components and vasopressor dose from the onset state to onset + H ----
def window_max(stays_hours,lo,hi,cols):
    z=stays_hours[(stays_hours.Hour>=lo)&(stays_hours.Hour<=hi)]
    return z[cols].max(skipna=True) if len(z) else pd.Series(np.nan,index=cols)
def course_row(r,hh,H):
    a=r.anchor;lo0,hi0=(1,3) if a<=0 else (max(1.,np.floor(a)-2),np.floor(a));loH,hiH=lo0+H if a<=0 else a+H-2,hi0+H if a<=0 else a+H
    cols=SOFA_COMP+['VasopressorRecorded','VasopressorDose_NEeq'];m0=window_max(hh,lo0,hi0,cols);mH=window_max(hh,loH,hiH,cols)
    both=[c for c in SOFA_COMP if pd.notna(m0[c]) and pd.notna(mH[c])]
    dsofa=float(sum(mH[c]-m0[c] for c in both)) if len(both)>=4 else np.nan
    out={'stay':r.name,f'dsofa_{H}':dsofa,f'sofa_components_paired_{H}':len(both),f'pressor_{H}':float(mH.get('VasopressorRecorded',np.nan)),
         f'dose0':float(m0.get('VasopressorDose_NEeq',np.nan)),f'dose_{H}':float(mH.get('VasopressorDose_NEeq',np.nan)),'sofa0_among_measured':float(np.nansum([m0[c] for c in SOFA_COMP])) if any(pd.notna(m0[c]) for c in SOFA_COMP) else np.nan}
    end=r.icu_los_h if pd.notna(r.icu_los_h) else r.followup_end
    dead=r.hospital_death
    if dead==1:c='deteriorating'
    elif pd.isna(dsofa):c='left_icu_alive_before_horizon' if (pd.notna(end) and end<a+H and dead==0) else 'indeterminate'
    elif dsofa>=2:c='deteriorating'
    elif (out[f'pressor_{H}']==1) and pd.notna(out[f'dose_{H}']) and out[f'dose_{H}']>=DET_PRESSOR_MIN and (pd.isna(out['dose0']) or out[f'dose_{H}']>out['dose0']):c='deteriorating'
    elif dsofa<=0 and out[f'pressor_{H}']!=1 and dead==0:c='improving'
    else:c='indeterminate'
    out[f'course_{H}']=c;return out
sep_ids=KEYS[KEYS.stratum.ne('control')].index
HH={s:g for s,g in HOURLY[HOURLY.stay.isin(sep_ids)].groupby('stay')}
COURSE=pd.DataFrame([{**course_row(KEYS.loc[s],HH.get(s,HOURLY.iloc[:0]),H)} for s in sep_ids for H in COURSE_HORIZONS]).groupby('stay').first() if len(sep_ids) else pd.DataFrame()
if len(COURSE):
    for H in COURSE_HORIZONS:
        c=COURSE[f'course_{H}'];COURSE[f'course2_{H}']=np.where(c.eq('deteriorating'),'deteriorating',np.where(c.isin(['improving','left_icu_alive_before_horizon']),'improving',None))
    MANIFEST=MANIFEST.merge(COURSE.reset_index(),on='stay',how='left')
    MANIFEST['course']=MANIFEST[f'course_{PRIMARY_COURSE_H}'];MANIFEST['course2']=MANIFEST[f'course2_{PRIMARY_COURSE_H}']
else:MANIFEST['course']=None;MANIFEST['course2']=None
KEYS=MANIFEST.set_index('stay')[['Dataset','stratum','anchor','onset_h','followup_end','hospital_death','icu_death','icu_los_h','death_hour','course','course2']]
for T in (FRESH,HOURLY):T['course2']=T.stay.map(KEYS.course2)
def masked_crosstab(a,b):
    t=pd.crosstab(a,b);return t.where(t>=SMALL_CELL,-1)
print(f'\nCourse at onset + {PRIMARY_COURSE_H} h (deteriorating = hospital death, or paired SOFA-component rise >= 2, or vasopressor escalation to >= {DET_PRESSOR_MIN} NE-eq; improving = alive, no rise, no vasopressor; counts under 11 masked):')
sepm=MANIFEST[MANIFEST.stratum.ne('control')]
for ds in DATASETS:display(masked_crosstab(sepm[sepm.Dataset.eq(ds)].stratum,sepm[sepm.Dataset.eq(ds)].course).rename_axis(index=ds))
if len(COURSE_HORIZONS)>1:
    agree=(sepm[f'course2_{COURSE_HORIZONS[0]}']==sepm[f'course2_{COURSE_HORIZONS[1]}'])[sepm[f'course2_{COURSE_HORIZONS[0]}'].notna()&sepm[f'course2_{COURSE_HORIZONS[1]}'].notna()]
    print(f'Two-way course agreement between {COURSE_HORIZONS[0]} h and {COURSE_HORIZONS[1]} h: {agree.mean():.3f} of {len(agree)} stays' if len(agree) else 'Course agreement: not estimable')
MANIFEST[['stay','Dataset','stratum','course','course2']+[c for c in MANIFEST if c.startswith(('dsofa_','course_','course2_','pressor_','dose'))]].to_parquet(PATHO_ROOT/'course_no_ids.parquet',index=False)
# admission context by stratum (fractions among known; masked)
ctx=STATIC.join(KEYS[['Dataset','stratum']])
def frac_known(s):return float(s.mean()) if s.notna().sum()>=SMALL_CELL else np.nan
CTX=ctx.groupby(['Dataset','stratum']).agg({**{c:frac_known for c in STATIC_CH if c not in ('Age','Weight','HospitalHoursBeforeICU')},**{c:'median' for c in ['Age','HospitalHoursBeforeICU'] if c in ctx},**{c:frac_known for c in COMORB_CH}}).round(3)
CTX.to_csv(PATHO_ROOT/'admission_context_by_stratum.csv');print('\nAdmission context and comorbidity documentation by stratum (fractions; medians for Age and hours in hospital before the ICU):');display(CTX.T)
# %% CODE
# 7c. Trajectories, the prespecified comparisons (rank-based Cliff's delta, stay bootstrap), cross-database rule, measurement rates
CARRY_LONG=[c for c in ['Urine_mlkg_h_6h','Temp_Max24h','Temp_Min24h','ShockIndex','PulsePressure','SF_Ratio','NLR','VasopressorDose_NEeq','HR_Variance6h','Platelets_DeltaBaseline','Creatinine_DeltaBaseline']+SOFA_COMP+['SOFA_MetAmongMeasured','qSOFA_MetAmongMeasured','NEWS2_MetAmongMeasured'] if c in HOURLY]
CHANNELS=VALUE_CH+CARRY_LONG
_cl=HOURLY.melt(id_vars=['stay','Hour','rel','Dataset','stratum','course2'],value_vars=CARRY_LONG,var_name='channel',value_name='value').dropna(subset=['value'])
_cl['kind']='carried/window';FRESH['kind']='fresh'
LONG=pd.concat([FRESH,_cl],ignore_index=True);del _cl
BINS=[(a,a+4) for a in range(-48,72,4)];ADM_BINS=[(1,4),(5,8),(9,12),(13,16),(17,20),(21,24),(25,30)]
def binned(x,bins):
    lab=pd.Series(pd.NA,index=x.index,dtype='object')
    for a,b in bins:lab[(x>=a)&(x<b)]=f'{a}..{b}'
    return lab
LONG['bin_onset']=binned(LONG.rel,BINS);LONG['bin_adm']=binned(LONG.Hour,ADM_BINS)
HOURLY['bin_onset']=binned(HOURLY.rel,BINS);HOURLY['bin_adm']=binned(HOURLY.Hour,ADM_BINS)
def q25(s):return s.quantile(.25)
def q75(s):return s.quantile(.75)
def trajectories(bincol,by=('Dataset','stratum')):
    by=list(by)
    v=LONG.dropna(subset=[bincol]).groupby(by+['channel','kind',bincol]).agg(n_stays=('stay','nunique'),n_values=('value','size'),median=('value','median'),q25=('value',q25),q75=('value',q75)).reset_index()
    h=HOURLY.dropna(subset=[bincol]).groupby(by+[bincol]).agg(stay_hours=('Hour','size')).reset_index()
    v=v.merge(h,on=by+[bincol],how='left');v['measurements_per_stay_hour']=np.where(v.kind.eq('fresh'),v.n_values/v.stay_hours,np.nan)
    v['x']=v[bincol].str.split('..',regex=False).str[0].astype(int)
    for c in ['n_stays','n_values']:v[c]=v[c].where(v[c]>=SMALL_CELL,-1)
    return v.sort_values(by+['channel','x'])
TRAJ_ONSET=trajectories('bin_onset');TRAJ_ADM=trajectories('bin_adm')
TRAJ_COURSE=trajectories('bin_onset',by=('Dataset','stratum','course2'))
TRAJ_ONSET.to_csv(PATHO_ROOT/'trajectories_relative_to_onset.csv',index=False);TRAJ_ADM.to_csv(PATHO_ROOT/'trajectories_since_admission.csv',index=False);TRAJ_COURSE.to_csv(PATHO_ROOT/'trajectories_by_course.csv',index=False)
# ---- per-stay windows and rank-based Cliff's delta ----
def stay_window(stratum,lo,hi,by='rel',stat='median',course2=None,channels=None):
    """Per-stay summary of values inside [lo,hi) hours (by='rel': relative to the onset or pseudo-onset; 'Hour': since ICU admission)."""
    sel=LONG[LONG.stratum.eq(stratum)&(LONG[by]>=lo)&(LONG[by]<hi)] if isinstance(stratum,str) else LONG[LONG.stratum.isin(stratum)&(LONG[by]>=lo)&(LONG[by]<hi)]
    if course2 is not None:sel=sel[sel.course2.eq(course2)]
    if channels is not None:sel=sel[sel.channel.isin(channels)]
    if stat=='median':return sel.groupby(['Dataset','channel','stay'],as_index=False).value.median()
    rows=[]
    for (ds,ch,st),g in sel.groupby(['Dataset','channel','stay']):
        if len(g)>=3 and g[by].nunique()>=2:rows.append({'Dataset':ds,'channel':ch,'stay':st,'value':float(np.polyfit(g[by].to_numpy(float),g.value.to_numpy(float),1)[0])})
    return pd.DataFrame(rows,columns=['Dataset','channel','stay','value'])
def _rank(a):
    order=np.argsort(a,kind='mergesort');s=a[order];_,inv,cnt=np.unique(s,return_inverse=True,return_counts=True)
    start=np.cumsum(cnt)-cnt;r=np.empty(len(a));r[order]=(start+(cnt+1)/2)[inv];return r
def cliffs(x,y):
    """Cliff's delta = 2*AUC-1 from Mann-Whitney ranks (ties averaged); O((n+m) log(n+m))."""
    x=np.asarray(x,float);y=np.asarray(y,float);n,m=len(x),len(y)
    if n==0 or m==0:return np.nan
    r=_rank(np.concatenate([x,y]));return float(2*((r[:n].sum()-n*(n+1)/2)/(n*m))-1)
def compare(name,a,b,n_boot=200,seed=42,label_a='a',label_b='b'):
    rng=np.random.default_rng(seed);rows=[]
    for ds in DATASETS:
        for ch in CHANNELS:
            xa=a[(a.Dataset.eq(ds))&(a.channel.eq(ch))].value.dropna().to_numpy();xb=b[(b.Dataset.eq(ds))&(b.channel.eq(ch))].value.dropna().to_numpy()
            row={'comparison':name,'Dataset':ds,'channel':ch,'n_a':len(xa) if len(xa)>=SMALL_CELL else -1,'n_b':len(xb) if len(xb)>=SMALL_CELL else -1,'a':label_a,'b':label_b}
            if len(xa)<SMALL_CELL or len(xb)<SMALL_CELL:rows.append({**row,'delta':np.nan,'ci_low':np.nan,'ci_high':np.nan,'median_a':np.nan,'median_b':np.nan});continue
            d=cliffs(xa,xb);bs=np.array([cliffs(rng.choice(xa,len(xa)),rng.choice(xb,len(xb))) for _ in range(n_boot)])
            rows.append({**row,'delta':d,'ci_low':float(np.quantile(bs,.025)),'ci_high':float(np.quantile(bs,.975)),'median_a':float(np.median(xa)),'median_b':float(np.median(xb))})
    return pd.DataFrame(rows)
def classify(g):
    ok=g.delta.notna()
    if ok.sum()<2:return 'not estimable in both databases'
    s=np.sign(g.delta[ok]);m=g.delta[ok].abs()
    if s.nunique()==1 and (m>=.33).all():return 'strong shared'
    if s.nunique()==1 and (m>=.147).all():return 'shared'
    if (m>=.147).any():return 'database-specific'
    return 'no signal'
def with_class(comp):
    cl=comp.groupby(['comparison','channel']).apply(classify,include_groups=False).rename('cross_database').reset_index()
    return comp.merge(cl,on=['comparison','channel'],how='left')
SEPTIC=['incident','septic_on_arrival','early_icu_onset']
COMP=with_class(pd.concat([
    compare('C1 baseline: incident vs control, hours 1-24 since admission',stay_window('incident',1,25,'Hour'),stay_window('control',1,25,'Hour'),label_a='incident',label_b='control'),
    compare('C2 pre-onset signal: incident 12 h before onset vs control 12 h before pseudo-onset',stay_window('incident',-12,0),stay_window('control',-12,0),label_a='incident',label_b='control'),
    compare('C2b earlier pre-onset: incident 24-12 h before onset vs control matched',stay_window('incident',-24,-12),stay_window('control',-24,-12),label_a='incident',label_b='control'),
    compare('C3 septic on arrival (ICU hours 1-6) vs incident (onset to +6 h)',stay_window('septic_on_arrival',1,7,'Hour'),stay_window('incident',0,6),label_a='septic_on_arrival',label_b='incident'),
    compare('C4 early ICU onset (onset to +6 h) vs incident (onset to +6 h)',stay_window('early_icu_onset',0,6),stay_window('incident',0,6),label_a='early_icu_onset',label_b='incident'),
    compare('C5 septic on arrival (ICU hours 1-12) vs incident 12 h before onset',stay_window('septic_on_arrival',1,13,'Hour'),stay_window('incident',-12,0),label_a='septic_on_arrival',label_b='incident_pre_onset'),
    compare('C6 slope per hour: incident 12 h before onset vs control matched',stay_window('incident',-12,0,stat='slope'),stay_window('control',-12,0,stat='slope'),label_a='incident',label_b='control'),
    compare('C7 course: incident deteriorating vs improving, 12 h before onset',stay_window('incident',-12,0,course2='deteriorating'),stay_window('incident',-12,0,course2='improving'),label_a='deteriorating',label_b='improving'),
    compare('C8 course: septic on arrival deteriorating vs improving, ICU hours 1-6',stay_window('septic_on_arrival',1,7,'Hour',course2='deteriorating'),stay_window('septic_on_arrival',1,7,'Hour',course2='improving'),label_a='deteriorating',label_b='improving'),
    compare('C9 course: all septic deteriorating vs improving, onset +24 to +48 h',stay_window(SEPTIC,24,48,course2='deteriorating'),stay_window(SEPTIC,24,48,course2='improving'),label_a='deteriorating',label_b='improving'),
    compare('C10 course: all septic deteriorating vs improving, onset to +6 h',stay_window(SEPTIC,0,6,course2='deteriorating'),stay_window(SEPTIC,0,6,course2='improving'),label_a='deteriorating',label_b='improving'),
],ignore_index=True))
COMP.to_csv(PATHO_ROOT/'comparisons_cliffs_delta.csv',index=False)
# measurement rates (practice signal): values per stay-hour by stratum and window
def rate_window(stratum,lo,hi,by='rel'):
    sel=FRESH[FRESH.stratum.eq(stratum)&(FRESH[by]>=lo)&(FRESH[by]<hi)];hrs=HOURLY[HOURLY.stratum.eq(stratum)&(HOURLY[by]>=lo)&(HOURLY[by]<hi)].groupby('Dataset').size()
    r=sel.groupby(['Dataset','channel']).size().rename('n').reset_index();r['rate']=r.n/r.Dataset.map(hrs);r['stratum']=stratum;return r
RATES=pd.concat([rate_window('incident',-12,0).assign(window='12 h before onset'),rate_window('control',-12,0).assign(window='12 h before onset'),
                 rate_window('incident',1,25,'Hour').assign(window='hours 1-24'),rate_window('control',1,25,'Hour').assign(window='hours 1-24'),
                 rate_window('septic_on_arrival',1,13,'Hour').assign(window='hours 1-12'),rate_window('early_icu_onset',1,13,'Hour').assign(window='hours 1-12')],ignore_index=True)
RATES.to_csv(PATHO_ROOT/'measurement_rates.csv',index=False)
rr=RATES[RATES.window.eq('12 h before onset')].pivot_table(index=['Dataset','channel'],columns='stratum',values='rate')
rr['incident_over_control']=rr.get('incident')/rr.get('control');RATE_RATIO=rr.reset_index()
rate_cls=RATE_RATIO.groupby('channel').incident_over_control.agg(lambda s:'shared' if (s.notna().sum()==len(DATASETS)) and ((s>=1.5).all() or (s<=1/1.5).all()) else ('database-specific' if ((s>=1.5)|(s<=1/1.5)).any() else 'no signal'))
# temperature tails at the anchor hour (24 h extremes carried): fever, hypothermia, both
tails=HOURLY[(HOURLY.rel>=-1)&(HOURLY.rel<0)].groupby('stay').agg(tmax=('Temp_Max24h','max'),tmin=('Temp_Min24h','min')) if 'Temp_Max24h' in HOURLY else pd.DataFrame()
if len(tails):
    tails=tails.join(KEYS[['Dataset','stratum','course2']]);tails['fever']=tails.tmax.ge(38.3).astype(float).where(tails.tmax.notna());tails['hypothermia']=tails.tmin.le(36.).astype(float).where(tails.tmin.notna())
    TAILS=tails.groupby(['Dataset','stratum']).agg(n=('fever','size'),fever=('fever',frac_known),hypothermia=('hypothermia',frac_known)).round(3);TAILS['n']=TAILS.n.where(TAILS.n>=SMALL_CELL,-1)
    TAILS_COURSE=tails[tails.course2.notna()].groupby(['Dataset','stratum','course2']).agg(n=('fever','size'),fever=('fever',frac_known),hypothermia=('hypothermia',frac_known)).round(3);TAILS_COURSE['n']=TAILS_COURSE.n.where(TAILS_COURSE.n>=SMALL_CELL,-1)
    TAILS.to_csv(PATHO_ROOT/'temperature_tails.csv');TAILS_COURSE.to_csv(PATHO_ROOT/'temperature_tails_by_course.csv')
shared={c.split(' ')[0]:sorted(COMP[COMP.comparison.eq(c)&COMP.cross_database.isin(['shared','strong shared'])].channel.unique()) for c in COMP.comparison.unique()}
atomic_json(PATHO_ROOT/'shared_physiology.json',{'rule':'same sign and |Cliff delta| >= 0.147 in both databases (strong: >= 0.33)','shared_by_comparison':shared,'channels':CHANNELS,
    'measurement_rate_shared':sorted(rate_cls[rate_cls.eq('shared')].index)})
print('Channels:',len(CHANNELS),'| rows in long table:',f'{len(LONG):,}')
for c in COMP.comparison.unique():
    sub=COMP[COMP.comparison.eq(c)]
    if sub.delta.notna().sum()==0:print(f'\n{c}: not estimable (fewer than 11 stays on one side)');continue
    print(f'\n{c}  [delta > 0 means higher in {sub.a.iloc[0]}]')
    t=sub.pivot_table(index='channel',columns='Dataset',values='delta').round(2).join(sub.drop_duplicates('channel').set_index('channel').cross_database)
    display(t.sort_values(['cross_database']+[d for d in DATASETS if d in t]))
print('\nMeasurement-rate ratio incident/control, 12 h before (pseudo-)onset (practice signal):');display(RATE_RATIO.pivot_table(index='channel',columns='Dataset',values='incident_over_control').round(2).join(rate_cls.rename('rate_rule')))
if len(tails):print('\nTemperature tails at the (pseudo-)onset hour (24 h maximum >= 38.3 C; minimum <= 36 C):');display(TAILS);display(TAILS_COURSE)
print('Saved under',PATHO_ROOT)
# %% CODE
# 7d. Beyond the hypotheses: when each sign departs; the order of signs within patients; data-driven phenotypes at onset;
#     compensation states; temperature-heart-rate coupling; therapy-stratified reads; selection check; hospital heterogeneity; lactate clearance
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
# (a) departure timing: Cliff's delta incident vs matched control per 4 h bin over the 48 h before onset; first bin of a sustained departure
DEP_BINS=[(a,a+4) for a in range(-48,0,4)];rows=[]
for lo,hi in DEP_BINS:
    A=stay_window('incident',lo,hi);B=stay_window('control',lo,hi)
    ra=FRESH[FRESH.stratum.eq('incident')&(FRESH.rel>=lo)&(FRESH.rel<hi)].groupby(['Dataset','channel']).size();rb=FRESH[FRESH.stratum.eq('control')&(FRESH.rel>=lo)&(FRESH.rel<hi)].groupby(['Dataset','channel']).size()
    ha=HOURLY[HOURLY.stratum.eq('incident')&(HOURLY.rel>=lo)&(HOURLY.rel<hi)].groupby('Dataset').size();hb=HOURLY[HOURLY.stratum.eq('control')&(HOURLY.rel>=lo)&(HOURLY.rel<hi)].groupby('Dataset').size()
    for ds in DATASETS:
        for ch in CHANNELS:
            xa=A[A.Dataset.eq(ds)&A.channel.eq(ch)].value.to_numpy();xb=B[B.Dataset.eq(ds)&B.channel.eq(ch)].value.to_numpy()
            d=cliffs(xa,xb) if len(xa)>=SMALL_CELL and len(xb)>=SMALL_CELL else np.nan
            num=ra.get((ds,ch),0)/ha.get(ds,np.nan) if ha.get(ds,0) else np.nan;den=rb.get((ds,ch),0)/hb.get(ds,np.nan) if hb.get(ds,0) else np.nan
            rows.append({'Dataset':ds,'channel':ch,'bin_start':lo,'delta':d,'n_incident':len(xa) if len(xa)>=SMALL_CELL else -1,'n_control':len(xb) if len(xb)>=SMALL_CELL else -1,
                         'rate_ratio':(num/den) if (np.isfinite(num) and np.isfinite(den) and den>0) else np.nan})
DEP=pd.DataFrame(rows);DEP.to_csv(PATHO_ROOT/'departure_bins.csv',index=False)
def first_departure(g,col='delta',ratio=False):
    g=g.sort_values('bin_start');v=g[col].to_numpy(float);b=g.bin_start.to_numpy()
    if ratio:hit=np.where(np.isfinite(v),(v>=1.5)|(v<=1/1.5),False);sign=np.sign(np.log(np.where(np.isfinite(v)&(v>0),v,1.)))
    else:hit=np.isfinite(v)&(np.abs(v)>=.147);sign=np.sign(np.nan_to_num(v))
    if not len(v) or not hit[-1]:return np.nan
    k=len(v)-1
    while k>0 and hit[k-1] and sign[k-1]==sign[-1]:k-=1
    return float(b[k])
DEPART=DEP.groupby(['Dataset','channel']).apply(lambda g:pd.Series({'first_departure_h':first_departure(g),'delta_last_bin':g.sort_values('bin_start').delta.iloc[-1],
    'first_rate_departure_h':first_departure(g,'rate_ratio',True),'rate_ratio_last_bin':g.sort_values('bin_start').rate_ratio.iloc[-1],'bins_estimable':int(g.delta.notna().sum())}),include_groups=False).reset_index()
DEPART.to_csv(PATHO_ROOT/'departure_timing.csv',index=False)
print('(a) Empirical order of signs: first hour (bin start, relative to onset) from which the incident-control difference stays at or above 0.147 to the onset; and the same for the measurement-rate ratio (1.5-fold).')
display(DEPART.pivot_table(index='channel',columns='Dataset',values=['first_departure_h','delta_last_bin','first_rate_departure_h']).round(2).sort_values(('first_departure_h',DATASETS[0]),na_position='last'))
# (b) order of signs within patients: first crossing of a clinical threshold in the 48 h before onset; "new" = a normal value preceded it in the window
SIGNS={'Tachypnoea (Resp >= 22)':('Resp','fresh',lambda v:v>=22),'Tachycardia (HR >= 100)':('HR','fresh',lambda v:v>=100),'Fever (Temp >= 38.3)':('Temp','fresh',lambda v:v>=38.3),
       'Hypothermia (Temp <= 36)':('Temp','fresh',lambda v:v<=36.),'Hypotension (MAP < 65)':('MAP','fresh',lambda v:v<65),'SBP <= 100':('SBP','fresh',lambda v:v<=100),'Desaturation (O2Sat < 92)':('O2Sat','fresh',lambda v:v<92),
       'Lactate >= 2':('Lactate','fresh',lambda v:v>=2),'Leucocytosis (WBC >= 12)':('WBC','fresh',lambda v:v>=12),'Leucopenia (WBC <= 4)':('WBC','fresh',lambda v:v<=4),'Thrombocytopenia (Platelets < 150)':('Platelets','fresh',lambda v:v<150),
       'Hyperbilirubinaemia (>= 2)':('Bilirubin_total','fresh',lambda v:v>=2),'Hyperglycaemia (Glucose >= 180)':('Glucose','fresh',lambda v:v>=180),'Bicarbonate < 20':('HCO3','fresh',lambda v:v<20),
       'Oliguria (< 0.5 ml/kg/h over 6 h)':('Urine_mlkg_h_6h','carried',lambda v:v<.5),'Creatinine rise >= 0.3 from baseline':('Creatinine_DeltaBaseline','carried',lambda v:v>=.3),
       'Platelet fall >= 25% from baseline':('Platelets_DeltaBaseline','carried',lambda v:v<=-.25),'GCS < 15 (unsedated, not intubated)':('GCS','carried_unsedated',lambda v:v<15),'Shock index >= 0.9':('ShockIndex','carried',lambda v:v>=.9)}
def sign_events(stratum):
    ids=KEYS[KEYS.stratum.eq(stratum)].index
    F=FRESH[FRESH.stay.isin(ids)&(FRESH.rel>=-48)&(FRESH.rel<0)];H=HOURLY[HOURLY.stay.isin(ids)&(HOURLY.rel>=-48)&(HOURLY.rel<0)];out=[]
    for name,(ch,kind,pred) in SIGNS.items():
        if kind=='fresh':z=F[F.channel.eq(ch)][['stay','rel','value']]
        else:
            if ch not in H:continue
            hh=H
            if kind=='carried_unsedated':hh=H[(H.get('Med_Sedative_24h',pd.Series(0,index=H.index)).fillna(0)==0)&(H.get('Intubated',pd.Series(0,index=H.index)).fillna(0)==0)]
            z=hh[['stay','rel',ch]].rename(columns={ch:'value'}).dropna(subset=['value'])
            if ch=='Platelets_DeltaBaseline' and 'Platelets' in hh:   # fraction of the stay baseline
                base=hh['Platelets']-hh['Platelets_DeltaBaseline'];z=z.assign(value=(hh['Platelets_DeltaBaseline']/base.where(base>0)).loc[z.index]).dropna(subset=['value'])
        if z.empty:continue
        z=z.assign(hit=pred(z.value.to_numpy(float)));fh=z[z.hit].groupby('stay').rel.min().rename('first_hit')
        zz=z.merge(fh,on='stay',how='left');normal_before=zz[(~zz.hit)&(zz.rel<zz.first_hit)].groupby('stay').size()
        per=pd.DataFrame({'stay':z.stay.unique()});per['sign']=name;per['present']=per.stay.isin(fh.index);per['new']=per.stay.isin(normal_before.index);per['lead_h']=-per.stay.map(fh)
        per['lead_new_h']=per.lead_h.where(per.new);out.append(per)
    e=pd.concat(out,ignore_index=True) if out else pd.DataFrame(columns=['stay','sign','present','new','lead_h','lead_new_h'])
    e['Dataset']=e.stay.map(KEYS.Dataset);e['course2']=e.stay.map(KEYS.course2);return e
EV_INC=sign_events('incident');EV_CTL=sign_events('control')
def sign_table(e,by=('Dataset',)):
    by=list(by);t=e.groupby(by+['sign']).agg(n_measured=('stay','size'),present=('present','mean'),new=('new','mean'),lead_new_median_h=('lead_new_h','median'),lead_new_q25=('lead_new_h',q25),lead_new_q75=('lead_new_h',q75)).reset_index()
    small=t.n_measured<SMALL_CELL
    for c in ['present','new','lead_new_median_h','lead_new_q25','lead_new_q75']:t.loc[small,c]=np.nan
    t.loc[small,'n_measured']=-1;return t
SIGN_INC=sign_table(EV_INC);SIGN_CTL=sign_table(EV_CTL);SIGN_COURSE=sign_table(EV_INC[EV_INC.course2.notna()],('Dataset','course2'))
SIGN_INC.to_csv(PATHO_ROOT/'signs_incident.csv',index=False);SIGN_CTL.to_csv(PATHO_ROOT/'signs_control.csv',index=False);SIGN_COURSE.to_csv(PATHO_ROOT/'signs_incident_by_course.csv',index=False)
if len(SIGN_INC):
    st=SIGN_INC.merge(SIGN_CTL[['Dataset','sign','new']].rename(columns={'new':'new_in_controls_48h'}),on=['Dataset','sign'],how='left')
    print('\n(b) Signs in the 48 h before onset (incident) versus the matched 48 h of controls: fraction of measured stays in which the sign is present, fraction in which it is NEW (a normal value preceded it), median lead time of new signs.')
    display(st.pivot_table(index='sign',columns='Dataset',values=['present','new','new_in_controls_48h','lead_new_median_h']).round(2).sort_values(('lead_new_median_h',DATASETS[0]),ascending=False,na_position='last'))
def precedence(e):
    """P(sign A first before sign B | both new in the stay); masked when fewer than 11 stays have both."""
    w=e[e.new].pivot_table(index='stay',columns='sign',values='lead_new_h');signs=list(w.columns);P=pd.DataFrame(np.nan,index=signs,columns=signs);N=P.copy()
    for a in signs:
        for b in signs:
            if a==b:continue
            both=w[[a,b]].dropna()
            if len(both)>=SMALL_CELL:P.loc[a,b]=float((both[a]>both[b]).mean());N.loc[a,b]=len(both)
    return P,N
PREC={ds:precedence(EV_INC[EV_INC.Dataset.eq(ds)]) for ds in DATASETS if len(EV_INC)}
for ds,(P,N) in PREC.items():
    P.to_csv(PATHO_ROOT/f'precedence_{ds}.csv');
    if P.notna().any().any():print(f'\nPrecedence {ds}: P(row sign appears before column sign | both new before onset); mean over columns = how early the sign tends to be');display(P.mean(axis=1).sort_values(ascending=False).round(2).rename('mean P(earlier)'))
# (c) data-driven phenotypes at onset (all septic strata): k-means on pooled standardised last-known values at the onset hour
PH_CH=[c for c in ['Temp','HR','Resp','MAP','Lactate','WBC','Platelets','Creatinine','Bilirubin_total','Albumin','Glucose','HCO3','O2Sat','GCS','VasopressorDose_NEeq','Urine_mlkg_h_6h'] if c in ONSET_STATE]
PHENO_OUT={}
if len(ONSET_STATE) and PH_CH:
    X=ONSET_STATE[PH_CH].join(STATIC[['Age']] if 'Age' in STATIC else pd.DataFrame(index=ONSET_STATE.index)).join(KEYS[['Dataset','stratum','course2','hospital_death']])
    X=X[X.stratum.isin(SEPTIC)];feat=[c for c in PH_CH+['Age'] if c in X]
    if 'VasopressorDose_NEeq' in feat:X['VasopressorDose_NEeq']=X.VasopressorDose_NEeq.fillna(0.)
    miss=X.groupby('Dataset')[feat].apply(lambda d:d.isna().mean()).round(2);miss.to_csv(PATHO_ROOT/'phenotype_missingness.csv')
    feat=[c for c in feat if X[c].notna().mean()>=.4];miss_dropped=[c for c in PH_CH+['Age'] if c in X and c not in feat]
    enough=X[feat].notna().sum(axis=1)>=max(min(6,len(feat)),len(feat)//2);X=X[enough]
    if len(X)>=50:
        lo,hi=X[feat].quantile(.01),X[feat].quantile(.99);Z=X[feat].clip(lo,hi,axis=1);Z=Z.fillna(Z.median()).fillna(0.);mu,sd=Z.mean(),Z.std().replace(0,1).fillna(1);Z=((Z-mu)/sd).fillna(0.)
        sil={}
        for k in range(2,7):
            if len(Z)>k*5:
                lab=KMeans(k,n_init=10,random_state=RANDOM_STATE).fit_predict(Z);sub=np.random.default_rng(RANDOM_STATE).choice(len(Z),min(len(Z),3000),replace=False);sil[k]=float(silhouette_score(Z.iloc[sub],lab[sub]))
        K=4 if len(Z)>40 else 2;km=KMeans(K,n_init=20,random_state=RANDOM_STATE).fit(Z);X['phenotype']=km.labels_
        cent=pd.DataFrame(km.cluster_centers_,columns=feat);names={}
        for i,r in cent.iterrows():
            top=r.abs().sort_values(ascending=False).index[:2];names[i]='P'+str(i)+': '+', '.join(('high ' if r[t]>0 else 'low ')+t for t in top)
        X['phenotype_name']=X.phenotype.map(names)
        PROFILE=X.groupby('phenotype_name')[feat].median().round(2);SIZE=X.groupby(['Dataset','stratum','phenotype_name']).size().unstack('phenotype_name').fillna(0).astype(int);SIZE=SIZE.where(SIZE>=SMALL_CELL,-1)
        OUTC=X.groupby(['Dataset','phenotype_name']).agg(n=('stay','size') if 'stay' in X else ('phenotype','size'),mortality=('hospital_death',frac_known),deteriorating=('course2',lambda s:frac_known(s.eq('deteriorating').astype(float).where(s.notna())))).round(3);OUTC['n']=OUTC.n.where(OUTC.n>=SMALL_CELL,-1)
        PROFILE.to_csv(PATHO_ROOT/'phenotype_profiles.csv');SIZE.to_csv(PATHO_ROOT/'phenotype_sizes.csv');OUTC.to_csv(PATHO_ROOT/'phenotype_outcomes.csv')
        # cross-database reproducibility: fit per database, match centroids by correlation
        rep={}
        for ds in DATASETS:
            zi=Z[X.Dataset.eq(ds)]
            if len(zi)>K*10:rep[ds]=KMeans(K,n_init=10,random_state=RANDOM_STATE).fit(zi).cluster_centers_
        match=np.nan
        if len(rep)==2:
            a,b=[rep[d] for d in DATASETS];C=np.corrcoef(a,b)[:K,K:];used=set();pairs=[]
            for i in np.argsort(-C.max(axis=1)):
                j=int(np.argmax([C[i,jj] if jj not in used else -9 for jj in range(K)]));used.add(j);pairs.append(float(C[i,j]))
            match=float(np.mean(pairs))
        PHENO_OUT={'k':K,'silhouette_by_k':sil,'cross_database_centroid_correlation_mean':match,'names':names,'features':feat,'features_dropped_for_missingness':miss_dropped}
        atomic_json(PATHO_ROOT/'phenotypes.json',PHENO_OUT)
        print(f'\n(c) Data-driven phenotypes at onset (k = {K}; silhouette by k: { {k:round(v,3) for k,v in sil.items()} }; mean matched-centroid correlation between databases: {match if np.isnan(match) else round(match,2)})')
        display(PROFILE.T);display(SIZE);display(OUTC)
    else:print('(c) Phenotypes: fewer than 50 septic stays with an onset state; skipped.')
# (d) compensation states before onset (carried hourly values): quiet / compensated (HR >= 100 or Resp >= 22, MAP >= 65, no vasopressor) / decompensated (MAP < 65 or vasopressor)
if {'HR','Resp','MAP'}<=set(HOURLY.columns):
    h=HOURLY[(HOURLY.rel>=-24)&(HOURLY.rel<0)].copy();pres=h.get('VasopressorRecorded',pd.Series(0,index=h.index)).fillna(0)>0
    h['state']=np.where((h.MAP<65)|pres,'decompensated',np.where((h.HR>=100)|(h.Resp>=22),'compensated',np.where(h.MAP.notna()&h.HR.notna()&h.Resp.notna(),'quiet','unknown')))
    h['bin']=binned(h.rel,[(a,a+4) for a in range(-24,0,4)])
    STATES=h[h.state.ne('unknown')].groupby(['Dataset','stratum','course2','bin'],dropna=False).state.value_counts(normalize=True).unstack('state').fillna(0).round(3)
    n_st=h[h.state.ne('unknown')].groupby(['Dataset','stratum','course2','bin'],dropna=False).stay.nunique();STATES['n_stays']=n_st.where(n_st>=SMALL_CELL,-1)
    STATES=STATES[STATES.n_stays.ne(-1)];STATES.to_csv(PATHO_ROOT/'compensation_states.csv')
    print('\n(d) Compensation states in the 24 h before (pseudo-)onset, fraction of stay-hours (incident by course; controls):');display(STATES.reset_index().query("stratum in ['incident','control']").set_index(['Dataset','stratum','course2','bin']))
# (e) temperature-heart-rate coupling: within-stay slope of HR on temperature (fresh pairs, same hour) and relative bradycardia
pairs=FRESH[FRESH.channel.isin(['Temp','HR'])].pivot_table(index=['stay','Hour','rel'],columns='channel',values='value').dropna().reset_index() if {'Temp','HR'}<=set(VALUE_CH) else pd.DataFrame()
if len(pairs):
    pairs=pairs.merge(KEYS[['Dataset','stratum','course2']],left_on='stay',right_index=True)
    w=pairs[((pairs.stratum.isin(['incident','control']))&(pairs.rel>=-24)&(pairs.rel<0))|((pairs.stratum.isin(['septic_on_arrival','early_icu_onset']))&(pairs.Hour<=24))]
    sl=[]
    for (st,ds,strat),g in w.groupby(['stay','Dataset','stratum']):
        if len(g)>=6 and (g.Temp.max()-g.Temp.min())>=.5:sl.append({'stay':st,'Dataset':ds,'stratum':strat,'channel':'HR_per_degree','value':float(np.polyfit(g.Temp,g.HR,1)[0])})
    SL=pd.DataFrame(sl,columns=['stay','Dataset','stratum','channel','value'])
    COUPLE=SL.groupby(['Dataset','stratum']).value.agg(n='size',median_slope='median',q25=q25,q75=q75).round(2) if len(SL) else pd.DataFrame()
    if len(COUPLE):COUPLE['n']=COUPLE.n.where(COUPLE.n>=SMALL_CELL,-1);COUPLE.loc[COUPLE.n.eq(-1),['median_slope','q25','q75']]=np.nan;COUPLE.to_csv(PATHO_ROOT/'temp_hr_coupling.csv')
    bb=w.merge(HOURLY[['stay','Hour','Med_BetaBlocker_24h']],on=['stay','Hour'],how='left') if 'Med_BetaBlocker_24h' in HOURLY else w.assign(Med_BetaBlocker_24h=0)
    fe=bb[(bb.Temp>=38.3)&(bb.Med_BetaBlocker_24h.fillna(0)==0)]
    RB=fe.groupby(['Dataset','stratum']).agg(febrile_hours=('HR','size'),relative_bradycardia=('HR',lambda s:float((s<90).mean()))).round(3) if len(fe) else pd.DataFrame()
    if len(RB):RB.loc[RB.febrile_hours<SMALL_CELL,'relative_bradycardia']=np.nan;RB['febrile_hours']=RB.febrile_hours.where(RB.febrile_hours>=SMALL_CELL,-1);RB.to_csv(PATHO_ROOT/'relative_bradycardia.csv')
    print('\n(e) Heart-rate response per degree of temperature (within-stay slope; incident and controls 24 h before (pseudo-)onset, arrived strata first 24 h) and relative bradycardia (HR < 90 while Temp >= 38.3, no beta-blocker):')
    if len(COUPLE):display(COUPLE)
    if len(RB):display(RB)
# (f) therapy-stratified reads: incident vs control delta (12 h before onset) within exposed and unexposed stays
PAIRS=[(c,e) for c,e in [('Resp','Intubated'),('HR','Med_BetaBlocker_24h'),('Temp','Med_Antipyretic_24h'),('GCS','Med_Sedative_24h'),('WBC','Med_Corticosteroid_24h'),('Urine_mlkg_h_6h','Med_Diuretic_24h'),('MAP','VasopressorRecorded'),('Glucose','Med_Insulin_24h')] if c in CHANNELS and e in HOURLY]
expo=HOURLY[(HOURLY.rel>=-12)&(HOURLY.rel<0)].groupby('stay')[[e for _,e in PAIRS]].max() if PAIRS else pd.DataFrame()
rows=[]
for ch,e in PAIRS:
    A=stay_window('incident',-12,0,channels=[ch]);B=stay_window('control',-12,0,channels=[ch])
    for exposed in (0,1):
        ids=set(expo.index[expo[e].fillna(0).gt(0).eq(bool(exposed))])
        for ds in DATASETS:
            xa=A[A.Dataset.eq(ds)&A.stay.isin(ids)].value.to_numpy();xb=B[B.Dataset.eq(ds)&B.stay.isin(ids)].value.to_numpy()
            rows.append({'channel':ch,'stratifier':e,'exposed':exposed,'Dataset':ds,'n_incident':len(xa) if len(xa)>=SMALL_CELL else -1,'n_control':len(xb) if len(xb)>=SMALL_CELL else -1,
                         'delta':cliffs(xa,xb) if len(xa)>=SMALL_CELL and len(xb)>=SMALL_CELL else np.nan})
STRAT=pd.DataFrame(rows);STRAT.to_csv(PATHO_ROOT/'therapy_stratified_deltas.csv',index=False)
if len(STRAT):print('\n(f) Incident-control delta 12 h before onset within therapy strata (does the masking therapy hide the sign?):');display(STRAT.pivot_table(index=['channel','stratifier'],columns=['Dataset','exposed'],values='delta').round(2))
# (g) selection check: the pre-onset delta restricted to stays measured in every 4 h bin of the 12 h window
def regular(stratum,ch):
    f=FRESH[FRESH.stratum.eq(stratum)&FRESH.channel.eq(ch)&(FRESH.rel>=-12)&(FRESH.rel<0)].copy();f['b']=np.floor(f.rel/4)
    n=f.groupby('stay').b.nunique();return set(n.index[n>=3])
rows=[]
for ch in VALUE_CH:
    A=stay_window('incident',-12,0,channels=[ch]);B=stay_window('control',-12,0,channels=[ch]);ra=regular('incident',ch);rb=regular('control',ch)
    for ds in DATASETS:
        xa=A[A.Dataset.eq(ds)&A.stay.isin(ra)].value.to_numpy();xb=B[B.Dataset.eq(ds)&B.stay.isin(rb)].value.to_numpy()
        all_d=COMP[COMP.comparison.str.startswith('C2 ')&COMP.Dataset.eq(ds)&COMP.channel.eq(ch)].delta
        rows.append({'channel':ch,'Dataset':ds,'delta_all_stays':float(all_d.iloc[0]) if len(all_d) else np.nan,'delta_regularly_measured':cliffs(xa,xb) if len(xa)>=SMALL_CELL and len(xb)>=SMALL_CELL else np.nan,
                     'n_incident_regular':len(xa) if len(xa)>=SMALL_CELL else -1,'n_control_regular':len(xb) if len(xb)>=SMALL_CELL else -1})
SELECT=pd.DataFrame(rows);SELECT.to_csv(PATHO_ROOT/'selection_check.csv',index=False)
sel_show=SELECT.dropna(subset=['delta_regularly_measured'])
if len(sel_show):print('\n(g) Selection check: pre-onset delta in all stays versus stays measured in every 4 h bin (a value signal that survives is not a who-gets-measured artefact):');display(sel_show.pivot_table(index='channel',columns='Dataset',values=['delta_all_stays','delta_regularly_measured']).round(2))
# (h) hospital heterogeneity (eICU controls, hours 1-24): share of between-hospital variance (ICC) in stay medians and in measurement rates
def icc(groups):
    g=[np.asarray(x,float) for x in groups if len(x)>=2]
    if len(g)<3:return np.nan
    allv=np.concatenate(g);k=len(g);N=len(allv);gm=allv.mean()
    msb=sum(len(x)*(x.mean()-gm)**2 for x in g)/(k-1);msw=sum(((x-x.mean())**2).sum() for x in g)/(N-k);k0=(N-sum(len(x)**2 for x in g)/N)/(k-1)
    return float((msb-msw)/(msb+(k0-1)*msw)) if (msb+(k0-1)*msw)>0 else np.nan
HOSP=MANIFEST.set_index('stay').Hospital_ID if 'Hospital_ID' in MANIFEST else pd.Series(dtype=object)
rows=[]
for ds in DATASETS:
    ids=KEYS[(KEYS.Dataset.eq(ds))&KEYS.stratum.eq('control')].index;hs=HOSP.reindex(ids);big=hs.value_counts();big=set(big.index[big>=20])
    if len(big)<3:rows.append({'Dataset':ds,'channel':'(all)','hospitals_with_20_controls':len(big),'icc_value':np.nan,'icc_rate':np.nan});continue
    hrs=HOURLY[HOURLY.stay.isin(ids)&(HOURLY.Hour<=24)].groupby('stay').size()
    for ch in VALUE_CH:
        f=FRESH[FRESH.stay.isin(ids)&FRESH.channel.eq(ch)&(FRESH.Hour<=24)];med=f.groupby('stay').value.median();cnt=f.groupby('stay').size().reindex(hrs.index,fill_value=0)/hrs
        mv=pd.DataFrame({'v':med,'h':hs.reindex(med.index)});mr=pd.DataFrame({'v':cnt,'h':hs.reindex(cnt.index)})
        rows.append({'Dataset':ds,'channel':ch,'hospitals_with_20_controls':len(big),'icc_value':icc([g.v.to_numpy() for h,g in mv.groupby('h') if h in big]),'icc_rate':icc([g.v.to_numpy() for h,g in mr.groupby('h') if h in big])})
ICC=pd.DataFrame(rows);ICC.to_csv(PATHO_ROOT/'hospital_heterogeneity.csv',index=False)
icc_show=ICC.dropna(subset=['icc_value'])
if len(icc_show):print('\n(h) Between-hospital share of variance among controls (hours 1-24): values versus measurement rates (practice spread):');display(icc_show.set_index(['Dataset','channel'])[['icc_value','icc_rate']].round(3).sort_values('icc_rate',ascending=False))
else:print('\n(h) Hospital heterogeneity: fewer than 3 hospitals with 20 controls; skipped.')
# (i) lactate clearance over the first 6 h after onset, by stratum and course
if 'Lactate' in VALUE_CH:
    L=FRESH[FRESH.channel.eq('Lactate')&FRESH.stratum.isin(SEPTIC)].copy();L['t']=np.where(L.stratum.eq('septic_on_arrival'),L.Hour-1,L.rel)
    l0=L[(L.t>=-2)&(L.t<=1)].groupby('stay').value.median();l6=L[(L.t>=4)&(L.t<=8)].groupby('stay').value.median()
    cl=pd.DataFrame({'l0':l0}).join(l6.rename('l6'),how='inner');cl=cl[cl.l0>0];cl['clearance']=(cl.l0-cl.l6)/cl.l0;cl=cl.join(KEYS[['Dataset','stratum','course2']])
    LACT=cl.groupby(['Dataset','stratum','course2'],dropna=False).agg(n=('clearance','size'),lactate_onset_median=('l0','median'),clearance_median=('clearance','median'),cleared_10pct=('clearance',lambda s:float((s>=.1).mean()))).round(3)
    LACT.loc[LACT.n<SMALL_CELL,['lactate_onset_median','clearance_median','cleared_10pct']]=np.nan;LACT['n']=LACT.n.where(LACT.n>=SMALL_CELL,-1);LACT.to_csv(PATHO_ROOT/'lactate_clearance.csv')
    if len(LACT):print('\n(i) Lactate clearance from onset (-2..+1 h) to +4..+8 h, by stratum and course:');display(LACT)
print('\nSaved under',PATHO_ROOT)
# %% CODE
# 7e. Therapy exposure by stratum, course and window (the table that must sit beside every post-onset comparison)
WINDOWS={'12 h before onset':(-12,0),'onset to +6 h':(0,6),'+6 to +24 h':(6,24),'+24 to +48 h':(24,48)}
EXPO_FLAGS=[c for c in ['VasopressorRecorded','InotropeRecorded','Intubated','O2_NIV','O2_HighFlow','Med_Sedative_24h','Med_Opioid_24h','Med_Corticosteroid_24h','Med_Hydrocortisone_24h','Procedure_RRT_24h','Transfusion_24h',
                        'Med_BetaBlocker_24h','Med_Antipyretic_24h','Med_Diuretic_24h','Med_Insulin_24h','Imaging_24h','Nutrition_TPN_24h','Device_CentralLine','Device_UrinaryCatheter'] if c in HOURLY]
EXPO_CONT=[c for c in ['VasopressorDose_NEeq','FluidIn_6h','FluidIn_24h','NetBalance_24h','LabResults_24h'] if c in HOURLY]
rows=[]
for wname,(lo,hi) in WINDOWS.items():
    h=HOURLY[(HOURLY.rel>=lo)&(HOURLY.rel<hi)]
    if h.empty:continue
    per=h.groupby('stay').agg({**{c:'max' for c in EXPO_FLAGS},**{c:'max' for c in EXPO_CONT}}).join(KEYS[['Dataset','stratum','course2']]);per['one']=1
    for c in EXPO_FLAGS:per[c]=per[c].gt(0).astype(float).where(per[c].notna()|pd.Series(c in ('VasopressorRecorded','InotropeRecorded','Intubated'),index=per.index))   # no record in the window = no support (support channels are unknown, not 0, when nothing is charted)
    for by in (['Dataset','stratum'],['Dataset','stratum','course2']):
        t=per.groupby(by,dropna=False).agg({**{c:frac_known for c in EXPO_FLAGS},**{c:'median' for c in EXPO_CONT},'one':'size'}).rename(columns={'one':'n'})
        t.loc[t.n<SMALL_CELL,[c for c in t.columns if c!='n']]=np.nan;t['n']=t.n.where(t.n>=SMALL_CELL,-1);t['window']=wname;t['grouping']='stratum' if len(by)==2 else 'stratum x course'
        rows.append(t.reset_index())
EXPOSURE=pd.concat(rows,ignore_index=True) if rows else pd.DataFrame();EXPOSURE.to_csv(PATHO_ROOT/'therapy_exposure.csv',index=False)
if len(EXPOSURE):
    print('Therapy exposure (fraction of stays with any exposure in the window; medians for doses and volumes):')
    show=[c for c in ['n','VasopressorRecorded','VasopressorDose_NEeq','FluidIn_24h','Intubated','Med_Sedative_24h','Med_Corticosteroid_24h','Procedure_RRT_24h','Transfusion_24h','Med_BetaBlocker_24h','Med_Antipyretic_24h','Med_Diuretic_24h','LabResults_24h'] if c in EXPOSURE]
    display(EXPOSURE[EXPOSURE.grouping.eq('stratum')].set_index(['window','Dataset','stratum'])[show].round(2))
    ec=EXPOSURE[EXPOSURE.grouping.eq('stratum x course')&EXPOSURE.course2.notna()]
    if len(ec):print('\nBy course:');display(ec.set_index(['window','Dataset','stratum','course2'])[show].round(2))
# antibiotic timing relative to onset (incident, cohort metadata only; never a predictor)
if 'FirstAntibioticAroundOnset' in MANIFEST:
    ab=MANIFEST[MANIFEST.stratum.eq('incident')].assign(lead=lambda d:d.FirstAntibioticAroundOnset-d.onset_h)
    AB=ab.groupby('Dataset').lead.agg(n='count',median='median',q25=q25,q75=q75,before_onset=lambda s:float((s<0).mean()) if s.notna().any() else np.nan).round(2);AB.loc[AB.n<SMALL_CELL,['median','q25','q75','before_onset']]=np.nan;AB['n']=AB.n.where(AB.n>=SMALL_CELL,-1)
    AB.to_csv(PATHO_ROOT/'antibiotic_timing_incident.csv');print('\nFirst antibiotic around onset relative to the onset hour (incident; negative = antibiotic before the operational onset):');display(AB)
# %% CODE
# 7f. Figures
import matplotlib.pyplot as plt
KEY=[c for c in ['HR','Resp','Temp','MAP','DBP','O2Sat','Lactate','WBC','Platelets','Creatinine','Bilirubin_total','GCS','Glucose','HCO3','Urine_mlkg_h_6h','VasopressorDose_NEeq'] if c in CHANNELS]
colors={'incident':'#b3122b','septic_on_arrival':'#9a5b00','early_icu_onset':'#5a2d82','control':'#1f6f3f'};styles={DATASETS[0]:'-',DATASETS[-1]:'--'}
def small_multiples(T,bincol_x,title,path,hue='stratum',hues=None,xlabel='hours relative to (pseudo-)onset',vline=True):
    fig,axes=plt.subplots(int(np.ceil(len(KEY)/2)),2,figsize=(12,2.0*np.ceil(len(KEY)/2)),squeeze=False);axes=axes.ravel()
    for i,ch in enumerate(KEY):
        ax=axes[i];t=T[T.channel.eq(ch)&T.n_stays.ge(SMALL_CELL)]
        for keys,s in t.groupby(['Dataset',hue]):
            ds,g=keys
            if hues is not None and g not in hues:continue
            s=s.sort_values('x');ax.plot(s.x,s['median'],styles.get(ds,'-'),color=colors.get(g,{'deteriorating':'#b3122b','improving':'#1f6f3f'}.get(g,'k')),lw=1.3,label=f'{g} ({ds})')
            ax.fill_between(s.x,s.q25,s.q75,color=colors.get(g,{'deteriorating':'#b3122b','improving':'#1f6f3f'}.get(g,'k')),alpha=.07)
        if vline:ax.axvline(0,color='#888',lw=.8)
        ax.set_title(ch,fontsize=8,loc='left');ax.tick_params(labelsize=7)
    for ax in axes[len(KEY):]:ax.axis('off')
    axes[0].legend(fontsize=6,ncol=2);fig.suptitle(title,fontsize=9);fig.supxlabel(xlabel,fontsize=8);fig.tight_layout();fig.savefig(path,dpi=140);plt.show()
small_multiples(TRAJ_ONSET,'bin_onset','Fresh-value medians (IQR shaded) relative to onset; controls relative to a matched pseudo-onset; solid '+DATASETS[0]+', dashed '+DATASETS[-1],PATHO_ROOT/'fig1_trajectories_onset.png')
small_multiples(TRAJ_ADM,'bin_adm','Fresh-value medians by hour since ICU admission (the arrived strata start septic)',PATHO_ROOT/'fig2_trajectories_admission.png',xlabel='hours since ICU admission',vline=False)
tc=TRAJ_COURSE[TRAJ_COURSE.stratum.eq('incident')&TRAJ_COURSE.course2.notna()]
if len(tc):small_multiples(tc,'bin_onset','Incident sepsis by course: deteriorating (red) versus improving (green), relative to onset',PATHO_ROOT/'fig3_incident_by_course.png',hue='course2')
# departure timing
dp=DEPART.dropna(subset=['first_departure_h'])
if len(dp):
    fig,axes=plt.subplots(1,len(DATASETS),figsize=(6*len(DATASETS),max(3,.28*dp.channel.nunique())),squeeze=False)
    for ax,ds in zip(axes.ravel(),DATASETS):
        d=dp[dp.Dataset.eq(ds)].sort_values('first_departure_h')
        if d.empty:ax.axis('off');continue
        ax.barh(d.channel,-d.first_departure_h,color=np.where(d.delta_last_bin>0,'#b3122b','#1f4e8c'));ax.set_xlabel('hours before onset from which the difference is sustained',fontsize=8);ax.set_title(ds+' (red: higher in incident, blue: lower)',fontsize=9);ax.tick_params(labelsize=7);ax.invert_yaxis()
    fig.tight_layout();fig.savefig(PATHO_ROOT/'fig4_departure_timing.png',dpi=140);plt.show()
# precedence heatmaps
if PREC and any(P.notna().any().any() for P,_ in PREC.values()):
    fig,axes=plt.subplots(1,len(PREC),figsize=(7*len(PREC),6),squeeze=False)
    for ax,(ds,(P,N)) in zip(axes.ravel(),PREC.items()):
        order=P.mean(axis=1).sort_values(ascending=False).index;M=P.loc[order,order].to_numpy(float)
        im=ax.imshow(M,vmin=0,vmax=1,cmap='RdBu_r');ax.set_xticks(range(len(order)));ax.set_yticks(range(len(order)));ax.set_xticklabels(order,rotation=90,fontsize=6);ax.set_yticklabels(order,fontsize=6);ax.set_title(ds+': P(row sign before column sign)',fontsize=9)
    fig.colorbar(im,ax=axes.ravel().tolist(),shrink=.6);fig.savefig(PATHO_ROOT/'fig5_precedence.png',dpi=140,bbox_inches='tight');plt.show()
# phenotype profiles (standardised medians)
if PHENO_OUT and (PATHO_ROOT/'phenotype_profiles.csv').is_file():
    pr=pd.read_csv(PATHO_ROOT/'phenotype_profiles.csv',index_col=0);zs=(pr-pr.mean())/pr.std().replace(0,1)
    fig,ax=plt.subplots(figsize=(10,2.5+.3*len(zs)));im=ax.imshow(zs.to_numpy(float),cmap='RdBu_r',vmin=-2,vmax=2,aspect='auto')
    ax.set_xticks(range(zs.shape[1]));ax.set_xticklabels(zs.columns,rotation=90,fontsize=7);ax.set_yticks(range(len(zs)));ax.set_yticklabels(zs.index,fontsize=7);ax.set_title('Phenotypes at onset: cluster medians, standardised across clusters',fontsize=9);fig.colorbar(im,shrink=.6);fig.tight_layout();fig.savefig(PATHO_ROOT/'fig6_phenotypes.png',dpi=140);plt.show()
# compensation states (incident, all courses pooled; controls)
if 'STATES' in globals() and len(STATES):
    s=STATES.reset_index();s=s[s.stratum.isin(['incident','control'])]
    fig,axes=plt.subplots(1,len(DATASETS),figsize=(6*len(DATASETS),3),squeeze=False)
    for ax,ds in zip(axes.ravel(),DATASETS):
        z=s[s.Dataset.eq(ds)&s.stratum.eq('incident')&s.course2.isna()].sort_values('bin',key=lambda b:b.str.split('..',regex=False).str[0].astype(int))
        if z.empty:ax.axis('off');continue
        x=z.bin.str.split('..',regex=False).str[0].astype(int);bottom=np.zeros(len(z))
        for st,col in [('quiet','#cfd8dc'),('compensated','#f4a261'),('decompensated','#b3122b')]:
            if st in z:ax.bar(x,z[st],4,bottom=bottom,color=col,label=st,align='edge');bottom+=z[st].to_numpy()
        ax.set_title(ds+': incident, fraction of stay-hours by state',fontsize=9);ax.set_xlabel('hours relative to onset',fontsize=8);ax.tick_params(labelsize=7);ax.legend(fontsize=6)
    fig.tight_layout();fig.savefig(PATHO_ROOT/'fig7_compensation.png',dpi=140);plt.show()
print('Figures saved under',PATHO_ROOT)
# %% CODE
# 7g. Hypotheses H1-H23 of the framework document scored where a sign test applies; stage-2 predictor sets; aggregate digest for the team
def hstat(comp_prefix,channel,expected):
    sub=COMP[COMP.comparison.str.startswith(comp_prefix+' ')&COMP.channel.eq(channel)]
    if sub.empty or sub.delta.isna().all():return 'not testable',{}
    d={r.Dataset:r.delta for r in sub.itertuples()};ok=[(np.sign(v)==expected and abs(v)>=.147) for v in d.values() if pd.notna(v)]
    if len(ok)==len(DATASETS) and all(ok):return 'supported in both databases',d
    if any(ok):return 'supported in one database',d
    if all((np.sign(v)==-expected and abs(v)>=.147) for v in d.values() if pd.notna(v)):return 'opposite direction',d
    return 'not supported (no signal)',d
H=[('H1','C2','Resp',+1),('H1','C6','Resp',+1),('H2','C2','HR',+1),('H2','C2','DBP',-1),('H2','C2','PulsePressure',+1),('H2','C2','ShockIndex',+1),('H2','C2','MAP',-1),
   ('H4','C2','O2Sat',-1),('H4','C2','SF_Ratio',-1),('H4','C2','FiO2',+1),('H5','C2','Urine_mlkg_h_6h',-1),('H6','C2','Creatinine',+1),('H6','C2','BUN',+1),('H7','C2','Platelets_DeltaBaseline',-1),('H7','C2','Platelets',-1),
   ('H8','C2','Lactate',+1),('H9','C2','WBC',+1),('H9','C2','NLR',+1),('H9','C2','Lymphocytes',-1),('H10','C2','Glucose',+1),('H11','C2','HCO3',-1),('H11','C2','BaseExcess',-1),('H11','C2','AnionGap',+1),('H11','C2','pH',-1),
   ('H12','C2','Bilirubin_total',+1),('H12','C2','Albumin',-1),('H13','C2','GCS',-1),('H14','C2','HR_Variance6h',-1),
   ('H17','C3','Lactate',+1),('H17','C3','VasopressorDose_NEeq',+1),('H17','C3','Temp',+1),('H18','C3','Temp_Min24h',+1),('H18','C3','Lymphocytes',+1),('H18','C3','SOFA_Renal',-1),('H18','C3','SOFA_Resp',-1),
   ('H20','C10','Lactate',+1),('H20','C10','Platelets',-1),('H20','C10','Temp',-1),('H20','C10','VasopressorDose_NEeq',+1),('H20','C10','Urine_mlkg_h_6h',-1),('H20','C10','Bilirubin_total',+1),
   ('H21','C7','Resp',+1),('H21','C7','HR',+1),('H21','C7','Platelets_DeltaBaseline',-1),('H21','C7','Urine_mlkg_h_6h',-1),('H21','C7','Temp',-1),('H21','C7','Lactate',+1),
   ('H23','C10','Temp',-1),('H23','C10','HR',+1),('H23','C9','Platelets',-1),('H23','C9','Bilirubin_total',+1),('H23','C9','Creatinine',+1)]
rows=[]
for h,c,ch,e in H:
    st,d=hstat(c,ch,e);rows.append({'hypothesis':h,'comparison':c,'channel':ch,'expected_sign':'+' if e>0 else '-','status':st,**{'delta_'+k:round(v,3) for k,v in d.items()}})
HYP=pd.DataFrame(rows)
notes={'H3':'read the temperature-tails table (fever AND hypothermia both more frequent in incident than control)','H13':'read the GCS row of the therapy-stratified table in the unsedated stratum','H14':'measurement artefact between databases; not comparable by design',
       'H15':'read the measurement-rate rule: '+', '.join(sorted(rate_cls[rate_cls.eq("shared")].index)) if len(rate_cls) else 'rates not estimable','H16':f"C1 channels shared at baseline: {len(shared.get('C1',[]))}",
       'H19':'read the onset-state fractions by database below','H22':'read the therapy-exposure tables by course'}
for h,n in notes.items():HYP=pd.concat([HYP,pd.DataFrame([{'hypothesis':h,'comparison':'-','channel':'-','expected_sign':'-','status':n}])],ignore_index=True)
HYP['order']=HYP.hypothesis.str[1:].astype(int);HYP=HYP.sort_values(['order','comparison','channel']).drop(columns='order');HYP.to_csv(PATHO_ROOT/'hypothesis_results.csv',index=False)
print('Hypotheses of the framework document, scored on the comparisons (sign and |delta| >= 0.147):');display(HYP.set_index(['hypothesis','comparison','channel']))
# H19: severity of the septic-on-arrival stratum at onset, by database
if len(ONSET_STATE):
    o=ONSET_STATE.join(KEYS[['Dataset','stratum']]);o=o[o.stratum.isin(SEPTIC)]
    sev=pd.DataFrame({'lactate_ge_2':o.Lactate.ge(2).astype(float).where(o.Lactate.notna()) if 'Lactate' in o else np.nan,'vasopressor':o.VasopressorRecorded.fillna(0).gt(0).astype(float) if 'VasopressorRecorded' in o else np.nan,
                      'map_lt_65':o.MAP.lt(65).astype(float).where(o.MAP.notna()) if 'MAP' in o else np.nan,'Dataset':o.Dataset,'stratum':o.stratum})
    SEV=sev.groupby(['Dataset','stratum']).agg(n=('Dataset','size'),lactate_ge_2=('lactate_ge_2',frac_known),vasopressor=('vasopressor',frac_known),map_lt_65=('map_lt_65',frac_known)).round(3);SEV['n']=SEV.n.where(SEV.n>=SMALL_CELL,-1)
    SEV.to_csv(PATHO_ROOT/'onset_severity.csv');print('\nSeverity at the onset state (fractions among measured):');display(SEV)
# ---- stage-2 predictor sets by registry class (10c.2 item 2); shared physiology = channels shared in the pre-onset comparisons ----
PHYS_KINDS={'raw measurement','derived criterion/ratio','renal window (availability-aware)'}
base_phys=set(REGISTRY[REGISTRY.kind.isin(PHYS_KINDS)|REGISTRY.kind.str.startswith('handcrafted')].feature)|{'Age','Gender'}
PHYSIOLOGY_ONLY=[f for f in FEATURES if f in base_phys or (f.endswith('_observed') and f[:-9] in base_phys) or (f.endswith('_age') and f[:-4] in base_phys)]
PHYSIOLOGY_NO_MASKS=[f for f in PHYSIOLOGY_ONLY if not f.endswith(('_observed','_age'))]
shared_pre=set(shared.get('C2',[]))|set(shared.get('C2b',[]))|set(shared.get('C6',[]))
SHARED_PHYSIOLOGY=[f for f in PHYSIOLOGY_ONLY if base_name(f) in shared_pre or f in shared_pre or f in ('Age','Gender')]
atomic_json(PATHO_ROOT/'stage2_predictor_sets.json',{'physiology_only':PHYSIOLOGY_ONLY,'physiology_no_masks':PHYSIOLOGY_NO_MASKS,'shared_physiology':SHARED_PHYSIOLOGY,'shared_pre_onset_channels':sorted(shared_pre),
    'rule':'10c.2 item 2: classes raw measurement, derived criterion/ratio, renal window, handcrafted physiology, with masks and ages, plus Age and Gender; shared = channels marked shared in the pre-onset comparisons C2, C2b or C6'})
print('\nStage-2 predictor sets | full:',len(FEATURES),'| physiology only:',len(PHYSIOLOGY_ONLY),'| without masks/ages:',len(PHYSIOLOGY_NO_MASKS),'| shared physiology:',len(SHARED_PHYSIOLOGY),'| shared pre-onset channels:',sorted(shared_pre))
# ---- aggregate digest (text) for the team; every table is already masked ----
import io as _io
buf=_io.StringIO();W=lambda *a:print(*a,file=buf)
W('PATHOPHYSIOLOGY STUDY DIGEST | key',PATHO_KEY,'| data',DATA_KEY,'| source',DATA_SOURCE,'| course horizon',PRIMARY_COURSE_H,'h | generated',time.strftime('%Y-%m-%d %H:%M'))
W('\n== Strata and coverage ==');W(COVER.set_index('Dataset').T.to_string())
W('\n== Course by stratum ==')
for ds in DATASETS:W(ds);W(masked_crosstab(sepm[sepm.Dataset.eq(ds)].stratum,sepm[sepm.Dataset.eq(ds)].course).to_string())
W('\n== Sepsis documentation and mortality by stratum ==');W(sep.groupby(['Dataset','stratum']).agg(stays=('stay','size'),hospital_mortality=('hospital_death',_frac),admitted_for_sepsis_dx=('admitted_for_sepsis_dx',_frac),sepsis_documented=('sepsis_documented',_frac)).round(3).to_string())
W('\n== Admission context by stratum ==');W(CTX.T.to_string())
for c in COMP.comparison.unique():
    sub=COMP[COMP.comparison.eq(c)]
    if sub.delta.notna().sum()==0:W(f'\n== {c}: not estimable ==');continue
    W(f'\n== {c} (delta > 0: higher in {sub.a.iloc[0]}) ==');W(sub.pivot_table(index='channel',columns='Dataset',values='delta').round(2).join(sub.drop_duplicates('channel').set_index('channel').cross_database).sort_values('cross_database').to_string())
W('\n== Measurement-rate ratio incident/control, 12 h before (pseudo-)onset ==');W(RATE_RATIO.pivot_table(index='channel',columns='Dataset',values='incident_over_control').round(2).join(rate_cls.rename('rate_rule')).to_string())
if len(tails):W('\n== Temperature tails ==');W(TAILS.to_string());W(TAILS_COURSE.to_string())
W('\n== Departure timing ==');W(DEPART.pivot_table(index='channel',columns='Dataset',values=['first_departure_h','delta_last_bin','first_rate_departure_h']).round(2).to_string())
if len(SIGN_INC):W('\n== Signs before onset (incident) ==');W(SIGN_INC.round(2).to_string());W('\n== Signs in matched control windows ==');W(SIGN_CTL.round(2).to_string());W('\n== Signs by course ==');W(SIGN_COURSE.round(2).to_string())
for ds,(P,N) in PREC.items():
    if P.notna().any().any():W(f'\n== Precedence {ds}: mean P(earlier) ==');W(P.mean(axis=1).sort_values(ascending=False).round(2).to_string())
if PHENO_OUT:W('\n== Phenotypes ==');W(json.dumps({k:v for k,v in PHENO_OUT.items() if k!='features'},default=str));W(pd.read_csv(PATHO_ROOT/'phenotype_profiles.csv',index_col=0).T.to_string());W(pd.read_csv(PATHO_ROOT/'phenotype_sizes.csv').to_string());W(pd.read_csv(PATHO_ROOT/'phenotype_outcomes.csv').to_string())
if 'STATES' in globals() and len(STATES):W('\n== Compensation states ==');W(STATES.to_string())
if 'COUPLE' in globals() and len(COUPLE):W('\n== Temperature-heart-rate coupling ==');W(COUPLE.to_string())
if 'RB' in globals() and len(RB):W(RB.to_string())
if len(STRAT):W('\n== Therapy-stratified deltas ==');W(STRAT.pivot_table(index=['channel','stratifier'],columns=['Dataset','exposed'],values='delta').round(2).to_string())
if len(sel_show):W('\n== Selection check ==');W(sel_show.pivot_table(index='channel',columns='Dataset',values=['delta_all_stays','delta_regularly_measured']).round(2).to_string())
if len(icc_show):W('\n== Hospital heterogeneity ==');W(icc_show.set_index(['Dataset','channel'])[['icc_value','icc_rate']].round(3).to_string())
if 'LACT' in globals() and len(LACT):W('\n== Lactate clearance ==');W(LACT.to_string())
if len(EXPOSURE):W('\n== Therapy exposure ==');W(EXPOSURE.set_index(['grouping','window','Dataset','stratum']+(['course2'] if 'course2' in EXPOSURE else []))[show].round(2).to_string())
if 'AB' in globals():W('\n== Antibiotic timing (incident) ==');W(AB.to_string())
if 'SEV' in globals():W('\n== Onset severity ==');W(SEV.to_string())
W('\n== Hypotheses ==');W(HYP.to_string(index=False))
W('\n== Stage-2 predictor sets ==');W('full',len(FEATURES),'| physiology only',len(PHYSIOLOGY_ONLY),'| no masks',len(PHYSIOLOGY_NO_MASKS),'| shared physiology',len(SHARED_PHYSIOLOGY));W('shared pre-onset channels:',sorted(shared_pre))
(PATHO_ROOT/'digest.txt').write_text(buf.getvalue());print('\nDigest written (aggregate tables only, counts under 11 masked):',PATHO_ROOT/'digest.txt',f'({len(buf.getvalue())//1024} KB)')
print('Study key:',PATHO_KEY)
