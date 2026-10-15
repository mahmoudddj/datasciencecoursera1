import sys,importlib.util,numpy as np,pandas as pd
def load(d,name):
    sys.path.insert(0,d)
    for m in list(sys.modules):
        if m.startswith(('v9_','v10_')):del sys.modules[m]
    mod=importlib.import_module(name);sys.path.pop(0);return mod
S=sys.argv[1]
old=load(S+'/mods_v10','v9_data');new=load(S+'/work/mods','v9_data')
rng=np.random.default_rng(0);bad=0
for k in range(300):
    n=rng.integers(0,40);e=rng.uniform(-5,30,n).round(rng.choice([0,2]));a=e+rng.choice([0,0,.5,2],n)
    v=rng.normal(40,60,n)
    ev=pd.DataFrame({'event_hour':e,'available_hour':a,'value':v})
    h=np.arange(1.,31.);w=np.where(rng.random(30)<.2,np.nan,70.)
    A=old.urine_features(ev,h,w);B=new.urine_features(ev,h,w)
    for f in A:
        if not np.allclose(A[f],B[f],equal_nan=True):bad+=1;print('urine',k,f)
    z=ev.assign(value=rng.choice([0.,1.],n))
    # old support logic inline
    vo=[];ao=[]
    for t in h:
        kn=z[(z.available_hour<=t)&(z.event_hour>t-1)&(z.event_hour<=t)]
        vo.append(kn.value.max() if len(kn) else np.nan);ao.append(t-kn.event_hour.max() if len(kn) else np.nan)
    vn,an=new.support_features(z,h)
    if not (np.allclose(vo,vn,equal_nan=True) and np.allclose(ao,an,equal_nan=True)):bad+=1;print('support',k)
print('mismatches',bad)
