# 7b. Team summary: aggregate numbers only. It also works on PARTIAL results: if time runs out,
# interrupt Section 7 (Runtime > Interrupt execution), then run this cell on its own.
# Development split only; the protected 20% final holdout stays sealed. No retuning on these numbers.
perf=[]
for p in sorted(RESULTS_ROOT.glob('*/*/seed_*/*/completed.json')):
    for r in json.loads(p.read_text()):
        if r.get('condition')=='normal':perf.append({**r,'feature_set':p.parts[-5]})
cols=['target','feature_set','arm','seed','stays','eligible_hours','positive_hours','prevalence','hourly_AUROC','hourly_AUPRC',
      'AUPRC_CI_low','AUPRC_CI_high','hourly_Brier','ECE_10bin','calibration_slope','event_sensitivity',
      'false_alarms_per_patient_day','median_warning_hours_detected']
TEAM_PERF=pd.DataFrame(perf)
if len(TEAM_PERF):
    TEAM_PERF=TEAM_PERF[[c for c in cols if c in TEAM_PERF]].sort_values(['target','feature_set','arm']).reset_index(drop=True)
    TEAM_PERF.to_csv(RESULTS_ROOT/'team_summary_performance.csv',index=False)
    display(TEAM_PERF.round(3))
else:print('No completed arms yet.')
coh=[]
for ds in DATASETS:
    z=INDEX[INDEX.Dataset.eq(ds)];sealed=z.Group_ID.map(protected_group);dev=z[~sealed]
    coh.append({'dataset':ds,'candidate_ICU_stays_sampled':globals().get('COHORT_PROTOCOL',{}).get('candidate_n') or globals().get('SOURCE_COUNTS',{}).get(ds),
      'stays_after_YAIB_exclusions':len(z),'sealed_final_holdout_stays':int(sealed.sum()),'development_stays':len(dev),
      'development_patients':dev.Group_ID.nunique(),'hospitals':dev.Hospital_ID.nunique(),
      'development_stays_with_sepsis_prediction_window':int(dev.eligible_positive.sum())})
TEAM_COHORT=pd.DataFrame(coh);TEAM_COHORT.to_csv(RESULTS_ROOT/'team_summary_cohort.csv',index=False);display(TEAM_COHORT)
for ds in DATASETS:
    a=COHORT_ROOT/ds/'attrition_by_batch.csv'
    if a.is_file():
        att=pd.read_csv(a);print(ds,'YAIB attrition (summed over batches):');display(att.select_dtypes('number').drop(columns=[c for c in att if c=='batch'],errors='ignore').sum().to_frame('stays').T)
print(f'{RUN_MODE.upper()} | {STUDY_STAGE} | completed arms: {len(TEAM_PERF)} | files: team_summary_performance.csv, team_summary_cohort.csv in {RESULTS_ROOT}')
