"""Versioned derivative of supplied_handcrafted_original.py, preserving unknowns.

Input: one patient's availability-aware hourly values, already in canonical units.
SOFA-style proxies are current-value features, NOT the clinical 24h SOFA score.
Threshold reference: Singer et al., JAMA 2016, doi:10.1001/jama.2016.0287.
No claims of reproducing TREWScore or improving clinical performance are made.

10.2 changes (audit):
- Trend statistics use only FRESH measurements at their real measurement times
  (cutoff Hour minus the `<feature>_age` channel). Values carried forward by the
  availability TTL are no longer counted repeatedly, and slopes are fitted against
  actual measurement times. Without an age channel the grid hours are used.
- Explicit time-since-FIRST and time-since-MOST-RECENT observed-event features for
  recorded vasopressor support and for a qSOFA >=2 state. Unknown hours neither
  create nor erase an event; before the first observed event the value is unknown.

10.3 changes (user decisions, 18 Oct 2026):
- qSOFA is reported twice: the strict total (all three criteria known, unchanged) and
  qSOFA_MetAmongMeasured, the number of criteria met among those that can be decided now.
  The GCS criterion uses GCS_Below15 when present: GCS < 15 is decidable from partial
  components (an abnormal eye or motor score) without imputing an unknown intubated verbal
  score. The qSOFA >= 2 event times use the same decidable criteria.

10.5 changes (user: include every possible predictor):
- SOFA with all six organ systems (Vincent 1996 thresholds): respiratory from P/F (3-4 only with
  an invasive airway), cardiovascular from MAP, norepinephrine-equivalent dose and inotropes, renal
  from creatinine and 24 h urine volume (when >= 18 of 24 h documented), plus coagulation, liver
  and CNS. Strict total (all six known), total among measured, and SOFA_Delta = sum over known
  components of (current minus best value so far in the stay): the Sepsis-3 'acute change'.
- NEWS2 (Royal College of Physicians 2017) among measured components, consciousness from GCS < 15.
"""
import numpy as np
import pandas as pd

VERSION = 'handcrafted-10.5'
FRESH_TOLERANCE_HOURS = 1e-3   # float32 shard round-trip safe (about 3.6 s)
GROUPS = {
 'DerivedMAP':'cardiovascular','PulsePressure':'cardiovascular',
 'BUNCreatinineRatio':'renal','AgeSBP':'demographic',
 'qSOFA_Resp':'respiratory','qSOFA_SBP':'cardiovascular','qSOFA_GCS':'neurologic',
 'qSOFA_Total':'systemic_composite','qSOFA_Available':'systemic_composite','qSOFA_MetAmongMeasured':'systemic_composite',
 'SOFAproxy_Coag':'hematologic','SOFAproxy_Liver':'hepatic',
 'SOFAproxy_MAP':'cardiovascular','SOFAproxy_Creatinine':'renal',
 'SOFAproxy_CNS':'neurologic','SOFAproxy_Total':'systemic_composite',
 'SOFAproxy_Available':'systemic_composite','SOFAproxy_MaxSoFar':'systemic_composite',
 'HRxResp':'systemic_composite','HRoverResp':'systemic_composite',
 'TempxHR':'systemic_composite','SBPoverResp':'systemic_composite','O2SatoverHR':'systemic_composite',
 'Vasopressor_HoursSinceFirst':'cardiovascular','Vasopressor_HoursSinceLast':'cardiovascular',
 'qSOFA2_HoursSinceFirst':'systemic_composite','qSOFA2_HoursSinceLast':'systemic_composite',
 'SOFA_Resp':'respiratory','SOFA_CV':'cardiovascular','SOFA_Renal':'renal','SOFA_Total':'systemic_composite',
 'SOFA_MetAmongMeasured':'systemic_composite','SOFA_Available':'systemic_composite','SOFA_Delta':'systemic_composite',
 'SOFA_Delta2':'systemic_composite','NEWS2_MetAmongMeasured':'systemic_composite','NEWS2_Available':'systemic_composite'}
TREND_SOURCES=[('HR','cardiovascular'),('MAP','cardiovascular'),('Resp','respiratory'),('Temp','inflammatory'),
               ('SBP','cardiovascular'),('O2Sat','respiratory')]
