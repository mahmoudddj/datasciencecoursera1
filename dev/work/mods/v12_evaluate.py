"""Stage-2 scoring passes on SAVED predictions (protocol 10c.2 items 8, 10, 16, 17). No model is retrained here.
A prediction frame has the columns of v9_train.predict after apply_calibration: Patient_ID, Group_ID, Hospital_ID, Hour,
y, logit, risk, Eligible, OnsetHour (+ FirstAntibioticAroundOnset). Stay tables are indexed by Patient_ID."""
import numpy as np
import pandas as pd
from v9_train import evaluate
from v11_train import evaluate_v11,alarm_records_v11,quantile_threshold,alarm_fraction

def relabel(d,onset_by_stay,horizon):
    """Re-derive y, Eligible and OnsetHour from an alternative onset per stay (hours before the onset are eligible;
    the `horizon` hours before it are positive). Stays absent from the table keep no onset."""
    d=d.copy();on=d.Patient_ID.astype(str).map(onset_by_stay).astype(float).to_numpy();h=d.Hour.to_numpy(float)
    d['OnsetHour']=on;has=np.isfinite(on)
    d['y']=np.where(has&(h>=on-horizon)&(h<on),1,0).astype(np.int8);d['Eligible']=np.where(has,(h<on),True).astype(np.int8)
    return d[d.Eligible.eq(1)]

def pre_treatment(d,first_treatment_by_stay):
    """Keep only the hours strictly before the stay's first treatment indicator (antibiotic or culture order); stays
    without one keep every hour. After Kamran et al. 2024."""
    ft=d.Patient_ID.astype(str).map(first_treatment_by_stay).astype(float).to_numpy()
    return d[~np.isfinite(ft)|(d.Hour.to_numpy(float)<ft)]

def pre_treatment_summary(d_pre,threshold,first_treatment_by_stay,persistence=1):
    """Stay-level reading of the pre-treatment evaluation (Kamran et al. 2024): among septic stays WITH a treatment
    indicator, the share whose risk reached the threshold (for `persistence` consecutive hours) before the first
    treatment, and the median hours from that first alarm to the treatment. Septic stays whose 6 h window lies entirely
    after the treatment are counted in the denominator (they cannot be detected before the clinician acted)."""
    rows=[]
    for pid,g in d_pre[d_pre.OnsetHour.notna()].groupby('Patient_ID',sort=False,observed=True):
        ft=first_treatment_by_stay.get(str(pid),np.nan)
        if not np.isfinite(ft):continue
        g=g.sort_values('Hour');above=(g.risk.to_numpy()>=threshold);h=g.Hour.to_numpy(float);run=0;first=np.nan
        for i,(a,t) in enumerate(zip(above,h)):
            run=run+1 if (a and (i==0 or h[i]-h[i-1]<=1.001)) else (1 if a else 0)
            if a and run>=persistence:first=t;break
        rows.append({'alarm_before_treatment':np.isfinite(first),'hours_before_treatment':ft-first if np.isfinite(first) else np.nan})
    if not rows:return {'pre_treatment_septic_stays':0}
    r=pd.DataFrame(rows)
    return {'pre_treatment_septic_stays':int(len(r)),'alarm_before_treatment_fraction':float(r.alarm_before_treatment.mean()),
            'median_hours_alarm_before_treatment':float(r.hours_before_treatment.median()) if r.hours_before_treatment.notna().any() else np.nan}

def documentation_strata(d,documented_by_stay):
    """Two frames: documented positives with all controls; undocumented positives with all controls."""
    doc=d.Patient_ID.astype(str).map(documented_by_stay);pos=d.OnsetHour.notna()
    return {'documented':d[~pos|doc.eq(True)],'undocumented':d[~pos|doc.eq(False)]}

def score(d,threshold,cfg,persistence=1,fresh_only=False):
    if d.y.nunique()<2:return {'not_estimable':True,'eligible_hours':int(len(d))}
    m,_,_=evaluate_v11(d,threshold,cfg,persistence,fresh_only);return m

# ---- abstention variants (item 16) ----
def alarm_records_abstain(d,threshold,abstain,mode,cooldown=6,horizon=6,persistence=2):
    """Alarm records under an abstention rule. `abstain` is a boolean array aligned with d. Modes: 'reset' (an abstained
    hour has risk 0 and breaks the persistence run; the section 9 behaviour), 'transparent' (abstained hours neither
    count nor reset: the run continues over them and the alarm needs `persistence` determinate hours above threshold),
    'gated' (the run counts every hour, but an alarm can fire only on a determinate hour and is deferred otherwise)."""
    rows=[];d=d.assign(_abs=np.asarray(abstain,bool))
    for pid,g in d.groupby('Patient_ID',sort=False,observed=True):
        g=g.sort_values('Hour');onset=g.OnsetHour.iloc[0];last=-np.inf;false=0;leads=[];total=0;run=0;prev_h=None;pending=False
        for h,p,ab in zip(g.Hour,g.risk,g._abs):
            if mode=='reset' and ab:p=0.
            if mode=='transparent' and ab:
                continue   # the hour is invisible to the policy; prev_h is not advanced, so the run survives it
            contiguous=prev_h is not None and h-prev_h<=(1.001 if mode!='transparent' else 1e9)
            run=(run+1 if (contiguous and p>=threshold) else (1 if p>=threshold else 0));prev_h=h
            fire=p>=threshold and run>=persistence and h-last>=cooldown
            if mode=='gated':
                if fire and ab:pending=True;fire=False
                elif pending and not ab and p>=threshold and h-last>=cooldown:fire=True
                if not (p>=threshold):pending=False
            if fire:
                last=h;total+=1;pending=False
                if pd.notna(onset) and 0<onset-h<=horizon:leads.append(onset-h)
                else:false+=1
        rows.append({'Patient_ID':pid,'Group_ID':g.Group_ID.iloc[0],'event_evaluable':bool((g.y==1).any()),'detected':bool(leads),
                     'warning_hours':max(leads) if leads else np.nan,'false_alarms':false,'alarms':total,'at_risk_hours':len(g)})
    return pd.DataFrame(rows)

