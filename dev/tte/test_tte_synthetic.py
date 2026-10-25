"""Syntax/logic smoke test of the TTE feasibility cells on tiny synthetic tables with the real column names.
Numbers are meaningless; the test only proves every query runs on both schemas."""
import gzip,io,os,sys,tempfile,random
from pathlib import Path
import pandas as pd,numpy as np
sys.path.insert(0,str(Path(__file__).parent));from tte_feasibility_cells import CELLS
rng=np.random.default_rng(0);T0=pd.Timestamp('2150-01-01')
def gz(path,df):
    path.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(path,'wt') as f:df.to_csv(f,index=False)
with tempfile.TemporaryDirectory() as td:
    td=Path(td);M=td/'mimic';E=td/'eicu';N=300
    # ---- MIMIC-IV ----
    stays=pd.DataFrame({'subject_id':range(1,N+1),'hadm_id':range(1001,1001+N),'stay_id':range(5001,5001+N),'first_careunit':'MICU',
        'intime':[T0+pd.Timedelta(days=i) for i in range(N)]});stays['outtime']=stays.intime+pd.Timedelta(hours=96)
    gz(M/'icu/icustays.csv.gz',stays)
    gz(M/'hosp/admissions.csv.gz',pd.DataFrame({'subject_id':stays.subject_id,'hadm_id':stays.hadm_id,'admittime':stays.intime-pd.Timedelta(hours=5),'dischtime':stays.outtime+pd.Timedelta(days=2),'hospital_expire_flag':rng.integers(0,2,N),'admission_type':'EW EMER.'}))
    gz(M/'hosp/patients.csv.gz',pd.DataFrame({'subject_id':stays.subject_id,'gender':['M','F']*(N//2),'anchor_age':rng.integers(20,90,N)}))
    items=pd.DataFrame([(221906,'Norepinephrine','Medications'),(222315,'Vasopressin','Medications'),(225158,'NaCl 0.9%','Fluids'),(225828,'LR','Fluids'),(222168,'Propofol','Medications'),(229420,'Dexmedetomidine (Precedex)','Medications'),
        (225168,'Packed Red Blood Cells','Blood Products'),(225792,'Invasive Ventilation','Ventilation'),(225802,'Dialysis - CRRT','Dialysis')],columns=['itemid','label','category'])
    gz(M/'icu/d_items.csv.gz',items)
    ie=[];pe=[]
    for s,t in zip(stays.stay_id,stays.intime):
        for it,h in [(221906,rng.uniform(0,40)),(225158 if rng.random()<.5 else 225828,rng.uniform(0,20)),(222168 if rng.random()<.5 else 229420,rng.uniform(0,20)),(225168,rng.uniform(5,60))]:
            if rng.random()<.8:ie.append({'stay_id':s,'starttime':t+pd.Timedelta(hours=h),'endtime':t+pd.Timedelta(hours=h+2),'itemid':it,'amount':500,'amountuom':'ml','rate':1,'rateuom':'ml/hr'})
        if rng.random()<.7:pe.append({'stay_id':s,'starttime':t+pd.Timedelta(hours=1),'endtime':t+pd.Timedelta(hours=50),'itemid':225792,'value':1})
        if rng.random()<.3:pe.append({'stay_id':s,'starttime':t+pd.Timedelta(hours=rng.uniform(10,70)),'endtime':t+pd.Timedelta(hours=90),'itemid':225802,'value':1})
    gz(M/'icu/inputevents.csv.gz',pd.DataFrame(ie));gz(M/'icu/procedureevents.csv.gz',pd.DataFrame(pe))
    drugs=['Hydrocortisone Na Succ.','Pantoprazole','Famotidine','Vancomycin','Piperacillin-Tazobactam','Metoprolol']
    pr=[{'subject_id':sid,'hadm_id':h,'starttime':t+pd.Timedelta(hours=rng.uniform(0,48)),'stoptime':t+pd.Timedelta(hours=72),'drug':random.choice(drugs),'route':'IV','dose_val_rx':1} for sid,h,t in zip(stays.subject_id,stays.hadm_id,stays.intime) for _ in range(4)]
    gz(M/'hosp/prescriptions.csv.gz',pd.DataFrame(pr))
    lab=[{'subject_id':sid,'hadm_id':h,'itemid':it,'charttime':t+pd.Timedelta(hours=k*12),'valuenum':float(v)} for sid,h,t in zip(stays.subject_id,stays.hadm_id,stays.intime) for k in range(8) for it,v in [(51222,rng.uniform(5,12)),(50912,rng.uniform(.6,4))]]
    gz(M/'hosp/labevents.csv.gz',pd.DataFrame(lab))
    gz(M/'hosp/microbiologyevents.csv.gz',pd.DataFrame([{'subject_id':sid,'hadm_id':h,'charttime':t+pd.Timedelta(hours=rng.uniform(0,30)),'spec_type_desc':'BLOOD CULTURE','org_name':None} for sid,h,t in zip(stays.subject_id,stays.hadm_id,stays.intime) if rng.random()<.6]))
    # ---- eICU ----
    pt=pd.DataFrame({'patientunitstayid':range(1,N+1),'patienthealthsystemstayid':range(1,N+1),'uniquepid':[f'p{i}' for i in range(N)],'hospitalid':rng.integers(1,8,N),'age':rng.integers(20,90,N).astype(str),'gender':'Male',
        'hospitaldischargestatus':rng.choice(['Alive','Expired'],N),'unitdischargestatus':'Alive','unitdischargeoffset':5760,'unittype':'MICU'})
    gz(E/'patient.csv.gz',pt)
    inf=[];tr=[];med=[];io_=[];lab=[];mic=[]
    for s in pt.patientunitstayid:
        for dn,h in [('Norepinephrine (mcg/min)',rng.uniform(0,40)),(random.choice(['Normal saline','Lactated Ringers']),rng.uniform(0,20)),(random.choice(['Propofol (mcg/kg/min)','Dexmedetomidine (mcg/kg/hr)']),rng.uniform(0,20))]:
            if rng.random()<.8:inf.append({'patientunitstayid':s,'infusionoffset':int(h*60),'drugname':dn,'drugrate':'5','infusionrate':5,'drugamount':100,'volumeoffluid':250})
        if rng.random()<.7:tr.append({'patientunitstayid':s,'treatmentoffset':60,'treatmentstring':'pulmonary|ventilation and oxygenation|mechanical ventilation'})
        if rng.random()<.3:tr.append({'patientunitstayid':s,'treatmentoffset':int(rng.uniform(600,4200)),'treatmentstring':'renal|dialysis|C V V H'})
        if rng.random()<.4:tr.append({'patientunitstayid':s,'treatmentoffset':int(rng.uniform(300,3600)),'treatmentstring':'hematology|blood product administration|packed red blood cells'})
        for dn in random.sample(['hydrocortisone sodium succinate','pantoprazole','famotidine','vancomycin','piperacillin/tazobactam','metoprolol'],3):
            med.append({'patientunitstayid':s,'drugstartoffset':int(rng.uniform(0,2880)),'drugstopoffset':4320,'drugname':dn,'dosage':'1','routeadmin':'IV','drugordercancelled':'No'})
        io_.append({'patientunitstayid':s,'intakeoutputoffset':int(rng.uniform(0,1440)),'celllabel':'Normal saline','cellvaluenumeric':500})
        for k in range(8):
            lab.append({'patientunitstayid':s,'labresultoffset':k*720,'labname':'Hgb','labresult':float(rng.uniform(5,12))});lab.append({'patientunitstayid':s,'labresultoffset':k*720,'labname':'creatinine','labresult':float(rng.uniform(.6,4))})
        if rng.random()<.6:mic.append({'patientunitstayid':s,'culturetakenoffset':int(rng.uniform(0,1800)),'culturesite':'Blood','organism':'no growth'})
    for name,rows in [('infusiondrug',inf),('treatment',tr),('medication',med),('intakeoutput',io_),('lab',lab),('microLab',mic)]:gz(E/f'{name}.csv.gz',pd.DataFrame(rows))
    os.environ.update(TTE_MIMIC_ROOT=str(M),TTE_EICU_ROOT=str(E),TTE_OUTPUT_DIR=str(td/'out'))
    g={'display':print,'__name__':'__main__'}
    for kind,src in CELLS:
        if kind=='code':exec(compile(src,'cell','exec'),g)
    F=g['FEAS'];bad=F[F.verdict.eq('error')]
    print(F[['question','database','verdict','error']].to_string())
    assert len(bad)==0,'queries failed'
    print('ALL',len(F),'QUESTION x DATABASE RUNS OK')
