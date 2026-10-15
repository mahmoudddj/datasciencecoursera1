import sys,json,tempfile,os
from pathlib import Path
import pandas as pd
S=sys.argv[1];sys.path.insert(0,S+'/work/mods')
from v9_data import fingerprint,signature
from v9_train import atomic_json
from v10_preflight import FULL_MIN_BYTES
cell=open(S+'/work/cells/main_7.py').read()
def make(root,ds,small,n):
    for stem,mn in FULL_MIN_BYTES[ds].items():
        f=root/(stem+'.csv.gz' if not stem.endswith(('icustays','patient')) else stem+'.csv');f.parent.mkdir(parents=True,exist_ok=True)
        if stem in ('icu/icustays','patient'):
            col='stay_id' if ds=='miiv' else 'patientunitstayid'
            pd.DataFrame({col:range(1,n+1),'pad':'x'*(40 if stem not in small else 1)}).to_csv(f,index=False)
            if stem in small:os.truncate(f,min(f.stat().st_size,5000)) if False else None
        else:
            with open(f,'wb') as h:h.truncate(5000 if stem in small else mn+1)
def run(small,n_miiv,allow_import=False):
    td=Path(tempfile.mkdtemp());mi=td/'mimic-iv-3.1';ei=td/'eicu'
    make(mi,'miiv',small,n_miiv);make(ei,'eicu',(),200859)
    g=dict(DATA_SOURCE='clinical',resolved_raw={'miiv':mi,'eicu':ei},DATASETS=['miiv','eicu'],RANDOM_STATE=42,ALLOW_DEMO_DATA=False,RUN_MODE='smoke',
           YAIB_COHORTS_COMMIT='x',SMOKE_STAYS_PER_DATASET=1200,EMBEDDED_MODULES={'v9_yaib_worker.py':{'sha256':'w'}},PROJECT=td/'proj',
           REUSE_COHORT_ROOT='',RUN_EXTRACTION=True,ALLOW_FULL_RAW_IMPORT=allow_import,fingerprint=fingerprint,signature=signature,
           atomic_json=atomic_json,Path=Path,json=json,pd=pd,display=lambda d:print(d.to_string(index=False)))
    try:exec(cell,g);return 'PASSED (continues to environment setup + smoke label extraction)'
    except Exception as e:return f'{type(e).__name__}: {e}'
print('A) YOUR DRIVE: demo-sized icustays/chartevents/patients/admissions inside the full folder:')
print(run(('icu/icustays','icu/chartevents','hosp/patients','hosp/admissions'),140),'\n')
print('B) after replacing the 4 files with full ones (no ALLOW_FULL_RAW_IMPORT needed at this step):')
print(run((),94458))