def abstention_rows(d,ood,tau,threshold,cfg,persistence=2):
    """One row per mode: event metrics under the abstention rule plus the abstained fractions (all hours; septic pre-onset hours)."""
    dd=d.assign(Patient_ID=d.Patient_ID.astype(str)).merge(ood.assign(Patient_ID=ood.Patient_ID.astype(str)),on=['Patient_ID','Hour'],how='left')
    ab=dd.ood.fillna(0).to_numpy()>tau;pre=dd.OnsetHour.notna()&(dd.Hour<dd.OnsetHour)
    rows=[]
    for mode in ('reset','transparent','gated'):
        a=alarm_records_abstain(dd,threshold,ab,mode,cfg['alarm_cooldown'],cfg['horizon'],persistence);ev=a[a.event_evaluable]
        rows.append({'abstention':mode,'persistence':persistence,'event_sensitivity':float(ev.detected.mean()) if len(ev) else np.nan,
                     'false_alarms_per_patient_day':float(a.false_alarms.sum()/a.at_risk_hours.sum()*24),'median_warning_hours_detected':float(ev.warning_hours.median()) if ev.warning_hours.notna().any() else np.nan,
                     'abstained_fraction_all_hours':float(ab.mean()),'abstained_fraction_septic_preonset_hours':float(ab[pre.to_numpy()].mean()) if pre.any() else np.nan})
    return pd.DataFrame(rows)

def adopt_abstention(rows,reference,tolerance_h=.5):
    """Adoption rule (item 16): a variant replaces the reference policy only if false alarms fall at equal or better event
    sensitivity and the median warning time is not shortened by more than `tolerance_h`."""
    ref=rows[rows.abstention.eq(reference)].iloc[0];out=[]
    for _,r in rows.iterrows():
        ok=(r.false_alarms_per_patient_day<ref.false_alarms_per_patient_day)and(r.event_sensitivity>=ref.event_sensitivity)and(not(np.isfinite(r.median_warning_hours_detected) and np.isfinite(ref.median_warning_hours_detected)) or r.median_warning_hours_detected>=ref.median_warning_hours_detected-tolerance_h)
        out.append({'abstention':r.abstention,'adoptable':bool(ok) and r.abstention!=reference})
    return pd.DataFrame(out)

# ---- threshold transport per hospital (item 17a) ----
def threshold_transport(d,chosen,cfg,min_hours=10000,min_stays=20):
    """For each hospital with at least `min_stays` scored stays: the alarm fraction, event sensitivity and PPV under
    (a) the fixed probability threshold and (b) the quantile operating point computed on that hospital's own hours
    (falling back to the fixed threshold below `min_hours`). Returns the per-hospital table and its dispersion."""
    rows=[]
    for hosp,g in d.groupby('Hospital_ID',observed=True):
        if g.Patient_ID.nunique()<min_stays:continue
        for rule in ('absolute','quantile'):
            thr=chosen['threshold'] if rule=='absolute' else (quantile_threshold(g,chosen['alarm_fraction'],min_hours) or chosen['threshold'])
            a=alarm_records_v11(g,thr,cfg['alarm_cooldown'],cfg['horizon'],cfg.get('persistence',1),bool(cfg.get('fresh_only',False)));ev=a[a.event_evaluable]
            rows.append({'Hospital_ID':str(hosp),'rule':rule,'stays':int(g.Patient_ID.nunique()),'events':int(len(ev)),'threshold':float(thr),'alarm_fraction':alarm_fraction(g,thr),
                         'event_sensitivity':float(ev.detected.mean()) if len(ev)>=11 else np.nan,'false_alarms_per_patient_day':float(a.false_alarms.sum()/a.at_risk_hours.sum()*24),
                         'alarm_PPV':float((a.alarms-a.false_alarms).sum()/a.alarms.sum()) if a.alarms.sum()>=11 else np.nan})
    t=pd.DataFrame(rows)
    disp=t.groupby('rule').agg(hospitals=('Hospital_ID','nunique'),alarm_fraction_iqr=('alarm_fraction',lambda s:float(s.quantile(.75)-s.quantile(.25))),
                               sensitivity_iqr=('event_sensitivity',lambda s:float(s.quantile(.75)-s.quantile(.25))),ppv_iqr=('alarm_PPV',lambda s:float(s.quantile(.75)-s.quantile(.25))),
                               false_alarm_iqr=('false_alarms_per_patient_day',lambda s:float(s.quantile(.75)-s.quantile(.25)))).reset_index() if len(t) else pd.DataFrame()
    return t,disp

# ---- suspicion target readings (item 9) ----
def suspicion_readings(d,suspicion_by_stay,cfg,chosen,horizons=(3,6)):
    """Event metrics of a suspicion-anchored model at its own 3 h horizon and at a 6 h reading, on the same predictions."""
    rows=[]
    for h in horizons:
        dh=relabel(d,suspicion_by_stay,h);m=score(dh,chosen['threshold'],{**cfg,'horizon':h},cfg.get('persistence',1),bool(cfg.get('fresh_only',False)))
        rows.append({'reading_horizon_h':h,**m})
    return pd.DataFrame(rows)
