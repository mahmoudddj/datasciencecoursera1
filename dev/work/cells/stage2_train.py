# 6-7. Stage 2 (protocol section 11): bind the run to data, code and configuration; run the arms in order.
from v12_train import run_stage2,ARM_ORDER,THREE_SEED_ARMS
TRAIN_CONFIG=training_config(RUN_MODE,MAX_HOURS)
TRAIN_CONFIG.update(batch=V11_BATCH,release_final=RELEASE_FINAL_HOLDOUT,runtime_versions=RUNTIME_VERSIONS,
    ssl_epochs=1 if RUN_MODE=='smoke' else V11_SSL_EPOCHS,pretrain_epochs=1 if RUN_MODE=='smoke' else STAGE2_PRETRAIN_EPOCHS,cnn_depth=2,event_lookback=24,dropout=V11_DROPOUT,weight_decay=V11_WEIGHT_DECAY,
    tree_max_iterations=20 if RUN_MODE=='smoke' else V11_TREE_MAX_ITERATIONS,tree_step=10 if RUN_MODE=='smoke' else 50,conformal_alpha=.02,
    loss='bce',protocol_v11='v11-1.0+10b+stage2',stage='2',
    arms=list(STAGE2_ARMS),operating_point=STAGE2_OPERATING_POINT,persistence=STAGE2_PERSISTENCE,fresh_only=STAGE2_FRESH_ONLY,quantile_min_hours=10000,
    input_dropout=STAGE2_INPUT_DROPOUT,suspicion_horizon=STAGE2_SUSPICION_HORIZON,train_includes_observer_fit=STAGE2_TRAIN_INCLUDES_OBSERVER_FIT,
    shared_physiology=list(STAGE2_SHARED_PHYSIOLOGY),best_non_project_arm=STAGE2_BEST_NON_PROJECT_ARM,leave_hospital_out=True,lho_fraction=STAGE2_LHO_FRACTION,
    finetune_fraction=STAGE2_FINETUNE_FRACTION,transfer=RUN_TRANSFER_EVALUATION,frozen=bool(PROTOCOL_FROZEN),transport_min_stays=20,temporal_min_events=20)
if RUN_MODE=='full':TRAIN_CONFIG.update(seeds=list(FULL_SEEDS),tabular_max_bytes=int(TABULAR_MAX_GB*1024**3))
if PROTOCOL_FROZEN:
    assert PROTOCOL_FREEZE_TAG.strip(),'PROTOCOL_FROZEN requires the signed tag in PROTOCOL_FREEZE_TAG'
    assert RUN_MODE=='full' and DATA_SOURCE=='clinical','Test rows are released only in a full clinical run'
RUN_KEY=signature({'data':DATA_KEY,'code':CODE_SIGNATURE,'config':TRAIN_CONFIG,'features':FEATURES,'tables':{k:(len(v) if isinstance(v,dict) else str(v)) for k,v in STAGE2_TABLES.items()},
    'ssl_corpus':globals().get('SSL_KEY','fixture'),'stage':'2'})[:16]
RESULTS_ROOT=VALIDATION_ROOT/'runs'/RUN_KEY;RESULTS_ROOT.mkdir(parents=True,exist_ok=True)
atomic_json(RESULTS_ROOT/'run_protocol.json',{'run_key':RUN_KEY,'data_key':DATA_KEY,'mode':RUN_MODE,'study_stage':STUDY_STAGE,'data_source':DATA_SOURCE,'config':TRAIN_CONFIG,'features':FEATURES,
  'code':CODE_SIGNATURE,'prior_test_exposure':PRIOR_TEST_EXPOSURE or 'NOT RECORDED (smoke)','protocol_frozen':bool(PROTOCOL_FROZEN),'freeze_tag':PROTOCOL_FREEZE_TAG,
  'seed_tiering':f'three seeds for {sorted(THREE_SEED_ARMS)}, the first seed for the other arms (section 11)',
  'training_split_rule':('train + the retired observer-fit split (70 % of development patients)' if STAGE2_TRAIN_INCLUDES_OBSERVER_FIT else 'train split only (40 %), as in stage 1'),
  'test_rows':('released: protocol frozen' if PROTOCOL_FROZEN else 'SEALED on disk (test_rows_sealed.json per arm); only validation rows are returned and printed'),
  'evaluation_scope':'protected cross-database final test' if RELEASE_FINAL_HOLDOUT else 'internal development split + development-level transfer; protected 20% patient hash sealed'})
display(pd.DataFrame({k:[str(TRAIN_CONFIG[k])] for k in ['epochs','pretrain_epochs','seeds','small_model','bootstrap','batch','dropout','loss','operating_point','persistence','arms']},index=['this run ('+RUN_MODE+')']).T)
print('Run:',RUN_KEY,'| features:',len(FEATURES),'| incident stays:',len(TRAIN_INDEX),'| frozen:',PROTOCOL_FROZEN,'|',STUDY_STAGE[:90])
# Pretraining corpus (item 3; TO FREEZE): the unlabelled corpus plus the arrival-sepsis stays (inputs; their arrival flag is the weak target).
PRETRAIN_CORPUS=dict(CORPUS)
if len(ARRIVAL_INDEX):PRETRAIN_CORPUS['arrival']=ARRIVAL_INDEX.copy()
if not STAGE2_ARMS:
    # Data build only (before the freeze): labels, raw stage, supplements, features, corpus and tables are cached; no model is trained.
    RESULTS=pd.DataFrame();atomic_json(RESULTS_ROOT/'DATA_BUILD_ONLY.json',{'mode':RUN_MODE,'data_key':DATA_KEY,'incident_stays':int(len(TRAIN_INDEX)),'arrival_stays':int(len(ARRIVAL_INDEX)),'frozen':bool(PROTOCOL_FROZEN)})
    print('STAGE2_ARMS is empty: data build only, nothing trained. Data key',DATA_KEY,'| incident stays',len(TRAIN_INDEX),'| arrival stays',len(ARRIVAL_INDEX))
else:
    assert PROTOCOL_FROZEN or RUN_MODE=='smoke' or DATA_SOURCE=='fixture','Full-cohort training requires PROTOCOL_FROZEN=True (signed tag, hash deposited). Set STAGE2_ARMS=[] for the data build.'
    with (RESULTS_ROOT/'stage2.log').open('a') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        RESULTS=run_stage2(TRAIN_INDEX,FEATURES,TRAIN_CONFIG,RESULTS_ROOT,STAGE2_TABLES,DATASETS,PRETRAIN_CORPUS)
    RESULTS.to_csv(RESULTS_ROOT/'all_results.csv',index=False)
    atomic_json(RESULTS_ROOT/'COMPLETE.json',{'status':'complete','mode':RUN_MODE,'data_source':DATA_SOURCE,'rows':len(RESULTS),'frozen':bool(PROTOCOL_FROZEN),'real_extraction_verified_in_this_run':DATA_SOURCE=='clinical'})
    print('COMPLETE:',RESULTS_ROOT,time.strftime('%H:%M'))
