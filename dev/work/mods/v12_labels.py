"""Stage-2 labels (protocol 10c.2 items 9, 10, 15): the suspicion-anchored event and its hourly label; documented and
positive-unlabelled soft labels; the pre-treatment hour mask. Pure functions on small frames; no database access.

Suspicion-anchored event (item 9): the first systemic antibiotic course of the ICU stay starting at or after ICU hour
START_MIN (6), with no systemic antibiotic start in the preceding WASHOUT hours (72), and CONTINUED: the course intervals
beginning at or after that start cover [start, start + CONTINUATION] (72 h) with no uncovered gap longer than MAX_GAP (24 h),
the YAIB abx_cont rule, or the patient dies within CONTINUATION hours. A start without a stop time covers DEFAULT_COVER
hours (24, one administration day). Hours are hours since ICU admission.
"""
import numpy as np
import pandas as pd

START_MIN=6.0;WASHOUT=72.0;CONTINUATION=72.0;MAX_GAP=24.0;DEFAULT_COVER=24.0

def _covered(intervals,start,end,max_gap):
    """True when the union of intervals (list of (s,e)) covers [start,end] with no gap longer than max_gap."""
    iv=sorted((max(s,start),e) for s,e in intervals if np.isfinite(s) and s<=end and (not np.isfinite(e) or e>=start))
    if not iv:return False
    cur=start
    for s,e in iv:
        if s-cur>max_gap:return False
        e=e if np.isfinite(e) else s+DEFAULT_COVER
        cur=max(cur,e)
        if cur>=end:return True
    return (end-cur)<=max_gap and cur>start

def suspicion_event(starts,stops,death_hour=np.nan,start_min=START_MIN,washout=WASHOUT,continuation=CONTINUATION,max_gap=MAX_GAP):
    """Event hour for ONE stay from its antibiotic course starts and stops (arrays of hours; stop may be NaN), or NaN.
    Also returns the reason the first candidate was rejected, for the audit."""
    s=np.asarray(starts,float);e=np.asarray(stops,float) if stops is not None else np.full(len(s),np.nan)
    e=np.where(np.isfinite(e),e,s+DEFAULT_COVER);order=np.argsort(s);s=s[order];e=e[order]
    reason='no_start_after_hour_%g'%start_min
    for i,t in enumerate(s):
        if not np.isfinite(t) or t<start_min:continue
        if ((s>t-washout)&(s<t)).any():reason='antibiotic_in_washout';continue
        dies=np.isfinite(death_hour) and death_hour<=t+continuation
        if dies or _covered(list(zip(s[s>=t],e[s>=t])),t,t+continuation,max_gap):return float(t),'event'
        reason='course_not_continued';continue
    return np.nan,reason

def suspicion_events(courses,death_hours=None,**kw):
    """Per-stay events from a frame (stay_id, start, stop). death_hours: Series indexed by stay_id. Returns a frame
    (stay_id, suspicion_hour, reason)."""
    rows=[]
    dh=death_hours if death_hours is not None else pd.Series(dtype=float)
    for sid,g in courses.groupby('stay_id'):
        h,r=suspicion_event(g.start.to_numpy(float),g.stop.to_numpy(float) if 'stop' in g else None,float(dh.get(sid,np.nan)),**kw)
        rows.append({'stay_id':sid,'suspicion_hour':h,'reason':r})
    return pd.DataFrame(rows,columns=['stay_id','suspicion_hour','reason'])

def suspicion_label(hours,event_hour,horizon=3.0,followup_end=None):
    """Hourly label and eligibility for the suspicion-anchored target. Positive: event-horizon <= hour < event.
    Eligible: hours before the event (censored at the event); without an event, hours whose horizon lies inside the follow-up."""
    h=np.asarray(hours,float)
    if np.isfinite(event_hour):
        y=((h>=event_hour-horizon)&(h<event_hour)).astype(float);elig=(h<event_hour).astype(float)
    else:
        y=np.zeros(len(h));elig=np.ones(len(h)) if followup_end is None else (h+horizon<=followup_end).astype(float)
    return y,elig

def pre_treatment_mask(hours,first_treatment_hour):
    """Hours strictly before the first treatment indicator of the stay (antibiotic or culture order); all hours when none."""
    h=np.asarray(hours,float)
    return np.ones(len(h),bool) if not np.isfinite(first_treatment_hour) else h<first_treatment_hour

def documentation_prior(stays):
    """Share of documented sepsis among operational positives, per database: the class prior for the PU soft label.
    `stays` has columns Dataset, operational_positive (0/1), documented (0/1)."""
    pos=stays[stays.operational_positive.eq(1)]
    return pos.groupby('Dataset').documented.mean().to_dict()

def stay_soft_value(operational_positive,documented,prior):
    """Positive-unlabelled soft value for one stay: 1 if documented positive, the prior if undocumented positive, 0 otherwise."""
    if not operational_positive:return 0.0
    return 1.0 if documented else float(prior)

def label_variant(hourly_label,stay_value):
    """Hourly label under a stay-level variant: the operational hourly label scaled by the stay value
    (1 keeps it, the prior softens it, 0 removes it for the documented-and-operational variant)."""
    return np.asarray(hourly_label,float)*float(stay_value)
