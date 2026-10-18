# 7b. Team summary (aggregate numbers only; works on PARTIAL results: interrupt Section 7, then run this cell).
# Development split + development-level transfer only; the protected 20% final holdout stays sealed. No retuning on these numbers.
perf=[]
for p in sorted(RESULTS_ROOT.glob('*/*/seed_*/*/completed.json')):
    for r in json.loads(p.read_text()):
        cal=p.parent/'calibration_and_threshold.json';platt=json.loads(cal.read_text())['platt'] if cal.is_file() else {}
        perf.append({**r,'feature_set':p.parts[-5],'platt_slope_fitted':platt.get('fitted_slope',platt.get('slope')),'platt_fallback':platt.get('fallback','')})
cols=['target','feature_set','arm','loss','condition','seed','stays','eligible_hours','positive_hours','prevalence','hourly_AUROC','hourly_AUPRC',
      'AUPRC_CI_low','AUPRC_CI_high','hourly_Brier','ECE_10bin','calibration_slope','event_sensitivity','false_alarms_per_patient_day',
      'median_warning_hours_detected','normalized_utility','utility_CI_low','utility_CI_high','utility_threshold',
      'median_lead_vs_first_antibiotic_hours','fraction_alarm_before_first_antibiotic','antibiotic_lead_n',
      'validation_utility','validation_AUPRC','conformal_threshold','conformal_abstained_fraction','platt_slope_fitted','platt_fallback']
TEAM_PERF=pd.DataFrame(perf)
if len(TEAM_PERF):
    TEAM_PERF=TEAM_PERF[[c for c in cols if c in TEAM_PERF]].sort_values(['target','feature_set','condition','arm']).reset_index(drop=True)
    TEAM_PERF.to_csv(RESULTS_ROOT/'team_summary_performance.csv',index=False)
    internal=TEAM_PERF[TEAM_PERF.condition.eq('normal')&~TEAM_PERF.target.str.contains('_from_')]
    print('INTERNAL development test (primary loss and comparators):');display(internal.drop(columns=['condition','platt_fallback'],errors='ignore').round(3))
    transfer=TEAM_PERF[TEAM_PERF.target.str.contains('_from_')]
    if len(transfer):print('TRANSFER: model of one database on the other database\'s development patients:');display(transfer[[c for c in ['target','feature_set','arm','hourly_AUROC','hourly_AUPRC','normalized_utility','event_sensitivity','false_alarms_per_patient_day','median_lead_vs_first_antibiotic_hours'] if c in transfer]].round(3))
    conf=TEAM_PERF[TEAM_PERF.condition.eq('conformal')]
    if len(conf):print('CONFORMAL secondary alarm policy (abstention + distribution-free hourly false-positive bound):');display(conf[[c for c in ['target','feature_set','arm','event_sensitivity','false_alarms_per_patient_day','conformal_abstained_fraction','median_lead_vs_first_antibiotic_hours'] if c in conf]].round(3))
    # Prespecified rules, reported from VALIDATION numbers only (never test).
    rich=TEAM_PERF[TEAM_PERF.feature_set.eq('rich')&TEAM_PERF.condition.eq('normal')&~TEAM_PERF.target.str.contains('_from_')].copy()
    if {'validation_utility','validation_AUPRC'}<=set(rich):
        rich['base']=rich.arm.str.split('@').str[0];rich['val_rank']=rich.groupby('target')[['validation_utility','validation_AUPRC']].rank(ascending=False).mean(axis=1)
        for t,g in rich.groupby('target'):
            for base in V11_LOSS_COMPARISON_ARMS:
                gg=g[g.base.eq(base)].sort_values('val_rank')
                if len(gg)>1:print(f'[{t}] loss rule for {base}: '+' > '.join(f"{a}(val U {u:.3f}, AUPRC {p:.3f})" for a,u,p in zip(gg.arm,gg.validation_utility,gg.validation_AUPRC)))
            o=g[g.arm.eq('osta')];f=g[g.arm.eq('flat_osta')]
            if len(o) and len(f):print(f'[{t}] organ-structure rule: osta val_rank {o.val_rank.iloc[0]:.1f} vs flat_osta {f.val_rank.iloc[0]:.1f} -> '+('organ structure KEPT' if o.val_rank.iloc[0]<f.val_rank.iloc[0] else 'organ structure NOT supported'))
            new=g[g.base.isin(['flat_osta','grud','tcn','cnn_osta','ssl_cnn_osta','ssl_cnn_flat','ssl_cnn_osta_pooled','ssl_cnn_flat_pooled','event_osta','hazard_ssl_cnn_osta','signature_boosted_tree'])&~g.arm.str.contains('@')].sort_values('val_rank')
            if len(new):print(f'[{t}] shortlist (validation rule): '+', '.join(new.arm.head(3)))
else:print('No completed arms yet.')
coh=[]
for ds in DATASETS:
    z=INDEX[INDEX.Dataset.eq(ds)];sealed=z.Group_ID.map(protected_group);dev=z[~sealed]
    coh.append({'dataset':ds,'candidate_ICU_stays_sampled':globals().get('COHORT_PROTOCOL',{}).get('candidate_n') or globals().get('SOURCE_COUNTS',{}).get(ds),
      'stays_after_YAIB_exclusions':len(z),'sealed_final_holdout_stays':int(sealed.sum()),'development_stays':len(dev),
      'development_patients':dev.Group_ID.nunique(),'hospitals':dev.Hospital_ID.nunique(),
      'development_stays_with_sepsis_prediction_window':int(dev.eligible_positive.sum()),
      'unlabelled_pretraining_stays':len(CORPUS.get(ds,[])) if DATA_SOURCE=='clinical' else 'fixture'})
TEAM_COHORT=pd.DataFrame(coh);TEAM_COHORT.to_csv(RESULTS_ROOT/'team_summary_cohort.csv',index=False);display(TEAM_COHORT)
print(f'{RUN_MODE.upper()} | {STUDY_STAGE[:120]} | completed rows: {len(TEAM_PERF)} | files: team_summary_performance.csv, team_summary_cohort.csv in {RESULTS_ROOT}')
