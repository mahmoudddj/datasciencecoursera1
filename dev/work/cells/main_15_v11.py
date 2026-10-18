# 7. V11 matched comparisons: every arm on identical hours; loss comparators; transfer to the other
# database's development patients; conformal policy; trajectory-rich subset; prespecified ensemble.
RESULT_PARTS=[]
for target in DATASETS:
    jobs=[('rich',FEATURES,TRAIN_CONFIG)]
    # Raw-vs-engineered control: raw values + masks + ages only.
    if RUN_CORE_FEATURE_ABLATION:jobs.append(('raw',CORE_FEATURES,{**TRAIN_CONFIG,'arms':['osta','logistic','boosted_tree'],'loss_comparison_arms':[],'stress_conditions':[]}))
    # Sensitivity: without the clinician-suspicion proxies (hydrocortisone, imaging orders, prophylaxis).
    if RUN_NO_PROXY_SENSITIVITY:jobs.append(('no_proxies',NO_PROXY_FEATURES,{**TRAIN_CONFIG,'arms':['osta'],'loss_comparison_arms':[],'stress_conditions':[]}))
    for label,fs,cfg in jobs:
        with (RESULTS_ROOT/(target+'_'+label+'.log')).open('a') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            result=run_fold_v11(INDEX,fs,target,cfg,RESULTS_ROOT/label/target,
                                transfer_index=INDEX if RUN_TRANSFER_EVALUATION else None,corpus=CORPUS if label=='rich' else None)
        result['feature_set']=label;RESULT_PARTS.append(result)
        print('Completed',target,label,time.strftime('%H:%M'),flush=True)
RESULTS=pd.concat(RESULT_PARTS,ignore_index=True);RESULTS.to_csv(RESULTS_ROOT/'all_results.csv',index=False)
atomic_json(RESULTS_ROOT/'COMPLETE.json',{'status':'complete','mode':RUN_MODE,'data_source':DATA_SOURCE,'rows':len(RESULTS),
  'real_extraction_verified_in_this_run':DATA_SOURCE=='clinical'})
print('COMPLETE:',RESULTS_ROOT)
