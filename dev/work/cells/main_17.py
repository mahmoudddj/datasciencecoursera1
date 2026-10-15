# Concise summary; patient-level files stay under RESULTS_ROOT. No winner selection, no test retuning.
SUMMARY=RESULTS.loc[RESULTS.condition.eq('normal')].groupby(['target','feature_set','arm'],as_index=False).agg(
    seeds=('seed','nunique'),eligible_hours=('eligible_hours','first'),prevalence=('prevalence','mean'),hourly_AUPRC=('hourly_AUPRC','mean'),
    hourly_AUROC=('hourly_AUROC','mean'),Brier=('hourly_Brier','mean'),event_sensitivity=('event_sensitivity','mean'),
    false_alarms_per_patient_day=('false_alarms_per_patient_day','mean'))
SUMMARY.to_csv(RESULTS_ROOT/'summary_normal_condition.csv',index=False)
# Comparability guard: every arm of a target/feature set scored the same eligible hours.
assert SUMMARY.groupby(['target'])['eligible_hours'].nunique().max()==1, 'Arms scored different eligible observations'
if DATA_SOURCE=='fixture':
    display(SUMMARY[['target','feature_set','arm','seeds','eligible_hours']])
    print('Synthetic fit/calibration/metric/export checks completed; scores are meaningless and clinical performance is unverified.')
else:
    display(SUMMARY.round(4))
    comps=[pd.read_csv(p).assign(target=p.parts[-3],seed=p.parts[-2]) for p in (RESULTS_ROOT/'rich').glob('*/seed_*/paired_comparisons.csv') if p.stat().st_size>1]
    if comps:display(pd.concat(comps).round(4))
    if RUN_MODE=='smoke':print('SMOKE: execution evidence only. Do not rank models or choose settings from these numbers.')
    import matplotlib.pyplot as plt
    for target in DATASETS:
        path=RESULTS_ROOT/'rich'/target/'seed_42'/'osta'/'calibration_normal.csv'
        if not path.exists():continue
        p=pd.read_csv(path);fig,ax=plt.subplots(figsize=(5,4))
        ax.plot([0,1],[0,1],'--',color='#555555',label='Ideal')
        ax.plot(p.mean_risk,p.event_fraction,'o-',color='#285f8f',label='OSTA')
        ax.set(xlim=(0,1),ylim=(0,1),xlabel='Mean predicted six-hour risk',ylabel='Observed fraction',title=target+' | '+RUN_MODE+' calibration')
        ax.legend();fig.tight_layout();fig.savefig(RESULTS_ROOT/(target+'_calibration.png'),dpi=160);plt.show()
print('Completion marker:',RESULTS_ROOT/'COMPLETE.json','| per-arm markers: */seed_*/<arm>/completed.json')
