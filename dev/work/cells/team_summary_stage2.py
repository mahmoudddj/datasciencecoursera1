# 7b. Stage-2 team summary (aggregates only; counts under 11 masked). Before the freeze only VALIDATION rows exist in
# RESULTS; test rows stay sealed on disk. After the freeze (PROTOCOL_FROZEN) the same tables include the test rows.
if len(RESULTS)==0:
    print('No training rows (data build only): the team summary is skipped.')
else:
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    SUMMARY_ROOT=RESULTS_ROOT/'team_summary';SUMMARY_ROOT.mkdir(exist_ok=True)
    def mask_small(df,cols=('stays','eligible_hours','event_evaluable_stays','missed_events','detected_event_denominator','positive_hours','events')):
        d=df.copy()
        for c in cols:
            if c in d:d[c]=d[c].where(~(pd.to_numeric(d[c],errors='coerce')<11),'<11')
        return d
    R=RESULTS.copy();R['database']=R.target.str.replace(r'_from_.*','',regex=True)
    metrics=[c for c in ['val_AUPRC','hourly_AUPRC','hourly_AUROC','event_sensitivity','false_alarms_per_patient_day','median_warning_hours_detected','alarm_PPV','normalized_utility','observed_to_expected','calibration_slope','abstained_fraction_all_hours','adoptable'] if c in R]
    # Table 1: every arm x database x condition, mean over seeds (and the seed spread of the project model as the yardstick for one-seed arms)
    T1=R.groupby(['condition','database','base_arm','arm','label','feature_set'],as_index=False).agg(seeds=('seed','nunique'),**{m:(m,'mean') for m in metrics if m!='adoptable'})
    T1.to_csv(SUMMARY_ROOT/'table1_arms_by_condition.csv',index=False)
    proj=R[R.arm.eq('flat_osta')&R.condition.eq('validation')].groupby('database').agg(val_AUPRC_sd=('val_AUPRC','std'),seeds=('seed','nunique'))
    proj.to_csv(SUMMARY_ROOT/'project_model_seed_spread.csv')
    print('Validation rows by arm (mean over seeds):');display(mask_small(T1[T1.condition.eq('validation')][['database','arm','feature_set','seeds']+[m for m in ['val_AUPRC','event_sensitivity','false_alarms_per_patient_day','median_warning_hours_detected'] if m in T1]]).round(3))
    print('Project-model seed spread (validation AUPRC sd), the yardstick for the one-seed arms:');display(proj.round(4))
    # Table 2: abstention variants and the adoption rule (validation only, item 16)
    A=R[R.condition.str.startswith('validation_abstention_')].copy()
    if len(A):
        A['variant']=A.condition.str.replace('validation_abstention_','');T2=A.groupby(['database','arm','variant'],as_index=False).agg(event_sensitivity=('event_sensitivity','mean'),false_alarms_per_patient_day=('false_alarms_per_patient_day','mean'),
            median_warning_hours_detected=('median_warning_hours_detected','mean'),abstained_fraction_all_hours=('abstained_fraction_all_hours','mean'),adoptable=('adoptable',lambda s:bool(pd.Series(s).astype(bool).all())))
        T2.to_csv(SUMMARY_ROOT/'table2_abstention_validation.csv',index=False);print('Abstention variants on validation (item 16; adoptable only if ALL seeds pass the rule):');display(T2[T2.arm.eq('flat_osta')].round(3))
    # Sealed test rows: counted, never read
    sealed=sorted(RESULTS_ROOT.glob('seed_*/**/test_rows_sealed.json'))
    print(f'Sealed test-row files on disk: {len(sealed)} ({"released into RESULTS" if PROTOCOL_FROZEN else "not read; protocol not frozen"})')
    # Figure 1: validation AUPRC per arm and database (mean over seeds)
    V=T1[T1.condition.eq('validation')];fig,ax=plt.subplots(figsize=(10,max(3,.3*V.arm.nunique())))
    for k,(db,g) in enumerate(V.groupby('database')):
        g=g.sort_values('val_AUPRC');ax.barh(np.arange(len(g))+.4*k,g.val_AUPRC,height=.4,label=db);ax.set_yticks(np.arange(len(g))+.2);ax.set_yticklabels(g.arm,fontsize=7)
    ax.set_xlabel('validation hourly AUPRC (mean over seeds)');ax.legend();fig.tight_layout();fig.savefig(SUMMARY_ROOT/'fig1_validation_auprc_by_arm.png',dpi=130);plt.close(fig)
    # Digest
    digest={'run_key':RUN_KEY,'mode':RUN_MODE,'frozen':bool(PROTOCOL_FROZEN),'arms_completed':sorted(R.arm.unique().tolist()),'conditions':sorted(R.condition.unique().tolist()),
            'sealed_test_files':len(sealed),'seeds_by_arm':R.groupby('arm').seed.nunique().to_dict(),'training_split_rule':'train+observer_fit' if STAGE2_TRAIN_INCLUDES_OBSERVER_FIT else 'train only'}
    atomic_json(SUMMARY_ROOT/'digest.json',digest);print('Team summary written to',SUMMARY_ROOT)