# 24 h extremes of fresh measurements (intermittent fever spikes, lowest blood pressure, desaturation).
EXTREMES=[('Temp','max','inflammatory'),('Temp','min','inflammatory'),('HR','max','cardiovascular'),('Resp','max','respiratory'),
          ('SBP','min','cardiovascular'),('MAP','min','cardiovascular'),('O2Sat','min','respiratory')]
for _f,_g in TREND_SOURCES:
    for _w in (3,6):
        for _stat in ('Slope','Variance','Skew','Count'):
            GROUPS[f'{_f}_{_stat}{_w}h']=_g
for _f,_k,_g in EXTREMES:GROUPS[f'{_f}_{_k.capitalize()}24h']=_g
ENGINEERED=list(GROUPS)

def _check_hours(h):
    if not np.isfinite(h).all() or (np.diff(h)<=0).any():raise ValueError('Hours must be unique and increasing')

def elapsed_since_event(flags,hours,which='last'):
    """Elapsed hours since first/last OBSERVED positive flag. NaN before any event.
    Unknown flags neither create nor erase events; not time since true latent event.
    """
    h=np.asarray(hours,float);f=np.asarray(flags,float)
    if which not in ('first','last'):raise ValueError(which)
    if len(h)!=len(f):raise ValueError('Length mismatch')
    _check_hours(h)
    if not np.isin(f[np.isfinite(f)],[0,1]).all():raise ValueError('Flags must be 0, 1, or unknown')
    last=np.nan;out=np.full(len(h),np.nan)
    for i,t in enumerate(h):
        if f[i]==1 and (which=='last' or np.isnan(last)):last=t
        if np.isfinite(last):out[i]=t-last
    return out

def fresh_measurement_times(values,hours,ages=None):
    """Measurement time of each row whose value is a NEW observation, else NaN.

    latest_known() exposes non-decreasing measurement times, so a row is fresh when
    its measurement time (Hour-age) exceeds the last fresh time. Without ages, every
    known value is treated as a measurement at its grid hour (legacy behaviour).
    """
    v=np.asarray(values,float);h=np.asarray(hours,float)
    if ages is None:return np.where(np.isfinite(v),h,np.nan)
    et=h-np.asarray(ages,float);out=np.full(len(v),np.nan);last=-np.inf
    for i in range(len(v)):
        if np.isfinite(v[i]) and np.isfinite(et[i]) and et[i]>last+FRESH_TOLERANCE_HOURS:
            if et[i]>h[i]+FRESH_TOLERANCE_HOURS:raise ValueError('Measurement time after cutoff')
            out[i]=et[i];last=et[i]
    return out

def trailing_stats(values,hours,window,times=None):
    """Statistics of the fresh measurements known at each cutoff whose measurement
    time lies in (cutoff-window, cutoff]. Columns: fitted OLS slope per hour against
    real measurement time, sample variance, adjusted Fisher-Pearson skew, count.
    Minimum n=2,2,3 (constant skew is 0). Direct slices keep prefixes exact.
    `times` defaults to the grid hours (each known value is a measurement).
    """
    h=np.asarray(hours,float);v=np.asarray(values,float)
    if len(h)!=len(v):raise ValueError('Length mismatch')
    _check_hours(h)
    x_all=np.where(np.isfinite(v),h,np.nan) if times is None else np.asarray(times,float)
    ok_all=np.isfinite(x_all)&np.isfinite(v)
    out=np.full((len(v),4),np.nan)
    for i,t in enumerate(h):
        sel=ok_all[:i+1]&(x_all[:i+1]>t-window)
        a=v[:i+1][sel];x=x_all[:i+1][sel];n=len(a);out[i,3]=n
        if n<2:continue
        a=a-a.mean();x=x-x.mean();ss=np.dot(a,a);sx=np.dot(x,x)
        out[i,0]=np.dot(x,a)/sx if sx>0 else np.nan;out[i,1]=ss/(n-1)
        if n>=3:out[i,2]=0. if ss==0 else np.sqrt(n*(n-1))/(n-2)*np.mean(a**3)/(ss/n)**1.5
    return out

