# 7. Frozen inference; no target fitting, calibration or threshold search.
with (RESULTS_ROOT/'inference.log').open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
    RESULTS=score_target(TARGET_INDEX,BUNDLES,RESULTS_ROOT)
atomic_json(RESULTS_ROOT/'COMPLETE.json',{'mode':RUN_MODE,'data_source':DATA_SOURCE,'legacy_mode':LEGACY_MODE,
   'release_final':RELEASE_FINAL_HOLDOUT,'source_provenance':{a:m['provenance'] for a,(_,m,_) in BUNDLES.items()},'prior_test_exposure':PRIOR_TEST_EXPOSURE or 'NOT RECORDED (smoke)'})
if DATA_SOURCE=='fixture':display(RESULTS[['Dataset','arm','provenance','trajectory_stays']])
else:display(RESULTS[['Dataset','arm','provenance','members','threshold','prevalence_step','hourly_AUPRC_step','hourly_AUROC_step','Brier_step','normalized_utility','event_sensitivity','late_alarm_episodes','early_alarm_episodes','alarm_PPV','false_alarm_episodes_per_patient_day','unsupported_channels']].round(4))
if RUN_MODE=='smoke' or any('smoke' in m['provenance'] or 'synthetic' in m['provenance'] for _,m,_ in BUNDLES.values()):
    print('Pipeline evidence only: smoke/synthetic source models are not the historical models and not publication evidence.')
print('COMPLETE:',RESULTS_ROOT)