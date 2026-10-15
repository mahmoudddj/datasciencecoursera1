import sys,importlib,time,numpy as np,pandas as pd
S=sys.argv[1]
def load(d):
    sys.path.insert(0,d)
    for m in list(sys.modules):
        if m.startswith(('v9_','v10_')):del sys.modules[m]
    mod=importlib.import_module('v9_data');sys.path.pop(0);return mod
rng=np.random.default_rng(0);rows=[]
spec=[('HR',90,15,1),('SBP',110,20,1),('DBP',65,10,1),('MAP',80,12,1),('Resp',20,5,1),('Temp',37.5,.8,4),('O2Sat',96,2,1),('GCS',13,2,4),
 ('Creatinine',1.4,.6,12),('Platelets',150,60,12),('Bilirubin_total',1.5,1,24),('BUN',25,8,12),('WBC',11,4,12),('Lactate',2,1,6),('Weight',80,5,48),('UrineOutput',40,25,1)]
for f,m,sd,every in spec:
    for eh in np.arange(0,120,every)+rng.uniform(0,.9,len(np.arange(0,120,every))):
        rows.append({'feature':f,'value':float(max(.5,rng.normal(m,sd))),'event_hour':eh,'available_hour':eh+.3,'unit':''})
for eh in rng.uniform(0,120,60):rows.append({'feature':'VasopressorRecorded','value':1.,'event_hour':eh,'available_hour':eh,'unit':''})
ev=pd.DataFrame(rows);meta={'followup_end':125.,'OnsetHour':np.nan,'Age':70.,'Gender':0.}
print('events',len(ev))
for name,d in [('original',S+'/mods_v10'),('v10.2',S+'/work/mods')]:
    m=load(d);m.build_sequence(ev,meta,120,6);t=time.time()
    for _ in range(5):m.build_sequence(ev,meta,120,6)
    print(name,'sec/stay',round((time.time()-t)/5,3))
