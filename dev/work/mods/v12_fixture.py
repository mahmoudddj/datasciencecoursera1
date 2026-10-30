"""Stage-2 synthetic fixture (engineering only, never a clinical fallback): the v10 fixture index plus the stay-level
tables the stage-2 driver reads (suspicion hours, first treatment, documentation, alternative onsets, antibiotic starts,
arrival flags, anchor-year groups) and an unlabelled corpus. Values are arbitrary; only shapes and keys matter."""
from pathlib import Path
import numpy as np
import pandas as pd
from v10_fixture import make_fixture

def make_stage2_fixture(root,n=160):
    root=Path(root);index,features=make_fixture(root,n)
    index=index.copy();index['stay_id']=np.arange(len(index))+1000;index['FirstAntibioticAroundOnset']=np.where(index.OnsetHour.notna(),index.OnsetHour-7.,np.nan)
    rng=np.random.default_rng(7);pid=index.Patient_ID.astype(str).to_numpy();septic=index.OnsetHour.notna().to_numpy()
    k=np.arange(len(index))
    # suspicion-anchored event: 7 h before the operational onset for septic stays; a late continued course in 1 of 8 controls
    susp=np.where(septic,index.OnsetHour.to_numpy()-7.,np.where(k%8==3,20.,np.nan))
    tables={'suspicion_hour':dict(zip(pid,susp)),
            'first_treatment':dict(zip(pid,np.where(np.isfinite(susp),susp-1.,np.nan))),
            'documented':dict(zip(pid,(septic&(k%4==1)).tolist())),
            'alt_onsets':{ds:{p:float(o)-2. for p,o,d in zip(pid,index.OnsetHour,index.Dataset) if d==ds and np.isfinite(o)} for ds in ('miiv','eicu')},
            'abx_starts':{p:([float(s)] if np.isfinite(s) else []) for p,s in zip(pid,susp)},
            'arrival':dict(zip(pid,np.where(k%16==5,1.,0.))),
            'anchor_year_group':{p:['2008 - 2010','2011 - 2013','2014 - 2016','2017 - 2019'][(i//2)%4] for i,(p,d) in enumerate(zip(pid,index.Dataset)) if d=='miiv'},   # septic stays alternate, so every group has both classes
            'doc_prior':{'miiv':.5,'eicu':.5}}
    corpus={ds:index[index.Dataset.eq(ds)].sample(frac=.3,random_state=3).assign(OnsetHour=np.nan,eligible_positive=0) for ds in ('miiv','eicu')}
    return index,features,tables,corpus
