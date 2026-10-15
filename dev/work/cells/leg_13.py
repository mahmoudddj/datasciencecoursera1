# 6. Build full hourly trajectories; incident-only shards from A are not accepted.
from v10_clinical import legacy_target
if DATA_SOURCE=='clinical':
    RAW_STAGE_KEY=raw_stage_key(COHORT_KEY,MAX_HOURS)
    TARGET_KEY=signature({'cohort':COHORT_KEY,'raw':RAW_FINGERPRINTS,'max_hours':MAX_HOURS,'raw_stage':RAW_STAGE_KEY,
       'adapter':EMBEDDED_MODULES['v10_clinical.py']['sha256'],'data':EMBEDDED_MODULES['v9_data.py']['sha256'],
       'features':EMBEDDED_MODULES['v10_features.py']['sha256'],'mode':RUN_MODE,'release_final':RELEASE_FINAL_HOLDOUT})[:16]
    # Reuses Notebook A's raw-table stage for the same cohort when present; otherwise scans once.
    TARGET_INDEX=pd.concat([legacy_target(ds,resolved_raw[ds],COHORT_ROOT/ds,
      VALIDATION_ROOT/'targets'/TARGET_KEY/ds,MAX_HOURS,RUN_MODE,RELEASE_FINAL_HOLDOUT,
      reuse_stage=PROJECT/'raw_stage_v10'/RAW_STAGE_KEY/ds) for ds in DATASETS],ignore_index=True)
else:TARGET_KEY=signature({'synthetic':True,'code':CODE_SIGNATURE})[:16]
RESULTS_ROOT=VALIDATION_ROOT/'runs'/signature({'target':TARGET_KEY,'source':{a:[x['sha256'] for x in m['members']] for a,(_,m,_) in BUNDLES.items()},'config':{a:m for a,(_,m,_) in BUNDLES.items()},'code':CODE_SIGNATURE})[:16]
RESULTS_ROOT.mkdir(parents=True,exist_ok=True)
print('Target scope:','synthetic engineering' if DATA_SOURCE=='fixture' else ('protected final external evaluation' if RELEASE_FINAL_HOLDOUT else 'development-designated external diagnostic; final holdouts sealed'))