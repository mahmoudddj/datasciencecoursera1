# Concise summary; patient-level files stay under RESULTS_ROOT. No winner selection, no test retuning.
if STAGE_1B:
    print('Stage 1b: no test-split rows are summarised; see the validation grid in 7b. Test rows are sealed in test_rows_sealed.json.')
    atomic_json(RESULTS_ROOT/'COMPLETE.json',{'status':'complete','mode':RUN_MODE,'data_source':DATA_SOURCE,'rows':len(RESULTS),'stage':'1b'})
if not STAGE_1B:
    NORMAL=RESULTS[RESULTS.condition.eq('normal')&~RESULTS.target.str.contains('_from_')]
    SUMMARY=NORMAL.groupby(['target','feature_set','arm'],as_index=False).agg(
        seeds=('seed','nunique'),eligible_hours=('eligible_hours','first'),prevalence=('prevalence','mean'),hourly_AUPRC=('hourly_AUPRC','mean'),
        hourly_AUROC=('hourly_AUROC','mean'),Brier=('hourly_Brier','mean'),event_sensitivity=('event_sensitivity','mean'),
        false_alarms_per_patient_day=('false_alarms_per_patient_day','mean'),normalized_utility=('normalized_utility','mean'))
    SUMMARY.to_csv(RESULTS_ROOT/'summary_normal_condition.csv',index=False)
    # Comparability guard: every arm of a target scored the same eligible hours.
    assert SUMMARY.groupby(['target'])['eligible_hours'].nunique().max()==1, 'Arms scored different eligible observations'
    if DATA_SOURCE=='fixture':
        display(SUMMARY[['target','feature_set','arm','seeds','eligible_hours']])
        print('Synthetic fit/calibration/metric/export checks completed; scores are meaningless and clinical performance is unverified.')
    else:
        display(SUMMARY.round(4))
        comps=[pd.read_csv(p).assign(target=p.parts[-2],seed=p.parts[-1]) for p in (RESULTS_ROOT/'rich').glob('*/seed_*/paired_comparisons.csv') if p.stat().st_size>1]
        if comps:display(pd.concat(comps).round(4))
        if RUN_MODE=='smoke':print('SMOKE: execution evidence only. Do not rank models or choose settings from these numbers.')
        import matplotlib.pyplot as plt
        for target in DATASETS:
            fig,ax=plt.subplots(figsize=(5,4));ax.plot([0,1],[0,1],'--',color='#555555',label='Ideal');drawn=False
            for arm,color in [('osta','#285f8f'),('ssl_cnn_osta','#b5651d'),('cnn','#3a7d44')]:
                path=RESULTS_ROOT/'rich'/target/'seed_42'/arm/'calibration_normal.csv'
                if path.exists():p=pd.read_csv(path);ax.plot(p.mean_risk,p.event_fraction,'o-',color=color,label=arm);drawn=True
            if drawn:
                ax.set(xlim=(0,1),ylim=(0,1),xlabel='Mean predicted six-hour risk',ylabel='Observed fraction',title=target+' | '+RUN_MODE+' calibration')
                ax.legend();fig.tight_layout();fig.savefig(RESULTS_ROOT/(target+'_calibration.png'),dpi=160);plt.show()
            else:plt.close(fig)
print('Completion marker:',RESULTS_ROOT/'COMPLETE.json','| per-arm markers: */<target>/seed_*/<arm>/completed.json')
