"""Synthetic engineering-only data. Never a clinical extraction fallback."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from v9_data import build_sequence

def make_fixture(root,n=160):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(42)
    ix=[];features=None
    for ds in ['miiv','eicu']:
        parts=[];offset=0;dest=root/(ds+'_synthetic.parquet')
        for i in range(n):
            septic=i%2;onset=16. if septic else np.nan
            h=np.arange(1,25,dtype=float);events=[]
            for f,mean,sd,unit in [('HR',85,12,'bpm'),('SBP',115,15,'mmHg'),('DBP',70,10,'mmHg'),('MAP',85,12,'mmHg'),('Resp',18,5,'/min'),('Temp',37,1,'C'),('O2Sat',96,2,'%'),('GCS',14,1,''),('Creatinine',1.2,.5,'mg/dl'),('BUN',20,6,'mg/dl'),('Platelets',180,40,''),('Bilirubin_total',1,.4,'mg/dl'),('WBC',8,3,''),('Bands',4,3,'%'),('PaCO2',38,5,''),('Weight',75,10,'kg'),('UrineOutput',40,12,'ml')]:
                v=np.maximum(.1,mean+rng.normal(0,sd,len(h)))
                if f=='HR':v+=septic*np.maximum(0,h-7)*2
                for t,value in zip(h,v):
                    if rng.random()<.12:continue
                    events.append({'feature':f,'value':value,'event_hour':t,'available_hour':t+(1 if f=='Creatinine' else 0),'unit':unit})
            meta={'followup_end':24.,'OnsetHour':onset,'Age':float(40+i%45),'Gender':float(i%2)}
            seq=build_sequence(pd.DataFrame(events),meta,24,6)
            feats=[c for c in seq if c not in ['Hour','Eligible','SepsisLabel']]
            if features is None:features=feats
            assert features==feats
            pid=f'{ds}|synthetic_{i}';seq.insert(0,'Patient_ID',pid);parts.append(seq)
            ix.append({'Dataset':ds,'Patient_ID':pid,'Group_ID':pid,'Hospital_ID':f'synthetic_h{i%6}' if ds=='eicu' else 'synthetic_BIDMC',
                **meta,'file':str(dest.resolve()),'offset':offset,'length':len(seq),'eligible_positive':septic,'synthetic':True})
            offset+=len(seq)
        pd.concat(parts,ignore_index=True).to_parquet(dest,index=False)
    index=pd.DataFrame(ix);index.to_parquet(root/'index.parquet',index=False)
    (root/'schema.json').write_text(json.dumps(features))
    return index,features

def make_legacy_fixture(root,nsource=80,ntarget=20):
    """Synthetic PhysioNet-like SPARSE source stays (vitals ~hourly with gaps, labs every
    6-12 h) and synthetic MIMIC/eICU-like target trajectories built through the real
    v9 build_sequence adapter (availability TTL, ages, StepLabel from onset-6 h)."""
    from v10_legacy import DEFAULT_BASE
    root=Path(root);root.mkdir(parents=True,exist_ok=True);rng=np.random.default_rng(21)
    source=[];target=[]
    means=dict(zip(DEFAULT_BASE,[85,96,37,115,85,70,18,1.2,20,180,1,8,60,1]))
    labs={'Creatinine','BUN','Platelets','Bilirubin_total','WBC'}
    def frame(i,pid):
        h=np.arange(1,25);septic=i%2
        d=pd.DataFrame({'Patient_ID':pid,'Hour':h,'SepsisLabel':((h>=10)&bool(septic)).astype(int)})
        for f,m in means.items():
            v=m+rng.normal(0,max(abs(m)*.04,.01),len(h))
            if f in labs:v=np.where((h-1-i%5)%8==0,v,np.nan)
            elif f not in ['Age','Gender']:v=np.where(rng.random(len(h))<.25,np.nan,v)
            d[f]=v
        d['Gender']=float(i%2);d['Age']=float(40+i%40)
        if septic:d['HR']+=np.maximum(h-7,0)*2
        return d
    sd=root/'source';sd.mkdir(exist_ok=True)
    for i in range(nsource):
        pid=f'synthetic_source_{i}';p=sd/(pid+'.parquet');frame(i,pid).to_parquet(p,index=False)
        source.append({'Patient_ID':pid,'file':str(p),'Outcome':i%2})
    for ds in ['miiv','eicu']:
        parts=[];offset=0;p=root/(ds+'_full_synthetic.parquet')
        for i in range(ntarget):
            onset=16. if i%2 else np.nan;events=[]
            for f,m in means.items():
                if f in ['Age','Gender']:continue
                every=8 if f in labs else 1
                for t in np.arange(0.,24.,every)+rng.uniform(0,.8):
                    v=m+rng.normal(0,max(abs(m)*.04,.01))+(2*max(t-7,0) if (f=='HR' and i%2) else 0)
                    events.append({'feature':f,'value':v,'event_hour':t,'available_hour':t+(1.5 if f in labs else .1),'unit':''})
            d=build_sequence(pd.DataFrame(events),{'followup_end':24.,'OnsetHour':np.nan,'Age':float(40+i%40),'Gender':float(i%2)},24,6)
            d=d.drop(columns=['Eligible','SepsisLabel']);d['StepLabel']=((d.Hour>=onset-6)&np.isfinite(onset)).astype(int)
            d['HospAdmTime']=-float(i%3);pid=f'{ds}|synthetic_target_{i}';d.insert(0,'Patient_ID',pid);parts.append(d)
            target.append({'Patient_ID':pid,'Group_ID':pid,'Hospital_ID':f'synthetic_h{i%6}','Dataset':ds,'OnsetHour':onset,'file':str(p),'offset':offset,'length':len(d)})
            offset+=len(d)
        pd.concat(parts,ignore_index=True).to_parquet(p,index=False)
    return pd.DataFrame(source),pd.DataFrame(target)

def make_raw_schema_fixture(root,n=8):
    """Schema-shaped synthetic RAW MIMIC-IV/eICU CSVs plus YAIB-like cohort folders
    (outc/sta parquet and unwindowed label batches). Engineering dry run only."""
    root=Path(root);rng=np.random.default_rng(5);out={}
    ids=list(range(101,101+n));onset={i:(12. if k%3==1 else 5. if k%3==2 and k>4 else np.nan) for k,i in enumerate(ids)}
    for ds in ['miiv','eicu']:
        raw=root/'raw'/ds;coh=root/'cohort'/ds;b=coh/'batches/plan/00000';b.mkdir(parents=True,exist_ok=True)
        if ds=='miiv':
            (raw/'icu').mkdir(parents=True,exist_ok=True);(raw/'hosp').mkdir(exist_ok=True)
            t0=pd.Timestamp('2150-01-01')
            pd.DataFrame({'stay_id':ids,'hadm_id':[i+1000 for i in ids],'subject_id':[i//2 for i in ids],
                'intime':[str(t0)]*n,'outtime':[str(t0+pd.Timedelta(hours=30))]*n}).to_csv(raw/'icu/icustays.csv',index=False)
            pd.DataFrame({'hadm_id':[i+1000 for i in ids],'admittime':[str(t0-pd.Timedelta(hours=5))]*n,'admission_location':'EMERGENCY ROOM'}).to_csv(raw/'hosp/admissions.csv',index=False)
            rows=[];labs=[];outs=[]
            for i in ids:
                for h in range(0,30):
                    ts=t0+pd.Timedelta(hours=h,minutes=int(rng.integers(0,50)))
                    for item,m in [(220045,90),(220179,115),(220180,65),(220181,82),(220210,19),(223762,37.2),(220277,96)]:
                        rows.append({'stay_id':i,'itemid':item,'charttime':str(ts),'storetime':str(ts+pd.Timedelta(minutes=10)),'valuenum':m+rng.normal(0,3),'value':'x','valueuom':''})
                    outs.append({'stay_id':i,'itemid':226559,'charttime':str(ts),'storetime':str(ts+pd.Timedelta(minutes=5)),'value':40+rng.normal(0,5),'valueuom':'mL'})
                    if h%8==0:labs.append({'hadm_id':i+1000,'itemid':50912,'charttime':str(ts),'storetime':str(ts+pd.Timedelta(hours=1)),'valuenum':1.1,'valueuom':'mg/dL'})
            pd.DataFrame(rows).to_csv(raw/'icu/chartevents.csv',index=False);pd.DataFrame(outs).to_csv(raw/'icu/outputevents.csv',index=False)
            pd.DataFrame(labs).to_csv(raw/'hosp/labevents.csv',index=False)
        else:
            raw.mkdir(parents=True,exist_ok=True)
            pd.DataFrame({'patientunitstayid':ids,'uniquepid':[f'u{i//2}' for i in ids],'hospitalid':[1,2]*(n//2),'unitadmitsource':'Emergency Department',
                'apacheadmissiondx':'Sepsis, pulmonary','hospitaladmitoffset':-300,'unitdischargeoffset':30*60}).to_csv(raw/'patient.csv',index=False)
            vit=[];io_=[];lab=[]
            for i in ids:
                for h in range(0,30):
                    off=h*60+int(rng.integers(0,50))
                    vit.append({'patientunitstayid':i,'observationoffset':off,'heartrate':90+rng.normal(0,3),'systemicsystolic':115,'systemicdiastolic':65,'systemicmean':82,'respiration':19,'temperature':37.1,'sao2':96})
                    io_.append({'patientunitstayid':i,'intakeoutputoffset':off,'intakeoutputentryoffset':off+10,'cellpath':'flowsheet|Output (ml)|Urine','celllabel':'Urine','cellvaluenumeric':40})
                    if h%8==0:lab.append({'patientunitstayid':i,'labresultoffset':off,'labresultrevisedoffset':off+60,'labname':'creatinine','labresult':'1.1','labmeasurenamesystem':'mg/dL'})
            pd.DataFrame(vit).to_csv(raw/'vitalPeriodic.csv',index=False);pd.DataFrame(io_).to_csv(raw/'intakeOutput.csv',index=False);pd.DataFrame(lab).to_csv(raw/'lab.csv',index=False)
        outc=[];lab_ev=[]
        for i in ids:
            end=min(30.,onset[i]+6) if np.isfinite(onset[i]) else 30.
            for h in range(0,int(end)+1):
                outc.append({'stay_id':i,'time':float(h),'label':int(np.isfinite(onset[i]) and abs(h-onset[i])<=6)})
            lab_ev.append({'stay_id':i,'time':onset[i] if np.isfinite(onset[i]) else 0.,'sep3_alt':True if np.isfinite(onset[i]) else None})
        pd.DataFrame(outc).to_parquet(coh/'outc.parquet');pd.DataFrame({'stay_id':ids,'age':65.,'sex':'Male'}).to_parquet(coh/'sta.parquet')
        pd.DataFrame(lab_ev).to_parquet(b/'labels.parquet');(b/'ids.json').write_text(json.dumps(ids));(b/'labels_complete.json').write_text('{}')
        out[ds]=(raw,coh)
    return out,onset