def engineer_one(d):
    if 'Patient_ID' in d and d.Patient_ID.nunique()!=1:raise ValueError('One stay per call required')
    d=d.copy();h=d.Hour.to_numpy(float)
    _check_hours(h)
    def col(n):return d[n].astype(float) if n in d else pd.Series(np.nan,index=d.index)
    def crit(n,p):
        x=col(n);return p(x).astype(float).where(x.notna())
    def score(n,cuts,descending=False):
        x=col(n);v=sum((x<c if descending else x>=c).astype(float) for c in cuts)
        return v.where(x.notna())
    e={}
    e['DerivedMAP']=(col('SBP')+2*col('DBP'))/3
    e['PulsePressure']=col('SBP')-col('DBP')
    e['BUNCreatinineRatio']=col('BUN')/col('Creatinine').where(col('Creatinine')>0)
    e['AgeSBP']=col('Age')*col('SBP')
    e['qSOFA_Resp']=crit('Resp',lambda x:x>=22)
    e['qSOFA_SBP']=crit('SBP',lambda x:x<=100)
    e['qSOFA_GCS']=crit('GCS',lambda x:x<15)
    q=pd.DataFrame({k:e[k] for k in ['qSOFA_Resp','qSOFA_SBP','qSOFA_GCS']})
    e['qSOFA_Total']=q.sum(axis=1,min_count=3);e['qSOFA_Available']=q.notna().sum(axis=1)
    # Criteria decidable now; the GCS criterion also from partial components (GCS_Below15).
    qm=q.copy()
    if 'GCS_Below15' in d:qm['qSOFA_GCS']=qm.qSOFA_GCS.fillna(col('GCS_Below15'))
    e['qSOFA_MetAmongMeasured']=qm.sum(axis=1,min_count=1)
    e['SOFAproxy_Coag']=score('Platelets',[150,100,50,20],True)
    e['SOFAproxy_Liver']=score('Bilirubin_total',[1.2,2,6,12])
    e['SOFAproxy_MAP']=crit('MAP',lambda x:x<70)   # measured MAP only; never DerivedMAP
    e['SOFAproxy_Creatinine']=score('Creatinine',[1.2,2,3.5,5])
    e['SOFAproxy_CNS']=score('GCS',[15,13,10,6],True)
    s=pd.DataFrame({k:e[k] for k in ['SOFAproxy_Coag','SOFAproxy_Liver','SOFAproxy_MAP','SOFAproxy_Creatinine','SOFAproxy_CNS']})
    e['SOFAproxy_Total']=s.sum(axis=1,min_count=5);e['SOFAproxy_Available']=s.notna().sum(axis=1)
    e['SOFAproxy_MaxSoFar']=e['SOFAproxy_Total'].cummax().ffill()
    # Full SOFA (six organ systems).
    pf=col('PF_Ratio');tube=col('Intubated').eq(1)
    resp=pd.Series(np.select([pf<100,pf<200,pf<300,pf<400],[4.,3.,2.,1.],0.),index=d.index)
    resp=resp.where(tube|(resp<=2),2.).where(pf.notna())
    ne=col('VasopressorDose_NEeq');ino=col('InotropeRecorded').eq(1);mp=col('MAP')
    cv=pd.Series(np.select([ne>.1,ne>0,ino,mp<70],[4.,3.,2.,1.],0.),index=d.index)
    cv=cv.where(mp.notna()|(ne>0)|ino)
    cr=score('Creatinine',[1.2,2,3.5,5])
    uo=col('UrineOutput_24h').where(col('UrineCoverage_24h')>=18)
    ur=pd.Series(np.select([uo<200,uo<500],[4.,3.],0.),index=d.index).where(uo.notna())
    renal=pd.concat([cr,ur],axis=1).max(axis=1,skipna=True)
    e['SOFA_Resp']=resp;e['SOFA_CV']=cv;e['SOFA_Renal']=renal
    comp=pd.DataFrame({'r':resp,'c':cv,'k':renal,'coag':e['SOFAproxy_Coag'],'liv':e['SOFAproxy_Liver'],'cns':e['SOFAproxy_CNS']})
    e['SOFA_Total']=comp.sum(axis=1,min_count=6);e['SOFA_MetAmongMeasured']=comp.sum(axis=1,min_count=1)
    e['SOFA_Available']=comp.notna().sum(axis=1)
    best=comp.cummin()  # best (lowest) value of each component so far; NaN-skipping running minimum
    e['SOFA_Delta']=(comp-best).sum(axis=1,min_count=1)
    e['SOFA_Delta2']=(e['SOFA_Delta']>=2).astype(float).where(e['SOFA_Delta'].notna())
    # NEWS2 among measured components.
    def band(x,edges,points):
        return pd.Series(np.select([c(x) for c in edges],points,0.),index=d.index).where(x.notna())
    rr=col('Resp');sp=col('O2Sat');sb=col('SBP');hr=col('HR');tp=col('Temp')
    news=pd.DataFrame({
     'rr':band(rr,[lambda x:x<=8,lambda x:x<=11,lambda x:x<=20,lambda x:x<=24],[3.,1.,0.,2.]).where(rr.notna()).fillna(np.nan),
     'sp':band(sp,[lambda x:x<=91,lambda x:x<=93,lambda x:x<=95],[3.,2.,1.]),
     'o2':(col('SupplementalO2')*2),
     'sb':band(sb,[lambda x:x<=90,lambda x:x<=100,lambda x:x<=110,lambda x:x>=220],[3.,2.,1.,3.]),
     'hr':band(hr,[lambda x:x<=40,lambda x:x<=50,lambda x:x<=90,lambda x:x<=110,lambda x:x<=130],[3.,1.,0.,1.,2.]),
     'cns':(col('GCS_Below15')*3),
     'tp':band(tp,[lambda x:x<=35,lambda x:x<=36,lambda x:x<=38,lambda x:x<=39],[3.,1.,0.,1.])})
    news.loc[rr>24,'rr']=3.;news.loc[hr>130,'hr']=3.;news.loc[tp>39,'tp']=2.
    e['NEWS2_MetAmongMeasured']=news.sum(axis=1,min_count=1);e['NEWS2_Available']=news.notna().sum(axis=1)
    e['HRxResp']=col('HR')*col('Resp');e['TempxHR']=col('Temp')*col('HR')
    e['HRoverResp']=col('HR')/col('Resp').where(col('Resp')>0)
    e['SBPoverResp']=col('SBP')/col('Resp').where(col('Resp')>0)
    e['O2SatoverHR']=col('O2Sat')/col('HR').where(col('HR')>0)
    # First vs most recent OBSERVED events, real cutoff-hour coordinates.
    pressor=col('VasopressorRecorded').to_numpy()
    e['Vasopressor_HoursSinceFirst']=elapsed_since_event(pressor,h,'first')
    e['Vasopressor_HoursSinceLast']=elapsed_since_event(pressor,h,'last')
    positives=qm.eq(1).sum(axis=1)
    q2=np.where(positives>=2,1.,np.where(qm.notna().all(axis=1),0.,np.nan))  # unknown unless decidable
    e['qSOFA2_HoursSinceFirst']=elapsed_since_event(q2,h,'first')
    e['qSOFA2_HoursSinceLast']=elapsed_since_event(q2,h,'last')
    for f,_ in TREND_SOURCES:
        ages=d[f+'_age'].to_numpy(float) if f+'_age' in d else None
        times=fresh_measurement_times(col(f).to_numpy(),h,ages)
        for w in (3,6):
            a=trailing_stats(col(f),h,w,times)
            for j,stat in enumerate(['Slope','Variance','Skew','Count']):e[f'{f}_{stat}{w}h']=a[:,j]
    for f,kind,_ in EXTREMES:
        ages=d[f+'_age'].to_numpy(float) if f+'_age' in d else None
        times=fresh_measurement_times(col(f).to_numpy(),h,ages);v=col(f).to_numpy()
        ok=np.isfinite(times)&np.isfinite(v);out=np.full(len(h),np.nan)
        for i,t in enumerate(h):
            sel=ok[:i+1]&(times[:i+1]>t-24)
            if sel.any():out[i]=(v[:i+1][sel].max() if kind=='max' else v[:i+1][sel].min())
        e[f'{f}_{kind.capitalize()}24h']=out
    e=pd.DataFrame(e,index=d.index)[ENGINEERED].replace([np.inf,-np.inf],np.nan)
    masks=e.notna().astype(float).add_suffix('_observed')
    # No overwriting of measured MAP, original SIRS criteria, or ShockIndex.
    if set(e)&set(d):raise ValueError('Features already engineered')
    return pd.concat([d,e,masks],axis=1)

def engineer_frame(d):
    if d.duplicated(['Patient_ID','Hour']).any():raise ValueError('Duplicate patient-hour')
    return pd.concat([engineer_one(g.sort_values('Hour')) for _,g in d.groupby('Patient_ID',sort=False)],ignore_index=True)
