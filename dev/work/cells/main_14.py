# 6. Resolve smoke/full settings and bind the run to data, code and split policy.
TRAIN_CONFIG=training_config(RUN_MODE,MAX_HOURS)
TRAIN_CONFIG.update(batch=TRAIN_BATCH_SIZE,release_final=RELEASE_FINAL_HOLDOUT,runtime_versions=RUNTIME_VERSIONS)
RAW_BASE=set(BASE+SUPPORT+['UrineOutput'])
CORE_FEATURES=[f for f in FEATURES if base_name(f) in RAW_BASE]
RAW_CONTROL_ARMS=['osta','logistic','boosted_tree'] if RUN_RAW_TABULAR_CONTROL else ['osta']
RUN_KEY=signature({'data':DATA_KEY,'code':CODE_SIGNATURE,'config':TRAIN_CONFIG,
  'raw_ablation':RUN_CORE_FEATURE_ABLATION,'raw_arms':RAW_CONTROL_ARMS,'80pct_control':RUN_FULL_LABEL_BASELINE,'features':FEATURES})[:16]
RESULTS_ROOT=VALIDATION_ROOT/'runs'/RUN_KEY;RESULTS_ROOT.mkdir(parents=True,exist_ok=True)
atomic_json(RESULTS_ROOT/'run_protocol.json',{'run_key':RUN_KEY,'data_key':DATA_KEY,'mode':RUN_MODE,
  'data_source':DATA_SOURCE,'config':TRAIN_CONFIG,'features':FEATURES,'core_features':CORE_FEATURES,'raw_control_arms':RAW_CONTROL_ARMS,
  'code':CODE_SIGNATURE,'prior_test_exposure':PRIOR_TEST_EXPOSURE or 'NOT RECORDED (smoke)',
  'evaluation_scope':'protected cross-database final test' if RELEASE_FINAL_HOLDOUT else 'internal development split; protected 20% patient hash sealed'})
# Full-mode resolution preview: computed, not launched.
FULL_PREVIEW=training_config('full',MAX_HOURS)
assert FULL_PREVIEW['epochs']==30 and not FULL_PREVIEW['small_model'] and len(FULL_PREVIEW['seeds'])==3
assert TRAIN_CONFIG['epochs']==(2 if RUN_MODE=='smoke' else 30)
display(pd.DataFrame({k:[str(TRAIN_CONFIG[k]),str(FULL_PREVIEW[k])] for k in
   ['epochs','observer_epochs','seeds','small_model','bootstrap','tree_iterations','stress_conditions','false_alarm_budget']},
   index=['this run ('+RUN_MODE+')','full mode']).T)
print('Run:',RUN_KEY,'| features:',len(FEATURES),'| raw-control features:',len(CORE_FEATURES),'| smoke candidate cap:',SMOKE_STAYS_PER_DATASET if RUN_MODE=='smoke' else None)
