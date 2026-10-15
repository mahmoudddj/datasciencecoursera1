"""Challenge-compatible trajectory scoring, distinct from incident risk metrics."""
import numpy as np
import pandas as pd
from official_evaluate_sepsis_score import compute_prediction_utility as official_utility

SCORER_CONTRACT='official-467c49b-regular-hourly-step-labels-v1'

def alarm_policy(prob,hours,threshold,persistence=1,min_rise=0.,latch=False):
    h=np.asarray(hours,float);p=np.asarray(prob,float)
    if len(p)!=len(h) or (np.diff(h)<=0).any():raise ValueError('Invalid time coordinates')
    if persistence<1:raise ValueError('Persistence >=1')
    a=np.zeros(len(p),int);start=None;count=0;latched=False
    for i,value in enumerate(p):
        if i and h[i]-h[i-1]!=1:count=0;start=None
        if value>=threshold:
            if count==0:start=i
            count+=1
            if count>=persistence and value-p[start]>=min_rise:latched=True;a[i]=1
        else:count=0;start=None
        if latch and latched:a[i]=1
    return a

def normalized_utility(frames,threshold,policy=None):
    observed=best=inaction=0.;n=0
    for g in frames:
        h=g.Hour.to_numpy(float);y=g.StepLabel.to_numpy(int)
        if len(h)<1 or (np.diff(h)!=1).any():raise ValueError('Official utility requires uncompressed contiguous hourly trajectories')
        if not np.isin(y,[0,1]).all() or (np.diff(y)<0).any():raise ValueError('Expected challenge step labels')
        pred=alarm_policy(g.risk,h,threshold,**(policy or {}))
        ideal=np.zeros(len(y),int)
        if y.any():
            onset=int(np.argmax(y))+6
            ideal[max(0,onset-12):min(len(y),onset+4)]=1
        observed+=official_utility(y,pred);best+=official_utility(y,ideal);inaction+=official_utility(y,np.zeros(len(y),int));n+=1
    return {'normalized_utility':(observed-inaction)/(best-inaction) if best!=inaction else np.nan,
        'utility_observed':float(observed),'utility_best':float(best),'utility_inaction':float(inaction),'trajectory_stays':n,
        'scorer':SCORER_CONTRACT,'utility_scope':'restricted_hourly_trajectory_external_not_original_challenge_benchmark'}

def challenge_event_metrics(frames,threshold,policy):
    rows=[]
    for g in frames:
        h=g.Hour.to_numpy(float);o=float(g.OnsetHour.iloc[0]);binary=alarm_policy(g.risk,h,threshold,**policy)
        # Episodes begin on a confirmed 0->1 transition, not on a later-discovered start.
        alarm=h[(binary==1)&(np.r_[0,binary[:-1]]==0)]
        lead=o-alarm if np.isfinite(o) else np.full(len(alarm),np.nan)
        timely=(lead>0)&(lead<=6);late=lead<=0;early=lead>6
        evaluable=np.isfinite(o) and ((h<o)&(h>=o-6)).any()
        rows.append({'Patient_ID':g.Patient_ID.iloc[0],'Group_ID':g.Group_ID.iloc[0],
          'event_evaluable':bool(evaluable),'detected':bool(timely.any()),'alarms':len(alarm),
          'timely_alarms':int(timely.sum()),'late_alarms':int(late.sum()),'early_alarms':int(early.sum()),
          'nonseptic_alarms':len(alarm) if not np.isfinite(o) else 0,
          'warning_hours':float(lead[timely].max()) if timely.any() else np.nan,'hours':len(h)})
    a=pd.DataFrame(rows);ev=a[a.event_evaluable];total=a.alarms.sum();false=total-a.timely_alarms.sum()
    return {'event_sensitivity':float(ev.detected.mean()) if len(ev) else np.nan,
       'event_denominator':len(ev),'missed_events':int((~ev.detected).sum()),
       'alarm_PPV':float(a.timely_alarms.sum()/total) if total else np.nan,
       'false_alarm_episodes_per_patient_day':float(false/a.hours.sum()*24),
       'median_warning_hours_detected':float(ev.warning_hours.median()) if ev.warning_hours.notna().any() else np.nan,
       'detected_event_denominator':int(ev.detected.sum()),'late_alarm_episodes':int(a.late_alarms.sum()),
       'early_alarm_episodes':int(a.early_alarms.sum())},a
