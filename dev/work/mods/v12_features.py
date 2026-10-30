"""Baseline-relative features (protocol 10c.2 item 7, revised 31 Oct 2026).

For each channel c with a measurement-age column c_age, the NEW measurements are recovered from the hourly grid (a new
value at hour t when the age did not grow by one hour since t-1) and placed at their measurement time t - age. The
baseline at hour t is the median of the new measurements made at or before min(t - HORIZON, MAX_BASE) hours; with fewer
than MIN_BASE measurements it is the first measurement of the stay if that measurement is at or before t - HORIZON, else
undefined. Features per channel: c_BaseDev (carried value minus baseline), c_BaseZ (deviation over the interquartile range
of the baseline set; undefined below MIN_BASE), c_BaseDevSlope6h (least-squares slope of the deviation over the new
measurements of the last SLOPE_WINDOW hours; at least three), c_BaseDevMax24h and c_BaseDevMin24h (extremes of the
deviation over the new measurements of the last 24 h). Causal by construction: nothing after hour t is read.
"""
import numpy as np
import pandas as pd

CHANNELS=['HR','MAP','SBP','DBP','Resp','Temp','O2Sat','Lactate','Creatinine','Bilirubin_total','Platelets','WBC']
HORIZON=6.0;MAX_BASE=24.0;MIN_BASE=3;SLOPE_WINDOW=6.0;EXTREME_WINDOW=24.0
TOL=1e-3

def new_measurements(hours,values,ages):
    """Measurement times and values recovered from the hourly grid (see module docstring)."""
    h=np.asarray(hours,float);v=np.asarray(values,float);a=np.asarray(ages,float)
    prev=np.concatenate([[np.nan],a[:-1]])
    new=np.isfinite(a)&np.isfinite(v)&(~np.isfinite(prev)|(a<prev+1-TOL))
    t=h[new]-a[new];return t,v[new]

def baseline_relative_channel(hours,values,ages,horizon=HORIZON,max_base=MAX_BASE,min_base=MIN_BASE):
    h=np.asarray(hours,float);v=np.asarray(values,float);n=len(h)
    t_meas,v_meas=new_measurements(h,v,ages)
    dev=np.full(n,np.nan);z=np.full(n,np.nan);slope=np.full(n,np.nan);mx=np.full(n,np.nan);mn=np.full(n,np.nan)
    for i,t in enumerate(h):
        cut=min(t-horizon,max_base);base_set=v_meas[t_meas<=cut]
        if len(base_set)>=min_base:base=np.median(base_set);iqr=np.subtract(*np.percentile(base_set,[75,25]))
        elif len(base_set)>=1:base=base_set[0];iqr=np.nan
        else:continue
        if np.isfinite(v[i]):
            dev[i]=v[i]-base
            if np.isfinite(iqr) and iqr>0:z[i]=dev[i]/iqr
        win=(t_meas>t-SLOPE_WINDOW)&(t_meas<=t)
        if win.sum()>=3 and np.ptp(t_meas[win])>0:slope[i]=float(np.polyfit(t_meas[win],v_meas[win]-base,1)[0])
        ext=(t_meas>t-EXTREME_WINDOW)&(t_meas<=t)
        if ext.any():d=v_meas[ext]-base;mx[i]=d.max();mn[i]=d.min()
    return {'BaseDev':dev,'BaseZ':z,'BaseDevSlope6h':slope,'BaseDevMax24h':mx,'BaseDevMin24h':mn}

def baseline_relative(frame,channels=CHANNELS,**kw):
    """Append the baseline-relative columns for every channel present with its age column. Returns the new columns only."""
    out={}
    for c in channels:
        if c in frame and c+'_age' in frame:
            for k,arr in baseline_relative_channel(frame.Hour.to_numpy(float),frame[c].to_numpy(float),frame[c+'_age'].to_numpy(float),**kw).items():out[f'{c}_{k}']=arr
    return pd.DataFrame(out,index=frame.index)

def baseline_relative_columns(channels=CHANNELS):
    return [f'{c}_{k}' for c in channels for k in ('BaseDev','BaseZ','BaseDevSlope6h','BaseDevMax24h','BaseDevMin24h')]
