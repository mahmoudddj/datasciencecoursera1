# 6. Resolve smoke/full settings and bind the run to data, code and split policy (V11 protocol).
TRAIN_CONFIG=training_config(RUN_MODE,MAX_HOURS)
TRAIN_CONFIG.update(batch=V11_BATCH,release_final=RELEASE_FINAL_HOLDOUT,runtime_versions=RUNTIME_VERSIONS,
    arms=list(V11_ARMS),loss=V11_PRIMARY_LOSS,comparison_losses=list(V11_COMPARISON_LOSSES),loss_comparison_arms=list(V11_LOSS_COMPARISON_ARMS),
    ssl_epochs=1 if RUN_MODE=='smoke' else V11_SSL_EPOCHS,cnn_depth=2,event_lookback=24,dropout=V11_DROPOUT,weight_decay=V11_WEIGHT_DECAY,
    tree_max_iterations=20 if RUN_MODE=='smoke' else V11_TREE_MAX_ITERATIONS,tree_step=10 if RUN_MODE=='smoke' else 50,
    conformal_alpha=.02,tls_tau=12.,protocol_v11='v11-1.0')
if RUN_MODE=='full':TRAIN_CONFIG.update(seeds=list(FULL_SEEDS),tabular_max_bytes=int(TABULAR_MAX_GB*1024**3))
RAW_BASE=set(BASE+SUPPORT+['UrineOutput'])
CORE_FEATURES=[f for f in FEATURES if base_name(f) in RAW_BASE]
NO_PROXY_FEATURES=[f for f in FEATURES if base_name(f) not in PROXY_FEATURES]
RUN_KEY=signature({'data':DATA_KEY,'code':CODE_SIGNATURE,'config':TRAIN_CONFIG,'raw_ablation':RUN_CORE_FEATURE_ABLATION,
  'no_proxies':RUN_NO_PROXY_SENSITIVITY,'transfer':RUN_TRANSFER_EVALUATION,'ssl_corpus':globals().get('SSL_KEY','fixture'),'features':FEATURES})[:16]
RESULTS_ROOT=VALIDATION_ROOT/'runs'/RUN_KEY;RESULTS_ROOT.mkdir(parents=True,exist_ok=True)
atomic_json(RESULTS_ROOT/'run_protocol.json',{'run_key':RUN_KEY,'data_key':DATA_KEY,'mode':RUN_MODE,'study_stage':STUDY_STAGE,
  'data_source':DATA_SOURCE,'config':TRAIN_CONFIG,'features':FEATURES,'core_features':CORE_FEATURES,'no_proxy_features':NO_PROXY_FEATURES,
  'code':CODE_SIGNATURE,'prior_test_exposure':PRIOR_TEST_EXPOSURE or 'NOT RECORDED (smoke)',
  'loss_selection_rule':'rank-average of VALIDATION-split utility and AUPRC over the comparison losses; decided before any result; test never used',
  'organ_structure_rule':'OSTA is abandoned as architecture if flat_osta >= osta on the same validation rule',
  'shortlist_rule':'top 2-3 new arms by the validation rule plus osta, cnn, boosted_tree, logistic go to the full cohort (3 seeds)',
  'evaluation_scope':'protected cross-database final test' if RELEASE_FINAL_HOLDOUT else 'internal development split + development-level transfer; protected 20% patient hash sealed'})
FULL_PREVIEW=training_config('full',MAX_HOURS)
assert TRAIN_CONFIG['epochs']==(2 if RUN_MODE=='smoke' else 30)
display(pd.DataFrame({k:[str(TRAIN_CONFIG[k])] for k in ['epochs','ssl_epochs','seeds','small_model','bootstrap','batch','dropout','weight_decay','loss','comparison_losses','false_alarm_budget']},index=['this run ('+RUN_MODE+')']).T)
print('Run:',RUN_KEY,'| features:',len(FEATURES),'| raw-control features:',len(CORE_FEATURES),'| arms:',len(V11_ARMS),'| stage:',STUDY_STAGE[:80])
