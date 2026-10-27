# Stage 1b code notes (notebook `_12_stage1b`), 27 Oct 2026

This file lists, in full, every V11-layer source file embedded in `Sepsis_V11_Improved_MIMIC_eICU_12_stage1b.ipynb`, in the order the notebook uses them. The v9/v10 layer (extraction, features, the base trainer, the utility scorer, the YAIB worker) is unchanged since `_11` and is listed at the end with line counts; it is in the repository under `dev/work/mods/`.

Reading order for stage 1b: `v11_models.FlatOSTAHeads` (the model) -> `v11_train` sections "stage 1b (protocol 10b)" (targets, uncertainty weighting, input dropout, fresh hours, quantile operating point, alarm policy) and `run_fold_v11` (the `stage1b` branch) -> `team_summary_stage1b.py` (the four rules).

## Notebook configuration block (Section 1 additions)

`dev/work/cells/v11_config_block.py` (24 lines)

```python
# ---- V11 (19 Oct 2026; every item prespecified before any _11 result) ----
V11_ARMS = ['osta','output_fusion','cnn','logistic','boosted_tree','signature_boosted_tree',   # kept / literature benchmark
            'flat_osta','grud','tcn','cnn_osta','event_osta',                                  # new supervised arms (flat_osta = organ ablation)
            'ssl_cnn_osta','ssl_cnn_flat','hazard_ssl_cnn_osta',                               # self-supervised, site encoder
            'ssl_cnn_osta_pooled','ssl_cnn_flat_pooled']                                       # self-supervised, pooled encoder (adaptation)
V11_PRIMARY_LOSS = 'utility_weighted_bce'          # 'bce' | 'tls' | 'utility_weighted_bce'; original OSTA loss retired (see _9/_10)
V11_COMPARISON_LOSSES = ['bce','tls']              # run on V11_LOSS_COMPARISON_ARMS only; selection rule = validation utility + AUPRC rank-average
V11_LOSS_COMPARISON_ARMS = ['osta','ssl_cnn_osta']
V11_SSL_EPOCHS = 5                                 # self-supervised pretraining epochs on the unlabelled corpus
V11_SSL_MAX_STAYS_PER_DATASET = 75000              # unlabelled stays per database (never cohort stays; protected patients excluded)
V11_FEATURE_WORKERS = max(1,(os.cpu_count() or 2)-1)
V11_BATCH = 32                                     # was 8; one prespecified change for every neural arm
V11_DROPOUT = 0.2; V11_WEIGHT_DECAY = 1e-4         # one prespecified regularisation step (the _9 histories peaked at epoch 1-3)
V11_TREE_MAX_ITERATIONS = 1000                     # boosted trees: patient-grouped early stopping on the validation split
RUN_TRANSFER_EVALUATION = True                     # each database's model scored on the OTHER database's development patients (holdout sealed)
RUN_NO_PROXY_SENSITIVITY = True                    # osta without hydrocortisone / imaging / prophylaxis (clinician-suspicion proxies)
# ---- STAGE 1b (protocol section 10b, 24 Oct 2026; decided after the stage-1 results, blind to the test splits) ----
STAGE_1B = True                                    # True: train only STAGE1B_ARMS x STAGE1B_INPUT_DROPOUT with plain BCE; report VALIDATION only; test rows sealed on disk
STAGE1B_ARMS = ['flat_osta','flat_osta_heads']     # flat backbone vs flat backbone + seven organ heads (uncertainty-weighted)
STAGE1B_INPUT_DROPOUT = [0.0,0.1,0.2]              # predictor groups (value+flag+age) hidden together during training
STAGE1B_LOSS = 'bce'                               # the stage-2 loss by the section 10 rule (first in 3 of 4 validation comparisons)
STAGE2_OPERATING_POINT = 'absolute'                # 'absolute' (V11) | 'quantile' (10b item E); set by rule 10b.2.3 for stage 2
STAGE2_PERSISTENCE = 1; STAGE2_FRESH_ONLY = False  # alarm policy (10b item F); set by rule 10b.2.4 for stage 2
```

## Cell 6: resolve settings, bind the run (main_14_v11.py)

`dev/work/cells/main_14_v11.py` (32 lines)

```python
# 6. Resolve smoke/full settings and bind the run to data, code and split policy (V11 protocol).
TRAIN_CONFIG=training_config(RUN_MODE,MAX_HOURS)
TRAIN_CONFIG.update(batch=V11_BATCH,release_final=RELEASE_FINAL_HOLDOUT,runtime_versions=RUNTIME_VERSIONS,
    arms=list(V11_ARMS),loss=V11_PRIMARY_LOSS,comparison_losses=list(V11_COMPARISON_LOSSES),loss_comparison_arms=list(V11_LOSS_COMPARISON_ARMS),
    ssl_epochs=1 if RUN_MODE=='smoke' else V11_SSL_EPOCHS,cnn_depth=2,event_lookback=24,dropout=V11_DROPOUT,weight_decay=V11_WEIGHT_DECAY,
    tree_max_iterations=20 if RUN_MODE=='smoke' else V11_TREE_MAX_ITERATIONS,tree_step=10 if RUN_MODE=='smoke' else 50,
    conformal_alpha=.02,tls_tau=12.,protocol_v11='v11-1.0',
    operating_point=STAGE2_OPERATING_POINT,persistence=STAGE2_PERSISTENCE,fresh_only=STAGE2_FRESH_ONLY,quantile_min_hours=10000)
if STAGE_1B:   # protocol 10b: validation-only development of the project model, the operating point and the alarm policy
    TRAIN_CONFIG.update(stage='1b',arms=list(STAGE1B_ARMS),loss=STAGE1B_LOSS,comparison_losses=[],loss_comparison_arms=[],
        input_dropout_grid=[float(q) for q in STAGE1B_INPUT_DROPOUT],stress_conditions=[],protocol_v11='v11-1.0+10b')
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
  'stage_1b':('Protocol 10b: flat_osta vs flat_osta_heads x input dropout {0,0.1,0.2}, plain BCE; the quantile operating point and the alarm policy '
              '(persistence 1/2 h, all/fresh hours) evaluated on the VALIDATION split only; rules 10b.2.1-4 decide; test-split rows are written '
              'to test_rows_sealed.json and never printed; the sealed holdout is untouched') if STAGE_1B else 'not active',
  'evaluation_scope':'protected cross-database final test' if RELEASE_FINAL_HOLDOUT else 'internal development split + development-level transfer; protected 20% patient hash sealed'})
FULL_PREVIEW=training_config('full',MAX_HOURS)
assert TRAIN_CONFIG['epochs']==(2 if RUN_MODE=='smoke' else 30)
display(pd.DataFrame({k:[str(TRAIN_CONFIG[k])] for k in ['epochs','ssl_epochs','seeds','small_model','bootstrap','batch','dropout','weight_decay','loss','comparison_losses','false_alarm_budget']},index=['this run ('+RUN_MODE+')']).T)
print('Run:',RUN_KEY,'| features:',len(FEATURES),'| raw-control features:',len(CORE_FEATURES),'| arms:',len(TRAIN_CONFIG['arms']),'| stage 1b:',STAGE_1B,'|',STUDY_STAGE[:80])
```

## Cell 5c: unlabelled corpus (ssl_corpus_v11.py)

`dev/work/cells/ssl_corpus_v11.py` (30 lines)

```python
# 5c. Unlabelled corpus for self-supervised pretraining: stays never labelled by YAIB, protected-hash
# patients excluded, no label extraction of any kind. Features are built with the same code as the
# labelled sample (same schema), in parallel, and reused afterwards. Capped per database in Section 1.
CORPUS={}
if STAGE_1B:
    SSL_KEY='stage1b_no_pretraining';print('Stage 1b: no self-supervised arms, the unlabelled corpus is not built.')
elif DATA_SOURCE=='clinical':
    SSL_KEY=signature({'raw_stage':RAW_STAGE_KEY,'code':signature({k:EMBEDDED_MODULES[k]['sha256'] for k in ['v9_data.py','v10_features.py','v11_data.py','feature_specs.json']}),
                       'cap':V11_SSL_MAX_STAYS_PER_DATASET,'seed':RANDOM_STATE,'max_hours':MAX_HOURS,'horizon':HORIZON_HOURS,
                       'excluded_cohort_stays':sorted(int(x) for x in INDEX.stay_id)})[:16]
    SSL_ROOT=VALIDATION_ROOT/'ssl_corpus'/SSL_KEY;SSL_ROOT.mkdir(parents=True,exist_ok=True)
    for ds in DATASETS:
        dest=SSL_ROOT/ds;stage=dest/'raw_stage';shards=dest/'shards';complete=dest/'completed.json';dest.mkdir(parents=True,exist_ok=True)
        if complete.is_file():
            CORPUS[ds]=pd.read_parquet(shards/'index.parquet');print('Reuse unlabelled corpus:',ds,len(CORPUS[ds]),'stays');continue
        selected,static=unlabelled_stays(ds,resolved_raw[ds],INDEX.loc[INDEX.Dataset.eq(ds),'stay_id'],protected_group,
                                         V11_SSL_MAX_STAYS_PER_DATASET,RANDOM_STATE,MAX_HOURS)
        print(f'{ds}: unlabelled corpus of {len(selected)} stays (cohort stays and protected patients excluded)',flush=True)
        if not (stage/'raw_complete.json').is_file():
            stage.mkdir(parents=True,exist_ok=True)
            RawExtractor(ds,resolved_raw[ds],selected,stage,MAX_HOURS,memory=DUCKDB_MEMORY,temp=str(RUNTIME_ROOT/'v10_duckdb_temp')).extract()
            atomic_json(stage/'raw_complete.json',{'ssl_key':SSL_KEY,'stays':len(selected)})
        ix,feats=build_shards(ds,stage,None,shards,MAX_HOURS,HORIZON_HOURS,FEATURE_BATCH_STAYS,static=static,workers=V11_FEATURE_WORKERS)
        assert feats==FEATURES,'Unlabelled corpus must have the labelled schema'
        assert not ix.Group_ID.map(protected_group).any() and not set(ix.stay_id)&set(INDEX.loc[INDEX.Dataset.eq(ds),'stay_id'])
        atomic_json(complete,{'ssl_key':SSL_KEY,'stays':len(ix),'labels_used':'none'});CORPUS[ds]=ix
    print({ds:len(ix) for ds,ix in CORPUS.items()},'unlabelled stays per database |',SSL_ROOT)
else:
    # Synthetic engineering run: the fixture stays stand in as the unlabelled corpus (no labels are read by pretraining).
    CORPUS={ds:INDEX[INDEX.Dataset.eq(ds)].copy() for ds in DATASETS};print('Fixture: synthetic stays used as the pretraining corpus.')
```

## Cell 7: run every arm (main_15_v11.py)

`dev/work/cells/main_15_v11.py` (19 lines)

```python
# 7. V11 matched comparisons: every arm on identical hours; loss comparators; transfer to the other
# database's development patients; conformal policy; trajectory-rich subset; prespecified ensemble.
RESULT_PARTS=[]
for target in DATASETS:
    jobs=[('rich',FEATURES,TRAIN_CONFIG)]
    # Raw-vs-engineered control: raw values + masks + ages only.
    if RUN_CORE_FEATURE_ABLATION and not STAGE_1B:jobs.append(('raw',CORE_FEATURES,{**TRAIN_CONFIG,'arms':['osta','logistic','boosted_tree'],'loss_comparison_arms':[],'stress_conditions':[]}))
    # Sensitivity: without the clinician-suspicion proxies (hydrocortisone, imaging orders, prophylaxis).
    if RUN_NO_PROXY_SENSITIVITY and not STAGE_1B:jobs.append(('no_proxies',NO_PROXY_FEATURES,{**TRAIN_CONFIG,'arms':['osta'],'loss_comparison_arms':[],'stress_conditions':[]}))
    for label,fs,cfg in jobs:
        with (RESULTS_ROOT/(target+'_'+label+'.log')).open('a') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
            result=run_fold_v11(INDEX,fs,target,cfg,RESULTS_ROOT/label/target,
                                transfer_index=INDEX if (RUN_TRANSFER_EVALUATION and not STAGE_1B) else None,corpus=CORPUS if (label=='rich' and not STAGE_1B) else None)
        result['feature_set']=label;RESULT_PARTS.append(result)
        print('Completed',target,label,time.strftime('%H:%M'),flush=True)
RESULTS=pd.concat(RESULT_PARTS,ignore_index=True);RESULTS.to_csv(RESULTS_ROOT/'all_results.csv',index=False)
atomic_json(RESULTS_ROOT/'COMPLETE.json',{'status':'complete','mode':RUN_MODE,'data_source':DATA_SOURCE,'rows':len(RESULTS),
  'real_extraction_verified_in_this_run':DATA_SOURCE=='clinical'})
print('COMPLETE:',RESULTS_ROOT)
```

## Cell 7a: stage 1b summary and the four rules (team_summary_stage1b.py)

`dev/work/cells/team_summary_stage1b.py` (57 lines)

```python
# 7a. STAGE 1b summary (protocol 10b): VALIDATION-split rows only. Test-split rows exist on disk (test_rows_sealed.json) and are not read here.
if STAGE_1B:
    rows=[]
    for p in sorted(RESULTS_ROOT.glob('rich/*/seed_*/*/completed.json')):
        for r in json.loads(p.read_text()):
            if r.get('condition')=='validation_grid':rows.append(r)
    G=pd.DataFrame(rows);assert len(G) and G.condition.eq('validation_grid').all(),'Stage 1b summary found non-validation rows'
    assert not any(RESULTS_ROOT.glob('rich/*/seed_*/*/predictions_conformal.parquet')),'conformal rows must not exist in stage 1b'
    G['config']=G.base_arm+' / input dropout '+G.input_dropout.astype(str)
    G.to_csv(RESULTS_ROOT/'stage1b_validation_grid.csv',index=False)
    budget=TRAIN_CONFIG['false_alarm_budget'];decision={'run_key':RUN_KEY,'rules':'protocol 10b.2','budget':budget}
    # ---- Rule 1: backbone and input dropout, reference policy (absolute threshold, persistence 1, all hours) ----
    ref=G[G.operating_point.eq('absolute')&G.persistence.eq(1)&~G.fresh_only].copy()
    ref['val_rank']=ref.groupby('target')[['validation_utility','validation_AUPRC']].rank(ascending=False).mean(axis=1)
    show=['target','config','validation_utility','validation_AUPRC','event_sensitivity','false_alarms_per_patient_day','median_warning_hours_detected','val_rank']
    print('RULE 1 inputs (validation split, reference policy):');display(ref[show].sort_values(['target','val_rank']).round(3))
    cross=ref.groupby('config').val_rank.mean().sort_values();print('Cross-database mean rank (lower is better):');display(cross.round(2).to_frame('mean_val_rank'))
    best=cross.index[0];best_flat=cross[[c for c in cross.index if c.startswith('flat_osta /')]].index[0];best_heads=[c for c in cross.index if c.startswith('flat_osta_heads /')]
    best_heads=best_heads[0] if best_heads else None
    heads_kept=best_heads is not None and cross[best_heads]<=cross[best_flat]
    project_model=best_heads if heads_kept else best_flat
    print(f'[rule 1] project model for stage 2: {project_model} | organ heads '+('KEPT (not ranked below plain flat OSTA)' if heads_kept else 'NOT supported (ranked below plain flat OSTA)'))
    decision.update(project_model=project_model,heads_kept=bool(heads_kept),cross_rank=cross.round(3).to_dict())
    # ---- Rule 2: organ heads as explanation (per-organ validation AUROC of the 6 h target) ----
    hcols=[c for c in G.columns if c.startswith('head_auroc_6h_')]
    if hcols:
        H=ref[ref.base_arm.eq('flat_osta_heads')][['target','config']+hcols].drop_duplicates()
        print('RULE 2: per-organ head AUROC on validation (6 h target); < 0.60 on BOTH databases = uninformative');display(H.round(3))
        uninformative=[c.replace('head_auroc_6h_','') for c in hcols if (H.groupby('target')[c].max().fillna(0)<.60).all()]   # no defined target = uninformative
        print('[rule 2] uninformative heads:',uninformative or 'none');decision['uninformative_heads']=uninformative
        tw=ref[ref.base_arm.eq('flat_osta_heads')][['target','config','task_weights']].drop_duplicates();print('Learned task weights (sepsis first, then heads):');display(tw)
    # ---- Rule 3: quantile operating point (persistence 1, all hours) ----
    q=G[G.operating_point.eq('quantile')&G.persistence.eq(1)&~G.fresh_only]
    silent=lambda d:(d.false_alarms_per_patient_day.eq(0)&d.event_sensitivity.fillna(0).eq(0))
    q_ok=bool(len(q)) and bool((q.false_alarms_per_patient_day<=budget).all()) and not bool(silent(q).any()) and bool(q.operating_point_used.eq('quantile').all())
    a=G[G.operating_point.eq('absolute')&G.persistence.eq(1)&~G.fresh_only]
    r3=pd.concat([a.assign(point='absolute'),q.assign(point='quantile')]);r3['silent']=silent(r3)
    r3['silence_cause']=np.where(~r3.silent,'',np.where(r3.alarm_fraction.eq(0),'budget unattainable on the calibration split (chosen threshold never fires)','scale shift (fires on calibration, not here)'))
    print('RULE 3 inputs: quantile vs absolute operating point (validation); alarm_fraction = share of calibration hours the chosen threshold flags:')
    display(r3[['target','config','point','alarm_fraction','threshold_used','event_sensitivity','false_alarms_per_patient_day','silence_cause']].sort_values(['target','config','point']).round(3))
    print('[rule 3] quantile operating point '+('ADOPTED for stage 2' if q_ok else 'NOT adopted (budget exceeded, a model silent, or hours below the minimum); absolute threshold stays')+f' | silent models under absolute: {int(silent(a).sum())}, under quantile: {int(silent(q).sum()) if len(q) else "n/a"}')
    op='quantile' if q_ok else 'absolute';decision['operating_point']=op
    # ---- Rule 4: alarm policy for the chosen model and operating point ----
    P=G[G.config.eq(project_model)&G.operating_point.eq(op)].copy()
    agg=P.groupby(['persistence','fresh_only']).agg(sens=('event_sensitivity','mean'),fa=('false_alarms_per_patient_day','max'),warn=('median_warning_hours_detected','mean')).reset_index()
    print('RULE 4 inputs (chosen model, chosen operating point; mean sensitivity over databases, max false alarms per patient-day, mean median warning hours):');display(agg.round(3))
    ok=agg[agg.fa<=budget]
    if len(ok):
        ok=ok.sort_values(['sens','warn','persistence','fresh_only'],ascending=[False,False,True,True],na_position='last');pol=ok.iloc[0]   # sensitivity, then warning time, then simplicity
    else:pol=agg.sort_values(['fa']).iloc[0];print('[rule 4] no policy met the budget on both databases; the lowest-burden policy is recorded and reported as found')
    print(f'[rule 4] stage-2 policy: persistence {int(pol.persistence)} h, '+('fresh-information hours only' if bool(pol.fresh_only) else 'all hours')+f' | mean sensitivity {pol.sens:.3f}, max FA/patient-day {pol.fa:.3f}')
    decision.update(persistence=int(pol.persistence),fresh_only=bool(pol.fresh_only))
    atomic_json(RESULTS_ROOT/'stage1b_decision.json',decision)
    print('\nSTAGE 2 SETTINGS to copy into Section 1 (and into PROTOCOL.md 10b outcome, dated):')
    print(f"  STAGE_1B = False; project model = {project_model}; STAGE2_OPERATING_POINT = '{op}'; STAGE2_PERSISTENCE = {int(pol.persistence)}; STAGE2_FRESH_ONLY = {bool(pol.fresh_only)}")
    print('Saved:',RESULTS_ROOT/'stage1b_validation_grid.csv','and stage1b_decision.json')
else:print('Stage 1b summary skipped (STAGE_1B is False).')
```

## Cell 7b: stage-1 team summary (team_summary_v11.py)

`dev/work/cells/team_summary_v11.py` (45 lines)

```python
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
```

## Cell 8: concise summary (main_17_v11.py)

`dev/work/cells/main_17_v11.py` (32 lines)

```python
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
```

## Module v11_models.py: V11 architectures incl. FlatOSTAHeads

`dev/work/mods/v11_models.py` (245 lines)

```python
"""V11 architectures. Every model is causal by construction (past-hour outputs cannot change when
only future inputs change; verified by v11_tests) and exposes the same interface as v9_models:
forward(x, mask, hours, guidance=None) -> hourly logits; attributes arm, last_core_output, last_gates.

Arms
- flat_osta         OSTA transformer with ALL features in one group: the organ-structure ablation.
- grud              GRU with learned input/hidden decay from the age channels (Che et al. 2018 style).
- tcn               causal dilated temporal convolution network (Moor et al. style).
- cnn_osta          per-channel causal CNN encoder over [value, observed, age] -> OSTA (supervised).
- ssl_cnn_osta      the same encoder pretrained without labels (v11_train.pretrain) -> OSTA.
- ssl_cnn_flat      the pretrained encoder -> flat (single-group) head: the decisive SSL comparison.
- event_osta        attention over fresh observations of the fast channels (hourly proxy) -> OSTA.
- hazard_ssl_cnn_osta  pretrained encoder -> OSTA -> discrete-time hazard head (1/3/6/12/24 h);
                       the reported 6 h logit is logit(1 - S(6 h)).
"""
import math
import contextlib
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F
import v9_osta_base as original_osta
from v9_models import LOOKUP,organ_mapping,base_name,ExperimentModel
from v9_train import AGE_SCALE

FAST=['HR','MAP','SBP','DBP','Resp','O2Sat','Temp']
HAZARD_EDGES=[0.,1.,3.,6.,12.,24.]   # hours; bins (0,1],(1,3],(3,6],(6,12],(12,24]

def measured_channels(features):
    """Features that carry both an observed mask and an age channel (the measured channels)."""
    s=set(features)
    return [f for f in features if f+'_observed' in s and f+'_age' in s]

@contextlib.contextmanager
def flat_mapping():
    """Temporarily make every feature belong to one group so OSTA builds a single organ encoder."""
    old=original_osta.build_feature_to_organ_mapping
    def one(names):
        return {f:'all' for f in names},{'all':list(range(len(names)))}
    original_osta.build_feature_to_organ_mapping=one
    try:yield
    finally:original_osta.build_feature_to_organ_mapping=old

def osta_core(features,small,dropout,flat=False):
    kw=dict(d_organ=16 if small else 32,d_global=32 if small else 128,n_heads_organ=4,n_heads_inter=4,
            n_layers_organ=1 if small else 2,n_layers_global=1 if small else 2,dropout=dropout,mc_samples=1)
    if flat:
        with flat_mapping():return original_osta.OSTATransformer(list(features),**kw)
    return original_osta.OSTATransformer(list(features),**kw)

class CausalConv(nn.Module):
    """Left-padded 1D convolution: output at t depends on inputs <= t only."""
    def __init__(self,cin,cout,kernel,groups=1,dilation=1):
        super().__init__();self.pad=(kernel-1)*dilation;self.conv=nn.Conv1d(cin,cout,kernel,groups=groups,dilation=dilation)
    def forward(self,z):return self.conv(F.pad(z,(self.pad,0)))

class MultiChannelCausalEncoder(nn.Module):
    """Per-channel depthwise causal CNN over [value, observed, age] for every measured channel.
    Channels never mix (groups=K), so each latent stays attributable to its source channel and can be
    mapped to that channel's organ group. Dilations 1,2,4 give a receptive field of 15 h with kernel 3.
    Output: (B,T,K*depth) latents, tanh-bounded and gated (gate starts at 0.5)."""
    def __init__(self,features,channels,depth=2,hidden=8,kernel=3,dilations=(1,2,4),dropout=.1):
        super().__init__()
        self.channels=list(channels);self.depth=depth;k=len(self.channels)
        self.values=[features.index(f) for f in self.channels]
        self.observed=[features.index(f+'_observed') for f in self.channels]
        self.ages=[features.index(f+'_age') for f in self.channels]
        self.inp=CausalConv(k*3,k*hidden,kernel,groups=k)
        self.blocks=nn.ModuleList([CausalConv(k*hidden,k*hidden,kernel,groups=k,dilation=d) for d in dilations])
        self.out=CausalConv(k*hidden,k*depth,1,groups=k)
        self.dropout=nn.Dropout(dropout);self.gate=nn.Parameter(torch.zeros(k*depth))
        self.latent_names=[f'V11_CNN_{f}_{j}' for f in self.channels for j in range(depth)]
        for f in self.channels:
            for j in range(depth):LOOKUP[f'V11_CNN_{f}_{j}']=LOOKUP[base_name(f)]
    def forward(self,x):
        b,t,_=x.shape
        v=torch.stack((x[:,:,self.values],x[:,:,self.observed],x[:,:,self.ages]),dim=-1).reshape(b,t,-1).transpose(1,2)
        h=F.gelu(self.inp(v))
        for blk in self.blocks:h=h+F.gelu(blk(h))
        z=self.out(h).transpose(1,2)
        return self.dropout(torch.tanh(z)*torch.sigmoid(self.gate).view(1,1,-1))

class EncoderOSTA(nn.Module):
    """[features, encoder latents] -> OSTA (organ-grouped) or flat head."""
    def __init__(self,features,small=False,dropout=.1,depth=2,flat=False,hazard=False):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None;self.last_hazards=None
        self.encoder=MultiChannelCausalEncoder(features,measured_channels(features),depth=depth,dropout=dropout)
        self.core=osta_core(list(features)+self.encoder.latent_names,small,dropout,flat=flat)
        self.hazard=nn.Linear(32 if small else 128,len(HAZARD_EDGES)-1) if hazard else None
        self._global=None
        if hazard:
            self.core.prediction_head[0].register_forward_hook(lambda m,i,o:setattr(self,'_global',i[0]))
    def forward(self,x,mask,hours,guidance=None):
        out=self.core(torch.cat((x,self.encoder(x)),dim=-1),mask,hours);self.last_core_output=out
        if self.hazard is None:return out['logits']
        # Discrete-time hazards per bin; P(onset <= 6 h) = 1 - prod_{bins within 6 h}(1 - h_k).
        hz=torch.sigmoid(self.hazard(self._global)).clamp(1e-6,1-1e-6);self.last_hazards=hz
        within=[i for i,e in enumerate(HAZARD_EDGES[1:]) if e<=6.]
        p=1-torch.prod(1-hz[:,:,within],dim=-1)
        return torch.log(p)-torch.log1p(-p)

class FlatOSTA(nn.Module):
    def __init__(self,features,small=False,dropout=.1):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None
        self.core=osta_core(features,small,dropout,flat=True)
    def forward(self,x,mask,hours,guidance=None):
        out=self.core(x,mask,hours);self.last_core_output=out;return out['logits']

HEAD_SOFA=['SOFA_Resp','SOFAproxy_Coag','SOFAproxy_Liver','SOFA_CV','SOFAproxy_CNS','SOFA_Renal']   # the six SOFA organs, in SOFA order
HEAD_NAMES=['respiration','coagulation','liver','cardiovascular','cns','renal','any_organ']
HEAD_HORIZONS=(6,12,24)

class FlatOSTAHeads(nn.Module):
    """Stage 1b (protocol 10b): the flat backbone (one group, unrestricted attention over all predictors)
    with seven organ heads at the OUTPUT. Each head is a linear readout on the shared stay representation
    (the input of the prediction head) and predicts whether that organ's SOFA component rises within 6, 12
    and 24 h (the any_organ head: any component). The heads never feed back into the sepsis logits. The
    head losses and the sepsis loss are combined by learned uncertainty weighting (Kendall et al. 2018):
    one log-variance per task, so no auxiliary weight is chosen by hand."""
    def __init__(self,features,small=False,dropout=.1):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None;self.last_head_logits=None;self._global=None
        self.core=osta_core(features,small,dropout,flat=True)
        self.sofa=[features.index(f) for f in HEAD_SOFA if f in features];self.sofa_obs=[features.index(f+'_observed') for f in HEAD_SOFA if f in features]
        self.sofa_names=[n for f,n in zip(HEAD_SOFA,HEAD_NAMES[:6]) if f in features]
        self.n_heads=len(self.sofa)+1;d=32 if small else 128
        self.heads=nn.Linear(d,self.n_heads*len(HEAD_HORIZONS))
        self.log_var=nn.Parameter(torch.zeros(1+self.n_heads))   # task 0 = sepsis, then one per head
        self.core.prediction_head[0].register_forward_hook(lambda m,i,o:setattr(self,'_global',i[0]))
    @property
    def head_names(self):return self.sofa_names+['any_organ']
    def task_weights(self):
        """exp(-log_var) per task: the learned relative weight of each loss (reported, never set by hand)."""
        return torch.exp(-self.log_var).detach().cpu().numpy().tolist()
    def forward(self,x,mask,hours,guidance=None):
        out=self.core(x,mask,hours);self.last_core_output=out
        b,t,_=x.shape
        self.last_head_logits=self.heads(self._global).reshape(b,t,self.n_heads,len(HEAD_HORIZONS))
        return out['logits']

class GRUD(nn.Module):
    """GRU with learned decays. Input decay: each measured channel's carried value is pulled toward
    0 (the training mean after z-scoring) by exp(-relu(w)*age) when not freshly observed. Hidden
    decay: the state is damped by exp(-relu(v)*mean age) before each step. Strictly causal."""
    def __init__(self,features,small=False,dropout=.1):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None
        ch=measured_channels(features);self.values=[features.index(f) for f in ch]
        self.observed=[features.index(f+'_observed') for f in ch];self.ages=[features.index(f+'_age') for f in ch]
        self.w=nn.Parameter(torch.zeros(len(ch)));self.v=nn.Parameter(torch.zeros(1))
        hidden=32 if small else 128
        self.proj=nn.Linear(len(features),hidden);self.gru=nn.GRU(hidden,hidden,batch_first=True)
        self.head=nn.Sequential(nn.LayerNorm(hidden),nn.Dropout(dropout),nn.Linear(hidden,hidden//2),nn.GELU(),nn.Linear(hidden//2,1))
    def forward(self,x,mask,hours,guidance=None):
        age=x[:,:,self.ages].clamp_min(0);fresh=(x[:,:,self.observed]>.5)&(age*AGE_SCALE<1)
        decay=torch.exp(-F.relu(self.w)*age);vals=x[:,:,self.values]
        x=x.clone();x[:,:,self.values]=torch.where(fresh,vals,vals*decay)
        z=F.gelu(self.proj(x));b,t,_=z.shape
        h=torch.zeros(b,z.size(-1),device=x.device);outs=[]
        mean_age=age.mean(-1,keepdim=True)
        for i in range(t):
            h=h*torch.exp(-F.relu(self.v)*mean_age[:,i]).expand_as(h)
            h=self.gru(z[:,i:i+1],h.unsqueeze(0))[1][0];outs.append(h)
        return self.head(torch.stack(outs,1)).squeeze(-1)

class TCNBlock(nn.Module):
    def __init__(self,c,dilation,dropout):
        super().__init__();self.conv=CausalConv(c,c,3,dilation=dilation);self.norm=nn.LayerNorm(c);self.dropout=nn.Dropout(dropout)
    def forward(self,z):
        h=self.conv(z).transpose(1,2);h=self.dropout(F.gelu(self.norm(h))).transpose(1,2);return z+h

class CausalTCN(nn.Module):
    def __init__(self,features,small=False,dropout=.1):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None
        width=32 if small else 96
        self.project=nn.Conv1d(len(features),width,1)
        self.blocks=nn.Sequential(*(TCNBlock(width,d,dropout) for d in (1,2,4,8,16)))
        self.head=nn.Sequential(nn.LayerNorm(width),nn.Linear(width,width//2),nn.GELU(),nn.Linear(width//2,1))
    def forward(self,x,mask,hours,guidance=None):
        h=self.blocks(self.project(x.transpose(1,2))).transpose(1,2);return self.head(h).squeeze(-1)

class HourlyEventOSTA(nn.Module):
    """Attention from each hour to the FRESH observations of the fast channels within a causal lookback
    (hourly proxy of an observation-event model; keys exist only where a channel was measured)."""
    def __init__(self,features,small=False,dropout=.1,lookback=24):
        super().__init__();self.arm='osta';self.last_gates=None;self.last_core_output=None
        self.fast=[f for f in FAST if f in features and f+'_observed' in features and f+'_age' in features]
        self.value=[features.index(f) for f in self.fast];self.observed=[features.index(f+'_observed') for f in self.fast]
        self.age=[features.index(f+'_age') for f in self.fast];self.lookback=lookback
        self.dim=8 if small else 16;self.heads=2 if small else 4
        self.variable=nn.Embedding(len(self.fast),self.dim);self.event=nn.Linear(2,self.dim)
        self.query=nn.Sequential(nn.Linear(2,self.dim),nn.LayerNorm(self.dim))
        self.attn=nn.MultiheadAttention(self.dim,self.heads,batch_first=True,dropout=dropout)
        self.sentinel=nn.Parameter(torch.zeros(1,1,self.dim))
        self.latents=[f'V11_EVENT_{j}' for j in range(self.dim)]
        for c in self.latents:LOOKUP[c]='temporal_events'
        self.core=osta_core(list(features)+self.latents,small,dropout)
    def forward(self,x,mask,hours,guidance=None):
        b,t,_=x.shape;k=len(self.fast)
        fresh=(x[:,:,self.observed]>.5)&(x[:,:,self.age]*AGE_SCALE<1)&(mask.unsqueeze(-1)>.5)
        vals=x[:,:,self.value]
        etime=hours.unsqueeze(-1).expand(-1,-1,k).reshape(b,t*k);value=vals.reshape(b,t*k)
        var=torch.arange(k,device=x.device).view(1,1,k).expand(b,t,k).reshape(b,t*k)
        emb=self.event(torch.stack([value,etime/120.],-1))+self.variable(var)
        emb=torch.cat([self.sentinel.expand(b,-1,-1),emb],1)
        queries=self.query(torch.stack([hours/120.,(hours/120.)**2],-1))
        lag=hours.unsqueeze(-1)-etime.unsqueeze(1)
        allow=(lag>=0)&(lag<self.lookback)&fresh.reshape(b,t*k)[:,None,:]
        allowed=torch.cat([torch.ones((b,t,1),device=x.device,dtype=torch.bool),allow],-1)
        disallow=(~allowed).repeat_interleave(self.heads,dim=0)
        ctx,_=self.attn(queries,emb,emb,attn_mask=disallow,need_weights=False)
        out=self.core(torch.cat([x,ctx*mask.unsqueeze(-1)],-1),mask,hours);self.last_core_output=out
        return out['logits']

class Pretrainer(nn.Module):
    """Self-supervised heads on the encoder latents (no sepsis labels anywhere):
    forecast: next fresh value of each measured channel;   measured: channel measured within 6 h;
    organ: the 6 SOFA components at +6/+12/+24 h;          worsening: any SOFA component rises within 6/12/24 h."""
    SOFA=['SOFA_Resp','SOFA_CV','SOFA_Renal','SOFAproxy_Coag','SOFAproxy_Liver','SOFAproxy_CNS']
    def __init__(self,features,depth=2,dropout=.1):
        super().__init__()
        self.encoder=MultiChannelCausalEncoder(features,measured_channels(features),depth=depth,dropout=dropout)
        k=len(self.encoder.channels);self.k=k;d=k*depth
        self.forecast=nn.Linear(depth,1);self.measured=nn.Linear(depth,1)
        self.sofa=[features.index(f) for f in self.SOFA if f in features];self.sofa_obs=[features.index(f+'_observed') for f in self.SOFA if f in features]
        self.organ=nn.Sequential(nn.Linear(d,64),nn.GELU(),nn.Linear(64,len(self.sofa)*3))
        self.worsen=nn.Sequential(nn.Linear(d,32),nn.GELU(),nn.Linear(32,3))
    def forward(self,x):
        z=self.encoder(x);b,t,_=z.shape
        per=z.reshape(b,t,self.k,self.encoder.depth)
        return {'latent':z,'forecast':self.forecast(per).squeeze(-1),'measured':self.measured(per).squeeze(-1),
                'organ':self.organ(z).reshape(b,t,len(self.sofa),3),'worsen':self.worsen(z)}

def make_model(arm,features,cfg):
    small=cfg['small_model'];dropout=cfg['dropout']
    if arm in ['osta','output_fusion','cnn']:raise ValueError('v9 arms are built by v9_models.ExperimentModel')
    if arm=='flat_osta':return FlatOSTA(features,small,dropout)
    if arm=='flat_osta_heads':return FlatOSTAHeads(features,small,dropout)
    if arm=='grud':return GRUD(features,small,dropout)
    if arm=='tcn':return CausalTCN(features,small,dropout)
    if arm=='event_osta':return HourlyEventOSTA(features,small,dropout,cfg.get('event_lookback',24))
    if arm in ['cnn_osta','ssl_cnn_osta','ssl_cnn_osta_pooled']:return EncoderOSTA(features,small,dropout,cfg.get('cnn_depth',2))
    if arm in ['ssl_cnn_flat','ssl_cnn_flat_pooled']:return EncoderOSTA(features,small,dropout,cfg.get('cnn_depth',2),flat=True)
    if arm in ['hazard_ssl_cnn_osta']:return EncoderOSTA(features,small,dropout,cfg.get('cnn_depth',2),hazard=True)
    raise ValueError('Unknown v11 arm: '+arm)

SSL_ARMS={'ssl_cnn_osta':'site','ssl_cnn_flat':'site','hazard_ssl_cnn_osta':'site','ssl_cnn_osta_pooled':'pooled','ssl_cnn_flat_pooled':'pooled'}
```

## Module v11_train.py: losses, stage 1b helpers, fold runner

`dev/work/mods/v11_train.py` (599 lines)

```python
"""V11 training and evaluation driver (on top of v9_train / v10_train).

Prespecified protocol (19 Oct 2026, before any _11 result):
- losses: 'utility_weighted_bce' (PRIMARY), 'bce', 'tls' (temporal label smoothing);
  the hazard arm trains a discrete-time survival likelihood. Loss comparators run on the arms
  listed in cfg['loss_comparison_arms']. The loss carried to the full cohort is chosen by the
  rank-average of VALIDATION-split utility and AUPRC (never on test).
- early stopping on validation AUPRC (patience cfg['patience']); AdamW weight decay 1e-4.
- self-supervised pretraining on an unlabelled corpus (no sepsis labels; protected patients
  excluded): 'site' encoder = the target database's corpus; 'pooled' = both databases.
- evaluation: the v10 panel (utility, AUPRC, AUROC, sensitivity at the false-alarm budget,
  warning time, false alarms/day, calibration) + lead time versus the first antibiotic order,
  a conformal alarm policy, trajectory-rich hours, transfer rows (model of one database applied
  to the other database's DEVELOPMENT patients; the final holdout stays sealed), and a
  prespecified mean ensemble.
"""
from pathlib import Path
import json,os,gc,math,pickle
import numpy as np
import pandas as pd
import torch
from torch import nn
from sklearn.metrics import average_precision_score
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from v9_train import (AGE_SCALE,SequenceStore,fit_normalizer,loader,batch_to,seed_all,predict,calibrate,apply_calibration,
    select_threshold,evaluate,clustered_ci,paired_difference,atomic_json,atomic_torch,train_observers,OSTA_FAMILY)
from v9_models import ObserverBank,ExperimentModel
from v10_train import tabular_arrays,tabular_predict,utility_block,hospital_ci
from v10_protocol import partition,protected_group
from v10_evaluation import patient_utilities,normalized_from,utility_threshold_sweep
from v11_models import make_model,Pretrainer,SSL_ARMS,measured_channels,FAST,HAZARD_EDGES,HEAD_HORIZONS
from v9_data import signature,sha

V9_ARMS=['osta','output_fusion','cnn']
TABULAR=['logistic','boosted_tree','signature_boosted_tree']
NEURAL_V11=['flat_osta','flat_osta_heads','grud','tcn','cnn_osta','ssl_cnn_osta','ssl_cnn_flat','ssl_cnn_osta_pooled','ssl_cnn_flat_pooled','event_osta','hazard_ssl_cnn_osta']
ENSEMBLE_MEMBERS=['osta','cnn','ssl_cnn_osta']
PROXY_FEATURES=['Med_Hydrocortisone_24h','Imaging_24h','Prophylaxis_Surgical_24h','Prophylaxis_Medical']

# ----------------------------------------------------------------------------- losses
def utility_gap_weight(delta):
    """U_TP - U_FN of the PhysioNet utility as a function of hours from onset (delta = hour - onset):
    1.0 at -6 h rising linearly to 2.0 at +3 h."""
    return 1.+(delta.clamp(-6.,3.)+6.)/9.

def targets_and_weights(batch,onsets,loss,horizon=6,tls_tau=12.):
    """(target, weight) over all hours. weight=0 excludes an hour. onsets: (B,) hours, NaN if no onset."""
    y=batch['y'];elig=batch['eligible'];mask=batch['mask'];hours=batch['hours']
    on=onsets.view(-1,1);has=torch.isfinite(on);delta=torch.where(has,hours-torch.nan_to_num(on),torch.full_like(hours,-1e9))
    if loss=='bce':return y,elig
    if loss=='utility_weighted_bce':
        post=has&(delta>=0)&(delta<=3)&(mask>.5)          # onset .. onset+3 h: training positives only
        target=torch.where(post,torch.ones_like(y),y);use=((elig>.5)|post).float()
        pos=(target>.5)&(use>.5);w=torch.where(pos,utility_gap_weight(delta),torch.ones_like(y))
        if pos.any():w=torch.where(pos,w/w[pos].mean(),w)   # positive weights normalised to mean 1
        return target,w*use
    if loss=='tls':
        d=-delta  # hours until onset
        ramp=.5*torch.clamp(1-(d-horizon)/tls_tau,min=0.)
        soft=torch.where(has&(d>horizon)&(elig>.5),ramp,y)
        return soft,elig
    raise ValueError('Unknown loss '+str(loss))

def hazard_nll(hazards,batch,onsets):
    """Discrete-time survival likelihood over HAZARD_EDGES bins for every pre-onset (or non-septic)
    observed hour; censored at the end of the observed stay. hazards: (B,T,K) in (0,1)."""
    hours=batch['hours'];mask=batch['mask'];on=onsets.view(-1,1);has=torch.isfinite(on)
    last=(hours*mask).max(1,keepdim=True).values;c=last-hours               # known follow-up from each hour
    d=torch.where(has,torch.nan_to_num(on)-hours,torch.full_like(hours,float('inf')))
    use=(mask>.5)&((~has)|(d>0))
    edges=torch.tensor(HAZARD_EDGES,device=hours.device);lo=edges[:-1].view(1,1,-1);hi=edges[1:].view(1,1,-1)
    dd=d.unsqueeze(-1);cc=c.unsqueeze(-1)
    event=(dd>lo)&(dd<=hi)&(dd<=cc)                                          # onset falls in this bin and is observed
    survived=(hi<=cc)&(dd>hi)                                                # bin fully observed without onset
    ll=(torch.log(hazards)*event.float()+torch.log1p(-hazards)*survived.float()).sum(-1)
    return -(ll*use.float()).sum()/use.float().sum().clamp_min(1.)

# ----------------------------------------------------------------------------- stores
class SignatureStore(SequenceStore):
    """Appends depth-2 path signatures of the fast channels (time-augmented, carried-forward
    z-scored values) over trailing windows: level-1 increments and level-2 iterated integrals.
    Used only by the signature_boosted_tree arm (the PhysioNet 2019 winner's method)."""
    def __init__(self,index,features,norm,max_hours,windows=(6,24)):
        super().__init__(index,features,norm,max_hours)
        self.fast=[f for f in FAST if f in features];self.fidx=[features.index(f) for f in self.fast];self.windows=windows
        d=len(self.fast)+1;names=['t']+self.fast
        self.sig_names=[f'Sig{w}h_{a}' for w in windows for a in names]+[f'Sig{w}h_{a}_{b}' for w in windows for a in names for b in names]
        self.base_features=list(features);self.features=list(features)+self.sig_names
    def base_item(self,i):
        self.features,ext=self.base_features,self.features
        try:return super().__getitem__(i)
        finally:self.features=ext
    @staticmethod
    def signatures(path):
        """path: (n,d) points. Returns level-1 (d,) and level-2 (d*d,) signature terms."""
        if len(path)<2:return np.zeros(path.shape[1]),np.zeros(path.shape[1]**2)
        # Exact level-2 iterated integrals of the piecewise-linear path (Chen's identity on linear segments).
        inc=np.diff(path,axis=0);cum=path[:-1]-path[0]
        return path[-1]-path[0],(cum.T@inc+.5*inc.T@inc).ravel()
    def __getitem__(self,i):
        item=self.base_item(i);x=item['x'];n=int(item['mask'].sum());out=np.zeros((x.shape[0],len(self.sig_names)),np.float32)
        vals=x[:n][:,self.fidx];t=(item['hours'][:n]/24.)[:,None];P=np.concatenate([t,vals],1);col=0
        for w in self.windows:
            d=P.shape[1];l1=np.zeros((n,d));l2=np.zeros((n,d*d))
            for k in range(n):
                a,b=self.signatures(P[max(0,k-w):k+1]);l1[k]=a;l2[k]=b
            out[:n,col:col+d]=l1;col+=d;out[:n,col:col+d*d]=l2;col+=d*d
        item['x']=np.concatenate([x,out],1);return item

def onset_tensor(store,device):
    return torch.tensor(store.index.OnsetHour.to_numpy(dtype=np.float32),device=device)

# ----------------------------------------------------------------------------- pretraining
def ssl_targets(x,mask,pt):
    """Label-free targets from the batch itself (future values of the same stay)."""
    b,t,_=x.shape;enc=pt.encoder
    fresh=(x[:,:,enc.observed]>.5)&(x[:,:,enc.ages]*AGE_SCALE<1)&(mask.unsqueeze(-1)>.5)
    nxt_val=torch.zeros_like(x[:,:,enc.values]);nxt_ok=torch.zeros_like(fresh)
    nxt_val[:,:-1]=x[:,1:,enc.values];nxt_ok[:,:-1]=fresh[:,1:]
    # measured within 6 h: any fresh observation in (t, t+6]
    cs=torch.cumsum(fresh.float(),1);pad=torch.cat([torch.zeros_like(cs[:,:1]),cs],1)
    idx=torch.arange(t,device=x.device);hi=torch.clamp(idx+6,max=t-1)
    within=(pad[:,hi+1]-pad[:,idx+1])>0;within_ok=(mask.unsqueeze(-1)>.5)&((idx+1)<t).view(1,t,1)
    out={'forecast':(nxt_val,nxt_ok),'measured':(within.float(),within_ok)}
    if pt.sofa:
        s=x[:,:,pt.sofa];so=x[:,:,pt.sofa_obs]>.5;organ=[];ok=[];worse=[];wok=[]
        for h in (6,12,24):
            fut=torch.zeros_like(s);fok=torch.zeros_like(so)
            if t>h:fut[:,:-h]=s[:,h:];fok[:,:-h]=so[:,h:]&(mask[:,h:].unsqueeze(-1)>.5)
            organ.append(fut);ok.append(fok)
            # any component rises within h hours (known now and later)
            m=torch.zeros_like(s);mk=torch.zeros_like(so)
            for j in range(1,h+1):
                if t>j:
                    cand=torch.full_like(s,-1e9);cand[:,:-j]=torch.where(so[:,j:]&(mask[:,j:].unsqueeze(-1)>.5),s[:,j:],torch.full_like(s[:,j:],-1e9))
                    m=torch.maximum(m,cand) if j>1 else cand;mk[:,:-j]|=so[:,j:]&(mask[:,j:].unsqueeze(-1)>.5)
            known=so&mk;rise=((m>s+1e-6)&known).any(-1);worse.append(rise.float());wok.append(known.any(-1))
        out['organ']=(torch.stack(organ,-1),torch.stack(ok,-1));out['worsen']=(torch.stack(worse,-1),torch.stack(wok,-1))
    return out

def ssl_loss(pred,targets):
    total=0.;parts={}
    for k,(tgt,ok) in targets.items():
        okf=ok.float()
        if okf.sum()==0:continue
        if k in ('measured','worsen'):l=nn.functional.binary_cross_entropy_with_logits(pred[k],tgt,reduction='none')
        else:l=nn.functional.smooth_l1_loss(pred[k],tgt,reduction='none')
        v=(l*okf).sum()/okf.sum();parts[k]=float(v.detach());total=total+v
    return total,parts

def pretrain(stores,features,cfg,seed,path,device,label='site'):
    """Self-supervised pretraining of the encoder on unlabelled stays. `stores`: list of SequenceStores
    (already normalised with the TARGET's normaliser). Checkpoint by validation SSL loss on a
    held-out tenth of the corpus stays. Returns the encoder state dict."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file():return torch.load(path,map_location='cpu',weights_only=False)['encoder']
    seed_all(seed);pt=Pretrainer(features,depth=cfg.get('cnn_depth',2),dropout=cfg['dropout']).to(device)
    opt=torch.optim.AdamW(pt.parameters(),lr=cfg['learning_rate'],weight_decay=1e-4)
    index=pd.concat([s.index for s in stores],ignore_index=True);norm=stores[0].norm
    val_mask=(np.arange(len(index))%10==0)
    train=SequenceStore(index[~val_mask],features,norm,cfg['max_hours']);val=SequenceStore(index[val_mask],features,norm,cfg['max_hours'])
    best=math.inf;history=[]
    for ep in range(cfg['ssl_epochs']):
        for split,store in [('train',train),('val',val)]:
            pt.train(split=='train');tot=0.;n=0;agg={}
            for b in loader(store,cfg['batch'],split=='train',seed+ep):
                q=batch_to(b,device);x=q['x']
                with torch.set_grad_enabled(split=='train'):
                    tg=ssl_targets(x,q['mask'],pt);loss,parts=ssl_loss(pt(x),tg)
                    if split=='train' and torch.is_tensor(loss):
                        opt.zero_grad();loss.backward();nn.utils.clip_grad_norm_(pt.parameters(),1.);opt.step()
                tot+=float(loss) if torch.is_tensor(loss) else 0.;n+=1
                for k,v in parts.items():agg[k]=agg.get(k,0.)+v
            avg=tot/max(n,1);history.append({'epoch':ep+1,'split':split,'loss':avg,**{k:v/max(n,1) for k,v in agg.items()}})
            if split=='val' and avg<best:
                best=avg;atomic_torch(path,{'encoder':{k:v.detach().cpu().clone() for k,v in pt.encoder.state_dict().items()},
                    'seed':seed,'population':label,'validation_ssl_loss':best,'stays':int(len(index)),'labels_used':'none'})
        print(f'SSL {label} epoch {ep+1} train {history[-2]["loss"]:.4f} val {history[-1]["loss"]:.4f}',flush=True)
    atomic_json(path.with_suffix('.history.json'),history)
    return torch.load(path,map_location='cpu',weights_only=False)['encoder']

# ----------------------------------------------------------------------------- neural training
def build_model(arm,features,bank,cfg,encoder_state=None):
    if arm in V9_ARMS:model=ExperimentModel(features,arm,bank.names,small=cfg['small_model'],dropout=cfg['dropout'])
    else:model=make_model(arm,features,cfg)
    if encoder_state is not None:model.encoder.load_state_dict(encoder_state)
    return model

def train_neural(arm,model,train,val,bank,cfg,seed,path,device,loss):
    path=Path(path);path.mkdir(parents=True,exist_ok=True);best_path=path/'best.pt';last_path=path/'last.pt'
    model.to(device);opt=torch.optim.AdamW(model.parameters(),lr=cfg['learning_rate'],weight_decay=cfg.get('weight_decay',1e-4))
    best=-1.;wait=0;start=0;history=[];onsets=onset_tensor(train,device)
    if last_path.is_file():
        st=torch.load(last_path,map_location=device,weights_only=False);model.load_state_dict(st['model']);opt.load_state_dict(st['optimizer'])
        start=st['epoch']+1;best=st['best'];wait=st['wait'];history=st['history']
    ld=loader(train,cfg['batch'],True,seed);ld.batch_sampler.epoch=start
    p_in=float(cfg.get('input_dropout',0.) or 0.);groups,n_groups=feature_groups(train.features) if p_in>0 else (None,0)
    heads=getattr(model,'heads',None) is not None
    for ep in range(start,cfg['epochs']):
        if wait>=cfg['patience']:break
        seed_all(seed+ep);model.train();bank.eval();tot=0.;nb=0
        for b in ld:
            b=batch_to(b,device)
            with torch.no_grad():z=bank(b['x']) if arm in OSTA_FAMILY and arm!='osta' else None
            xin=input_dropout(b['x'],groups,n_groups,p_in) if p_in>0 else b['x']
            logits=model(xin,b['mask'],b['hours'],z);on=onsets[b['idx']]
            if arm.startswith('hazard_'):l=hazard_nll(model.last_hazards,b,on)
            else:
                target,w=targets_and_weights(b,on,loss,cfg['horizon'],cfg.get('tls_tau',12.))
                if w.sum()==0:continue
                l=(nn.functional.binary_cross_entropy_with_logits(logits,target,reduction='none')*w).sum()/w.sum()
            if heads:l=uncertainty_weighted([l,heads_loss(model,b)],model.log_var)   # heads read the UNDROPPED targets from b['x']
            if not torch.isfinite(l):raise FloatingPointError(f'{arm}: nonfinite loss')
            opt.zero_grad();l.backward();nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step();tot+=float(l.detach());nb+=1
        pred,_=predict(model,bank,val,cfg['batch'],device)
        score=average_precision_score(pred.y,pred.logit) if pred.y.nunique()==2 else float('nan')
        if not np.isfinite(score):raise ValueError('Validation target has fewer than two classes')
        if score>best:best=score;wait=0;atomic_torch(best_path,{'state':model.state_dict(),'epoch':ep,'val_AUPRC':best})
        else:wait+=1
        history.append({'epoch':ep+1,'loss':tot/max(nb,1),'val_hourly_AUPRC':score,**({'task_weights':model.task_weights()} if heads else {})})
        atomic_torch(last_path,{'model':model.state_dict(),'optimizer':opt.state_dict(),'epoch':ep,'best':best,'wait':wait,'history':history})
        print(arm,loss,'epoch',ep+1,'loss',round(tot/max(nb,1),5),'validation AUPRC',round(score,5),flush=True)
    model.load_state_dict(torch.load(best_path,map_location=device,weights_only=False)['state'])
    atomic_json(path/'training_history.json',history);return model.eval()

# ----------------------------------------------------------------------------- stage 1b (protocol 10b)
def component_rise_targets(x,mask,sofa,sofa_obs,horizons=HEAD_HORIZONS):
    """Per-organ targets for the organ heads: for each SOFA component k and horizon h, 1 if the component
    is observed later within h hours at a HIGHER value than now (both observed), plus an any_organ target.
    Returns (target (B,T,K+1,H), ok (B,T,K+1,H)); ok marks hours where the target is defined. Label-free:
    built from the batch's own future values, as ssl_targets does, but kept per component."""
    s=x[:,:,sofa];so=x[:,:,sofa_obs]>.5;b,t,k=s.shape;tg=[];oks=[]
    for h in horizons:
        m=torch.full_like(s,-1e9);mk=torch.zeros_like(so)
        for j in range(1,h+1):
            if t>j:
                later=so[:,j:]&(mask[:,j:].unsqueeze(-1)>.5)
                cand=torch.full_like(s,-1e9);cand[:,:-j]=torch.where(later,s[:,j:],torch.full_like(s[:,j:],-1e9))
                m=torch.maximum(m,cand);mk[:,:-j]|=later
        known=so&mk;rise=(m>s+1e-6)&known
        anyk=known.any(-1,keepdim=True);anyr=(rise&known).any(-1,keepdim=True)
        tg.append(torch.cat([rise.float(),anyr.float()],-1));oks.append(torch.cat([known,anyk],-1))
    return torch.stack(tg,-1),torch.stack(oks,-1)

def heads_loss(model,b):
    """Mean BCE of the organ heads over defined, in-stay hours (the heads' own task loss)."""
    tgt,ok=component_rise_targets(b['x'],b['mask'],model.sofa,model.sofa_obs)
    okf=(ok&(b['mask'].unsqueeze(-1).unsqueeze(-1)>.5)).float()
    if okf.sum()==0:return None
    l=nn.functional.binary_cross_entropy_with_logits(model.last_head_logits,tgt,reduction='none')
    return (l*okf).sum()/okf.sum()

def uncertainty_weighted(losses,log_var):
    """Kendall, Gal & Cipolla (2018) multi-task weighting: sum_i exp(-s_i) L_i + s_i, s_i learned."""
    total=0.
    for i,l in enumerate(losses):
        if l is None:continue
        total=total+torch.exp(-log_var[i])*l+log_var[i]
    return total

def feature_groups(features):
    """Group id per feature column: a measured channel's value, _observed and _age columns share one id,
    so input dropout hides the three together (protocol 10b, item C)."""
    base={};ids=[]
    for f in features:
        bn=f[:-9] if f.endswith('_observed') else f[:-4] if f.endswith('_age') else f
        ids.append(base.setdefault(bn,len(base)))
    return torch.tensor(ids,dtype=torch.long),len(base)

def input_dropout(x,groups,n_groups,p,generator=None):
    """Hide whole predictor groups (value+flag+age together) with probability p per stay-hour. Training only.
    Hidden columns become 0 = the normalised mean (flags 0 = not measured)."""
    if p<=0:return x
    keep=(torch.rand(x.shape[0],x.shape[1],n_groups,device=x.device,generator=generator)>=p).float()
    return x*keep[:,:,groups.to(x.device)]

def fresh_hours(store):
    """Hours in which at least one measured channel was newly charted (age < 1 h), per stay-hour.
    Policy item F (protocol 10b): alarms may be restricted to these hours."""
    chans=measured_channels(store.features)
    oi=[store.features.index(f+'_observed') for f in chans];ai=[store.features.index(f+'_age') for f in chans];rows=[]
    for i in range(len(store)):
        b=store[i];n=int(b['mask'].sum());x=b['x'][:n]
        fresh=((x[:,oi]>.5)&(x[:,ai]*AGE_SCALE<1)).any(1) if oi else np.ones(n,bool)
        rows.append(pd.DataFrame({'Patient_ID':store.index.Patient_ID.iloc[i],'Hour':b['hours'][:n],'fresh':fresh}))
    return pd.concat(rows,ignore_index=True)

def with_fresh(d,fresh):
    """Attach the fresh flag to a prediction frame (missing hours count as not fresh)."""
    if fresh is None or 'fresh' in d:return d
    dd=d.assign(Patient_ID=d.Patient_ID.astype(str)).merge(fresh.assign(Patient_ID=fresh.Patient_ID.astype(str)),on=['Patient_ID','Hour'],how='left')
    dd['fresh']=dd.fresh.fillna(False).astype(bool);dd['Patient_ID']=d.Patient_ID.to_numpy();return dd

def alarm_fraction(d,threshold):
    """Share of scored hours at or above the threshold: the alarm rate the quantile operating point carries over."""
    return float(np.mean(d.risk.to_numpy()>=threshold))

def quantile_threshold(d,fraction,min_hours=10000):
    """Quantile operating point (protocol 10b, item E): the threshold that flags the same FRACTION of this
    population's own hours. Label-free. Below min_hours the caller must fall back to the absolute threshold."""
    r=d.risk.to_numpy(dtype=float)
    if len(r)<min_hours:return None
    if fraction<=0:return 1.0000001
    return float(np.quantile(r,1-min(fraction,1.)))

def operating_threshold(d,chosen,cfg,key='threshold',frac_key='alarm_fraction'):
    """Absolute (V11) or quantile (10b) operating point for a scored population; records which was used."""
    if cfg.get('operating_point','absolute')=='quantile' and frac_key in chosen:
        q=quantile_threshold(d,chosen[frac_key],cfg.get('quantile_min_hours',10000))
        if q is not None:return q,'quantile'
    return chosen[key],'absolute'

def alarm_records_v11(d,threshold,cooldown=6,horizon=6,persistence=1,fresh_only=False):
    """v9 alarm_records with two policy options: persistence (risk at or above the threshold for this many
    consecutive scored hours before an alarm) and fresh_only (alarms only in hours with new charting).
    False alarms are still counted against every scored hour (at_risk_hours)."""
    rows=[];use_fresh=fresh_only and 'fresh' in d
    for pid,g in d.groupby('Patient_ID',sort=False,observed=True):
        g=g.sort_values('Hour');onset=g.OnsetHour.iloc[0];last=-np.inf;false=0;leads=[];total=0;run=0;prev_h=None
        fr=g.fresh.to_numpy() if use_fresh else np.ones(len(g),bool)
        for h,p,f in zip(g.Hour,g.risk,fr):
            run=(run+1 if (prev_h is not None and h-prev_h<=1.001 and p>=threshold) else (1 if p>=threshold else 0));prev_h=h
            if p>=threshold and run>=persistence and f and h-last>=cooldown:
                last=h;total+=1
                if pd.notna(onset) and 0<onset-h<=horizon:leads.append(onset-h)
                else:false+=1
        evaluable=bool((g.y==1).any())
        rows.append({'Patient_ID':pid,'Group_ID':g.Group_ID.iloc[0],'event_evaluable':evaluable,'detected':bool(leads),
          'warning_hours':max(leads) if leads else np.nan,'false_alarms':false,'alarms':total,'at_risk_hours':len(g)})
    return pd.DataFrame(rows)

def evaluate_v11(d,threshold,cfg,persistence=1,fresh_only=False):
    """v9 evaluate (hourly metrics unchanged) with the event metrics recomputed under the alarm policy."""
    out,a,points=evaluate(d,threshold,cfg)
    if persistence==1 and not fresh_only:return out,a,points
    a=alarm_records_v11(d,threshold,cfg['alarm_cooldown'],cfg['horizon'],persistence,fresh_only);ev=a[a.event_evaluable]
    out.update({'alarm_PPV':float((a.alarms-a.false_alarms).sum()/a.alarms.sum()) if a.alarms.sum() else np.nan,
      'event_sensitivity':float(ev.detected.mean()) if len(ev) else np.nan,'missed_events':int((~ev.detected).sum()),
      'false_alarms_per_patient_day':float(a.false_alarms.sum()/a.at_risk_hours.sum()*24),'detected_event_denominator':int(ev.detected.sum()),
      'warning_hours_q25':float(ev.warning_hours.quantile(.25)) if ev.warning_hours.notna().any() else np.nan,
      'warning_hours_q75':float(ev.warning_hours.quantile(.75)) if ev.warning_hours.notna().any() else np.nan,
      'median_warning_hours_detected':float(ev.warning_hours.median()) if ev.warning_hours.notna().any() else np.nan})
    return out,a,points

def head_validation_auroc(model,store,cfg,device):
    """Per-organ head AUROC on a store's in-stay hours for the 6 h target (protocol 10b, rule 2)."""
    from sklearn.metrics import roc_auc_score
    if getattr(model,'heads',None) is None:return {}
    model.eval();bank_free=True;logit=[];tgt=[];okk=[]
    with torch.no_grad():
        for b in loader(store,cfg['batch']):
            b=batch_to(b,device);model(b['x'],b['mask'],b['hours'],None)
            t,ok=component_rise_targets(b['x'],b['mask'],model.sofa,model.sofa_obs)
            m=(b['mask'].unsqueeze(-1).unsqueeze(-1)>.5)&ok
            logit.append(model.last_head_logits.cpu().numpy());tgt.append(t.cpu().numpy());okk.append(m.cpu().numpy())
    L=np.concatenate(logit);T=np.concatenate(tgt);K=np.concatenate(okk);out={}
    for j,name in enumerate(model.head_names):
        sel=K[:,:,j,0];y=T[:,:,j,0][sel];p=L[:,:,j,0][sel]
        out['head_auroc_6h_'+name]=float(roc_auc_score(y,p)) if len(np.unique(y))==2 else np.nan
    return out

STAGE1B_GRID=[(op,pers,fresh) for op in ['absolute','quantile'] for pers in [1,2] for fresh in [False,True]]

# ----------------------------------------------------------------------------- tabular
def fit_tabular_v11(arm,train,val,cfg,seed,path):
    p=Path(path)/'estimator.pkl'
    if p.is_file():
        with p.open('rb') as f:return pickle.load(f)
    x,y=tabular_arrays(train,cfg['tabular_max_bytes'])
    if arm=='logistic':model=LogisticRegression(C=1.,solver='lbfgs',max_iter=1000,random_state=seed).fit(x,y)
    else:
        # Patient-grouped early stopping on the validation split (sklearn's internal split mixes hours of one patient).
        xv,yv=tabular_arrays(val,cfg['tabular_max_bytes']);step=cfg.get('tree_step',50);best=-1.;wait=0;best_iter=step;hist=[]
        model=HistGradientBoostingClassifier(max_iter=step,warm_start=True,early_stopping=False,learning_rate=.05,max_leaf_nodes=31,l2_regularization=1.,random_state=seed)
        for it in range(step,cfg.get('tree_max_iterations',1000)+1,step):
            model.set_params(max_iter=it);model.fit(x,y);ap=float(average_precision_score(yv,model.predict_proba(xv)[:,1]));hist.append({'iterations':it,'val_AUPRC':ap})
            if ap>best:best=ap;wait=0;best_iter=it
            else:wait+=1
            if wait>=cfg['patience']:break
        model=HistGradientBoostingClassifier(max_iter=best_iter,early_stopping=False,learning_rate=.05,max_leaf_nodes=31,l2_regularization=1.,random_state=seed).fit(x,y)
        atomic_json(Path(path)/'training_history.json',hist)
    tmp=p.with_suffix('.partial.pkl')
    with tmp.open('wb') as f:pickle.dump(model,f)
    os.replace(tmp,p);return model

# ----------------------------------------------------------------------------- extra evaluation
def antibiotic_lead(d,threshold,cfg):
    """Lead time of the first TIMELY alarm (within the 6 h window before onset) relative to the first
    antibiotic order around onset. Evaluation metadata only (the order time is never a predictor)."""
    if 'FirstAntibioticAroundOnset' not in d:return {}
    rows=[]
    for pid,g in d.groupby('Patient_ID',sort=False,observed=True):
        onset=g.OnsetHour.iloc[0];abx=g.FirstAntibioticAroundOnset.iloc[0]
        if not (pd.notna(onset) and pd.notna(abx)):continue
        g=g.sort_values('Hour');timely=g[(g.risk>=threshold)&(g.Hour<onset)&(g.Hour>=onset-cfg['horizon'])]
        rows.append({'detected':len(timely)>0,'lead_vs_antibiotic':(abx-timely.Hour.iloc[0]) if len(timely) else np.nan,'alarm_before_antibiotic':bool(len(timely) and timely.Hour.iloc[0]<abx)})
    if not rows:return {'antibiotic_lead_n':0}
    r=pd.DataFrame(rows);det=r[r.detected]
    return {'antibiotic_lead_n':int(len(r)),'antibiotic_lead_detected':int(len(det)),
            'median_lead_vs_first_antibiotic_hours':float(det.lead_vs_antibiotic.median()) if len(det) else np.nan,
            'fraction_alarm_before_first_antibiotic':float(r.alarm_before_antibiotic.mean())}

def ood_scores(store,z_cut=3.5):
    """Per-hour out-of-distribution score: fraction of OBSERVED measured channels with |z| > z_cut
    (model-agnostic; z from the training normaliser)."""
    ch=measured_channels(store.features);vi=[store.features.index(f) for f in ch];oi=[store.features.index(f+'_observed') for f in ch]
    rows=[]
    for i in range(len(store)):
        b=store[i];n=int(b['mask'].sum());x=b['x'][:n];obs=x[:,oi]>.5;ext=(np.abs(x[:,vi])>z_cut)&obs
        frac=np.where(obs.sum(1)>0,ext.sum(1)/np.maximum(obs.sum(1),1),0.)
        rows.append(pd.DataFrame({'Patient_ID':store.index.Patient_ID.iloc[i],'Hour':b['hours'][:n],'ood':frac.astype(np.float32)}))
    return pd.concat(rows,ignore_index=True)

def conformal_policy(cal,test,cal_ood,test_ood,cfg,alpha=.02):
    """Secondary alarm policy. (1) Abstain on out-of-distribution hours: ood above the (1-alpha)
    split-conformal quantile of calibration hours. (2) Alarm threshold = split-conformal quantile of
    calibration NON-SEPTIC eligible hours' risk at level 1-eps, eps = false-alarm budget per hour
    (budget/24), finite-sample corrected: a distribution-free bound on the hourly false-positive rate."""
    cal=cal.assign(Patient_ID=cal.Patient_ID.astype(str));test=test.assign(Patient_ID=test.Patient_ID.astype(str))
    c=cal.merge(cal_ood,on=['Patient_ID','Hour'],how='left');t=test.merge(test_ood,on=['Patient_ID','Hour'],how='left')
    s=np.sort(c.ood.fillna(0).to_numpy());n=len(s);k=min(n-1,int(np.ceil((n+1)*(1-alpha)))-1);tau=float(s[k]) if n else 1.
    neg=np.sort(c[c.y.eq(0)].risk.to_numpy());m=len(neg);eps=cfg['false_alarm_budget']/24.
    j=min(m-1,int(np.ceil((m+1)*(1-eps)))-1);thr=float(neg[j]) if m else 1.
    t=t.copy();abstain=t.ood.fillna(0)>tau;t.loc[abstain,'risk']=0.
    return t,{'conformal_threshold':thr,'conformal_ood_tau':tau,'conformal_abstained_fraction':float(abstain.mean())}

def dense_hours(store,required=('HR','MAP','Resp','O2Sat'),lookback=6,min_count=3):
    """Trajectory-rich hours: at least `min_count` fresh observations of EACH required channel in the
    trailing `lookback` hours (past/current information only)."""
    req=[f for f in required if f+'_observed' in store.features and f+'_age' in store.features]
    oi=[store.features.index(f+'_observed') for f in req];ai=[store.features.index(f+'_age') for f in req];rows=[]
    for i in range(len(store)):
        b=store[i];n=int(b['mask'].sum());x=b['x'][:n];fresh=((x[:,oi]>.5)&(x[:,ai]*AGE_SCALE<1)).astype(int)
        cs=np.vstack([np.zeros((1,len(req))),np.cumsum(fresh,0)]);counts=cs[np.arange(1,n+1)]-cs[np.maximum(0,np.arange(1,n+1)-lookback)]
        dense=(counts>=min_count).all(1) if req else np.ones(n,bool)
        rows.append(pd.DataFrame({'Patient_ID':store.index.Patient_ID.iloc[i],'Hour':b['hours'][:n],'dense':dense}))
    return pd.concat(rows,ignore_index=True)

def validation_panel(model_pred_val,cfg):
    """Validation-split utility and AUPRC used ONLY for the prespecified loss/shortlist rules."""
    out={'val_AUPRC':float(average_precision_score(model_pred_val.y,model_pred_val.logit)) if model_pred_val.y.nunique()==2 else np.nan}
    return out

# ----------------------------------------------------------------------------- driver
def run_fold_v11(index,features,target,cfg,root,transfer_index=None,corpus=None):
    """One target database: fit on its development split, evaluate internally; transfer to the other
    database's development patients; prespecified ensemble; conformal policy. cfg['arms'] lists the
    arms; cfg['loss'] is the primary loss; cfg['loss_comparison_arms'] x cfg['comparison_losses'] adds
    loss-comparator runs (saved as arm='<arm>@<loss>')."""
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    mf=partition(index,target,cfg)
    contract={'config':cfg,'features':features,'membership':mf[['Patient_ID','Group_ID','split']].to_dict('list'),
      'shards':{f:sha(f) for f in sorted(mf.file.unique())},'modules':{p.name:sha(p) for p in Path(__file__).parent.glob('v1*_*.py')}}
    key=signature(contract);marker=root/'contract.json'
    if marker.exists() and json.loads(marker.read_text())['sha256']!=key:raise ValueError('Run directory contract changed. Select a new RUN_KEY; old results are retained.')
    atomic_json(marker,{'sha256':key,'contract':contract});mf.to_parquet(root/'manifest.parquet',index=False)
    fit=SequenceStore(mf[mf.split.isin(['train','observer_fit'])],features,max_hours=cfg['max_hours']);norm=fit_normalizer(fit);np.savez(root/'normalization.npz',**norm);del fit
    stores={s:SequenceStore(mf[mf.split.eq(s)],features,norm,cfg['max_hours']) for s in ['train','observer_fit','val','calib','test']}
    atomic_json(root/'feature_schema.json',features)
    # Transfer: the OTHER database's development patients (never its protected holdout), scored with this target's calibration.
    other=None
    if transfer_index is not None:
        o=transfer_index[transfer_index.Dataset.ne(target)&~transfer_index.Group_ID.map(protected_group)]
        if len(o):other=SequenceStore(o.copy(),features,norm,cfg['max_hours'])
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu');results=[]
    cal_ood=ood_scores(stores['calib']);test_ood=ood_scores(stores['test']);dense=dense_hours(stores['test'])
    ssl_stores={}
    if corpus:
        for pop in ['site','pooled']:
            parts=[corpus[target]] if pop=='site' else [corpus[k] for k in sorted(corpus)]
            ssl_stores[pop]=[SequenceStore(ix,features,norm,cfg['max_hours']) for ix in parts if ix is not None and len(ix)]
    grid=[float(q) for q in (cfg.get('input_dropout_grid') or [0.])]
    jobs=[(a,cfg['loss'],q) for a in cfg['arms'] for q in grid]+[(a,l,0.) for a in cfg.get('loss_comparison_arms',[]) for l in cfg.get('comparison_losses',[]) if l!=cfg['loss']]
    stage1b=cfg.get('stage')=='1b'
    fresh_val=fresh_hours(stores['val']) if stage1b or cfg.get('fresh_only') else None
    fresh_test=fresh_hours(stores['test']) if cfg.get('fresh_only') else None
    for seed in cfg['seeds']:
        sd=root/f'seed_{seed}';sd.mkdir(exist_ok=True);seed_all(seed)
        need_bank=any(a in OSTA_FAMILY and a!='osta' for a,_,_ in jobs)
        bank=(train_observers(stores['observer_fit'],features,cfg,seed,sd/'observers.pt',device) if need_bank
              else ObserverBank(features,hidden=cfg['observer_hidden']).to(device).eval().requires_grad_(False))
        encoders={}
        for arm,loss,idrop in jobs:
            name=(arm if loss==cfg['loss'] else f'{arm}@{loss}')+(f'#id{idrop:g}' if idrop>0 else '');path=sd/name;path.mkdir(exist_ok=True);done=path/'completed.json'
            cfgj={**cfg,'input_dropout':idrop}
            if done.is_file():results+=json.loads(done.read_text());print('Reuse',target,name);continue
            seed_all(seed);tab=arm in TABULAR
            if tab:
                mk=lambda s:(SignatureStore(s.index,features,norm,cfg['max_hours']) if arm=='signature_boosted_tree' else s)
                model=fit_tabular_v11('boosted_tree' if arm=='signature_boosted_tree' else arm,mk(stores['train']),mk(stores['val']),cfg,seed,path)
                def pred(store,condition='normal',all_hours=False):return tabular_predict(model,mk(store),all_hours),{}
            else:
                enc=None
                if arm in SSL_ARMS:
                    pop=SSL_ARMS[arm]
                    if pop not in encoders:
                        if not ssl_stores.get(pop):raise ValueError(f'{arm}: no unlabelled corpus for population {pop}')
                        encoders[pop]=pretrain(ssl_stores[pop],features,cfg,seed,sd/f'ssl_encoder_{pop}.pt',device,pop)
                    enc=encoders[pop]
                model=build_model(arm,features,bank,cfg,enc)
                model=train_neural(arm,model,stores['train'],stores['val'],bank,cfgj,seed,path,device,loss)
                def pred(store,condition='normal',all_hours=False):return predict(model,bank,store,cfg['batch'],device,condition,all_hours)
            cal,_=pred(stores['calib']);params=calibrate(cal);cal=apply_calibration(cal,params);chosen,sweep=select_threshold(cal,cfg)
            chosen['alarm_fraction']=alarm_fraction(cal,chosen['threshold'])
            full_cal=pred(stores['calib'],all_hours=True)[0];full_test=pred(stores['test'],all_hours=True)[0]
            utility=utility_block(full_cal,full_test,params,cfg,seed,path)
            apply_calibration(full_test,params).to_parquet(path/'predictions_allhours.parquet',index=False)
            apply_calibration(full_cal,params).to_parquet(path/'predictions_allhours_calib.parquet',index=False)
            vp,_=pred(stores['val']);vcal=apply_calibration(vp,params);vfull=apply_calibration(pred(stores['val'],all_hours=True)[0],params)
            vthr,_=utility_threshold_sweep(apply_calibration(full_cal,params),np.unique(np.round(np.quantile(cal.risk,np.linspace(.5,.999,30)),6)))
            vutil=float(normalized_from(patient_utilities(vfull,vthr)))
            chosen['utility_alarm_fraction']=alarm_fraction(apply_calibration(full_cal,params),utility['utility_threshold'])
            heads_info={'task_weights':model.task_weights(),'head_names':model.head_names} if getattr(model,'heads',None) is not None else {}
            atomic_json(path/'calibration_and_threshold.json',{'platt':params,'chosen':chosen,'validation_utility':vutil,'validation_AUPRC':validation_panel(vp,cfg)['val_AUPRC'],'input_dropout':idrop,**heads_info})
            pd.DataFrame(sweep).to_csv(path/'threshold_sweep.csv',index=False)
            if stage1b:
                # ---- Protocol 10b: validation-only grid; the test split is scored, written and SEALED (not returned). ----
                vgrid=with_fresh(vcal,fresh_val);hauc=head_validation_auroc(model,stores['val'],cfg,device) if not tab else {}
                base_row={'target':target,'seed':seed,'arm':name,'base_arm':arm,'loss':loss if not tab else 'n/a','scope':'stage1b_validation_split',
                  'feature_count':len(features),'main_training_stays':len(stores['train']),'input_dropout':idrop,'validation_utility':vutil,
                  'validation_AUPRC':validation_panel(vp,cfg)['val_AUPRC'],'alarm_fraction':chosen['alarm_fraction'],'absolute_threshold':chosen['threshold'],
                  'task_weights':json.dumps(heads_info.get('task_weights')) if heads_info else '',**hauc}
                records=[]
                for op,pers,fresh in STAGE1B_GRID:
                    thr,used=operating_threshold(vgrid,chosen,{**cfg,'operating_point':op})
                    mv,_,_=evaluate_v11(vgrid,thr,cfg,pers,fresh)
                    records.append({**base_row,'condition':'validation_grid','operating_point':op,'operating_point_used':used,'persistence':pers,'fresh_only':fresh,'threshold_used':thr,**mv})
                d,_=pred(stores['test']);d=apply_calibration(d,params);m,alarms,points=evaluate(d,chosen['threshold'],cfg)
                m.update(clustered_ci(d,cfg['bootstrap'],seed));m.update(utility);m.update(antibiotic_lead(d,chosen['threshold'],cfg))
                sealed={'target':target,'seed':seed,'arm':name,'base_arm':arm,'loss':loss,'condition':'normal','scope':'stage1b_test_split_SEALED_until_stage2','input_dropout':idrop,**m}
                d.to_parquet(path/'predictions_normal.parquet',index=False);atomic_json(path/'test_rows_sealed.json',[sealed])
                results+=records;atomic_json(done,records);del model;gc.collect()
                if torch.cuda.is_available():torch.cuda.empty_cache()
                print('Completed (stage 1b, validation only)',target,name,flush=True);continue
            records=[]
            conditions=['normal']+(cfg['stress_conditions'] if (arm in OSTA_FAMILY and arm!='osta') else [])
            for condition in conditions:
                d,gates=pred(stores['test'],condition);d=apply_calibration(d,params);d=with_fresh(d,fresh_test)
                thr_t,op_used=operating_threshold(d,chosen,cfg)
                m,alarms,points=evaluate_v11(d,thr_t,cfg,cfg.get('persistence',1),bool(cfg.get('fresh_only',False)));m.update({'operating_point_used':op_used,'persistence':cfg.get('persistence',1),'fresh_only':bool(cfg.get('fresh_only',False))})
                if condition=='normal':
                    m.update(clustered_ci(d,cfg['bootstrap'],seed));m.update(hospital_ci(d,cfg['bootstrap'],seed));m.update(utility)
                    m.update(antibiotic_lead(d,thr_t,cfg))
                    m.update({'validation_utility':vutil,'validation_AUPRC':validation_panel(vp,cfg)['val_AUPRC'],'input_dropout':idrop,**heads_info})
                row={'target':target,'seed':seed,'arm':name,'base_arm':arm,'loss':loss if not tab else 'n/a','condition':condition,'scope':mf.evaluation_scope.iloc[0],
                  'feature_count':len(features),'main_training_stays':len(stores['train']),**m}
                records.append(row);d.to_parquet(path/f'predictions_{condition}.parquet',index=False)
                alarms.to_parquet(path/f'alarms_{condition}.parquet',index=False);points.to_csv(path/f'calibration_{condition}.csv',index=False)
                if condition=='normal':
                    # Conformal secondary policy and trajectory-rich subset on the same predictions.
                    tc,cinfo=conformal_policy(cal,d,cal_ood,test_ood,cfg,cfg.get('conformal_alpha',.02))
                    mc,_,_=evaluate(tc,cinfo['conformal_threshold'],cfg);mc.update(cinfo);mc.update(antibiotic_lead(tc,cinfo['conformal_threshold'],cfg))
                    records.append({**{k:v for k,v in row.items() if k not in m},'condition':'conformal',**mc})
                    dd=d.assign(Patient_ID=d.Patient_ID.astype(str)).merge(dense,on=['Patient_ID','Hour'],how='left');dd=dd[dd.dense.fillna(False).astype(bool)]
                    if dd.y.nunique()==2:
                        md,_,_=evaluate(dd,chosen['threshold'],cfg);records.append({**{k:v for k,v in row.items() if k not in m},'condition':'trajectory_rich',**md})
            if other is not None:
                dt,_=pred(other);dt=apply_calibration(dt,params);dt=with_fresh(dt,fresh_hours(other) if cfg.get('fresh_only') else None)
                thr_o,op_o=operating_threshold(dt,chosen,cfg);mt,at,pt_=evaluate_v11(dt,thr_o,cfg,cfg.get('persistence',1),bool(cfg.get('fresh_only',False)));mt.update({'operating_point_used':op_o})
                mt.update(clustered_ci(dt,cfg['bootstrap'],seed));mt.update(hospital_ci(dt,cfg['bootstrap'],seed))
                mt.update(utility_block(full_cal,pred(other,all_hours=True)[0],params,cfg,seed,_mk(path/'transfer')))
                mt.update(antibiotic_lead(dt,thr_o,cfg))
                ot=other.index.Dataset.iloc[0]
                records.append({'target':f'{ot}_from_{target}','seed':seed,'arm':name,'base_arm':arm,'loss':loss if not tab else 'n/a','condition':'normal',
                    'scope':'development_transfer_other_database_dev_patients','feature_count':len(features),'main_training_stays':len(stores['train']),**mt})
                dt.to_parquet(path/'transfer_predictions.parquet',index=False)
            results+=records;atomic_json(done,records);del model;gc.collect()
            if torch.cuda.is_available():torch.cuda.empty_cache()
            print('Completed',target,name,flush=True)
        # Prespecified mean ensemble of calibrated risks (no learned weights).
        members=[a for a in ENSEMBLE_MEMBERS if (sd/a/'predictions_normal.parquet').is_file()]
        if len(members)>=2 and not (sd/'ensemble_mean'/'completed.json').is_file():
            path=sd/'ensemble_mean';path.mkdir(exist_ok=True)
            def mean_of(fname):
                frames=[pd.read_parquet(sd/a/fname) for a in members];base=frames[0][[c for c in frames[0].columns if c!='risk']].copy()
                base['risk']=np.mean([f.risk.to_numpy() for f in frames],axis=0).astype(np.float32);return base
            calm=mean_of('predictions_allhours_calib.parquet');calm_e=calm[calm.Eligible.eq(1)];chosen,sweep=select_threshold(calm_e,cfg)
            testm=mean_of('predictions_allhours.parquet');teste=testm[testm.Eligible.eq(1)]
            ident={'intercept':0.,'slope':1.}
            def logitify(f):
                f=f.copy();r=np.clip(f.risk.to_numpy(float),1e-6,1-1e-6);f['logit']=np.log(r/(1-r));return f
            utility=utility_block(logitify(calm),logitify(testm),ident,cfg,seed,path)
            m,alarms,points=evaluate(teste,chosen['threshold'],cfg);m.update(clustered_ci(teste,cfg['bootstrap'],seed));m.update(hospital_ci(teste,cfg['bootstrap'],seed));m.update(utility)
            m.update(antibiotic_lead(teste,chosen['threshold'],cfg))
            row={'target':target,'seed':seed,'arm':'ensemble_mean','base_arm':'ensemble_mean','loss':cfg['loss'],'condition':'normal','scope':mf.evaluation_scope.iloc[0],
                 'feature_count':len(features),'main_training_stays':len(stores['train']),'members':'+'.join(members),**m}
            teste.to_parquet(path/'predictions_normal.parquet',index=False);atomic_json(path/'completed.json',[row]);results.append(row)
        # Paired comparisons against OSTA on identical hours.
        comparisons=[];p=sd/'osta'/'predictions_normal.parquet'
        if p.exists():
            for q_ in sorted(sd.glob('*/predictions_normal.parquet')):
                if q_.parent.name=='osta':continue
                comparisons.append({'comparison':q_.parent.name+' minus osta',**paired_difference(pd.read_parquet(q_),pd.read_parquet(p),cfg['bootstrap'],seed)})
        pd.DataFrame(comparisons).to_csv(sd/'paired_comparisons.csv',index=False)
    out=pd.DataFrame(results);out.to_csv(root/'results.csv',index=False);return out

def _mk(p):
    p=Path(p);p.mkdir(parents=True,exist_ok=True);return p
```

## Module v11_tests.py: engineering checks

`dev/work/mods/v11_tests.py` (135 lines)

```python
"""V11 engineering checks (nonclinical): losses, survival head, signatures, conformal policy,
lead-time metric, label-free pretraining, causality of every new arm, prophylaxis rule, corpus
selection, parallel shard building. Appended to v10_tests.run_checks."""
from pathlib import Path
import tempfile,json,contextlib,io
import numpy as np
import pandas as pd
import torch

def run_v11_checks():
    from v9_train import AGE_SCALE,SequenceStore,fit_normalizer
    from v11_models import make_model,Pretrainer,measured_channels,HAZARD_EDGES
    from v11_train import (targets_and_weights,hazard_nll,SignatureStore,ssl_targets,ssl_loss,antibiotic_lead,conformal_policy,
                           dense_hours,ood_scores,utility_gap_weight,component_rise_targets,heads_loss,uncertainty_weighted,feature_groups,
                           input_dropout,fresh_hours,with_fresh,alarm_fraction,quantile_threshold,operating_threshold,alarm_records_v11,evaluate_v11)
    from v11_data import SupplementExtractor,unlabelled_stays
    from v9_data import build_shards,build_sequence,normalize_events,RawExtractor
    from v10_protocol import protected_group
    checks={}
    def check(name,ok):
        if not ok:raise AssertionError('v11:'+name)
        checks[name]='pass'
    # ---- losses ----
    hours=torch.arange(1,25).float().view(1,-1);y=torch.zeros(1,24);y[0,13:19]=1   # onset 20: positives at 14..19
    elig=torch.ones(1,24);elig[0,19:]=0;mask=torch.ones(1,24)
    b={'y':y,'eligible':elig,'mask':mask,'hours':hours};on=torch.tensor([20.])
    t,w=targets_and_weights(b,on,'utility_weighted_bce')
    check('utility_weights_post_onset_positives',bool(t[0,19:23].eq(1).all()) and bool(w[0,19:23].gt(0).all()) and bool(w[0,23]==0))
    pos=t[0]>.5;check('utility_weights_mean_one_and_increasing',abs(float(w[0][pos].mean())-1)<1e-5 and bool((torch.diff(w[0][pos])>0).all()))
    check('utility_gap_shape',abs(float(utility_gap_weight(torch.tensor(-6.)))-1.)<1e-6 and abs(float(utility_gap_weight(torch.tensor(3.)))-2.)<1e-6)
    t2,w2=targets_and_weights(b,on,'tls');check('tls_soft_ramp',bool(t2[0,13:19].eq(1).all()) and 0<float(t2[0,12])<.5 and float(t2[0,0])==0 and bool(w2.eq(elig).all()))
    t3,w3=targets_and_weights(b,torch.tensor([float('nan')]),'utility_weighted_bce');check('nonseptic_unchanged',bool(t3.eq(y).all()) and bool(w3.eq(elig).all()))
    hz=torch.full((1,24,len(HAZARD_EDGES)-1),.1);nll=hazard_nll(hz,b,on);hz2=hz.clone();hz2[0,:,2]=.9
    check('hazard_nll_finite_and_sensitive',torch.isfinite(nll) and float(hazard_nll(hz2,b,on))!=float(nll))
    # ---- signatures: straight line has zero Levy area; increments exact ----
    P=np.stack([np.arange(5.),2*np.arange(5.)],1);l1,l2=SignatureStore.signatures(P)
    check('signature_increments',np.allclose(l1,[4.,8.]));S=l2.reshape(2,2);check('signature_levy_area_zero_for_line',abs(S[0,1]-S[1,0])<1e-9 and abs(S[0,0]-8.)<1e-9)
    # ---- fixture-based checks ----
    from v10_fixture import make_fixture
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);INDEX,FEATURES=make_fixture(td/'fx',n=24);mi=INDEX[INDEX.Dataset.eq('miiv')].copy()
        norm=fit_normalizer(SequenceStore(mi,FEATURES,max_hours=24));store=SequenceStore(mi,FEATURES,norm,24)
        j=FEATURES.index('HR_age');check('age_channel_in_days',abs(norm['std'][j]-AGE_SCALE)<1e-9 and norm['mean'][j]==0)
        sig=SignatureStore(mi,FEATURES,norm,24);it=sig[0];check('signature_store_width',it['x'].shape[1]==len(sig.features)==len(FEATURES)+2*(8+64))
        dh=dense_hours(store);check('dense_hours_causal_flag',set(dh.columns)=={'Patient_ID','Hour','dense'} and dh.dense.dtype==bool)
        oo=ood_scores(store);check('ood_scores_in_unit_interval',oo.ood.between(0,1).all())
        # pretraining targets use no labels: compare on a batch with y shuffled
        with contextlib.redirect_stdout(io.StringIO()):pt=Pretrainer(FEATURES,depth=2)
        it0=store[0];x=torch.tensor(it0['x']).unsqueeze(0);m=torch.tensor(it0['mask']).unsqueeze(0)
        tg=ssl_targets(x,m,pt);tot,parts=ssl_loss(pt(x),tg)
        check('ssl_targets_label_free',set(tg)>={'forecast','measured'} and torch.is_tensor(tot) and torch.isfinite(tot))
        # causality of every v11 arm on real feature layout
        cfg={'small_model':True,'dropout':0.,'cnn_depth':2,'event_lookback':24}
        xb=torch.stack([torch.tensor(store[i]['x']) for i in range(2)]);mb=torch.stack([torch.tensor(store[i]['mask']) for i in range(2)]);hb=torch.stack([torch.tensor(store[i]['hours']) for i in range(2)])
        for arm in ['flat_osta','flat_osta_heads','grud','tcn','cnn_osta','ssl_cnn_flat','event_osta','hazard_ssl_cnn_osta']:
            with contextlib.redirect_stdout(io.StringIO()):model=make_model(arm,FEATURES,cfg).eval()
            with torch.no_grad():
                a=model(xb,mb,hb);x2=xb.clone();x2[:,10:]=torch.randn_like(x2[:,10:]);bq=model(x2,mb,hb)
            check(f'{arm}_future_invariance',float((a[:,:10]-bq[:,:10]).abs().max())<1e-5)
        # ---- stage 1b (protocol 10b): organ heads, uncertainty weighting, input dropout, fresh hours ----
        with contextlib.redirect_stdout(io.StringIO()):fh=make_model('flat_osta_heads',FEATURES,cfg).train()
        lg=fh(xb,mb,hb);check('heads_shape_and_names',fh.last_head_logits.shape==(2,24,fh.n_heads,3) and fh.head_names[-1]=='any_organ' and len(fh.sofa)>=1)
        tgt,ok=component_rise_targets(xb,mb,fh.sofa,fh.sofa_obs)
        check('head_targets_shape_defined_only_when_known',tgt.shape==ok.shape==(2,24,fh.n_heads,3) and bool((tgt[~ok]==0).all()) and bool(ok[:,-1].eq(False).all()))
        # a hand-built component series: rises at hour 3 only -> rise target true at hours 1-2 within 6 h, false at hour 3 (no later rise)
        xs=torch.zeros(1,6,2);xs[0,:,0]=torch.tensor([1.,1.,2.,2.,2.,2.]);xs[0,:,1]=1.;ms=torch.ones(1,6)
        t1,o1=component_rise_targets(xs,ms,[0],[1])
        check('head_target_rise_logic',bool(t1[0,0,0,0]==1) and bool(t1[0,1,0,0]==1) and bool(t1[0,2,0,0]==0) and bool(o1[0,4,0,0]) and not bool(o1[0,5,0,0]) and bool(t1[0,0,1,0]==1))
        hl=heads_loss(fh,{'x':xb,'mask':mb});tot=uncertainty_weighted([lg.mean(),hl],fh.log_var);tot.backward()
        check('uncertainty_weighting_finite_and_learnable',torch.isfinite(tot) and fh.log_var.grad is not None and bool(torch.isfinite(fh.log_var.grad).all()) and len(fh.task_weights())==1+fh.n_heads)
        g,ng=feature_groups(FEATURES);j=FEATURES.index('HR');check('feature_groups_triples',int(g[j])==int(g[FEATURES.index('HR_observed')])==int(g[FEATURES.index('HR_age')]) and ng<len(FEATURES))
        torch.manual_seed(0);xd=input_dropout(xb,g,ng,.5);hidden=(xd[:,:,j]==0)&(xb[:,:,j]!=0)
        check('input_dropout_hides_triples_jointly',bool(hidden.any()) and bool((xd[:,:,FEATURES.index('HR_observed')][hidden]==0).all()) and bool((xd[:,:,FEATURES.index('HR_age')][hidden]==0).all()) and bool(input_dropout(xb,g,ng,0.).equal(xb)))
        frh=fresh_hours(store);check('fresh_hours_flag',set(frh.columns)=={'Patient_ID','Hour','fresh'} and frh.fresh.dtype==bool and frh.fresh.any())
        with contextlib.redirect_stdout(io.StringIO()):hm=make_model('hazard_ssl_cnn_osta',FEATURES,cfg).eval()
        with torch.no_grad():hm(xb,mb,hb)
        check('hazard_probabilities_bounded',bool((hm.last_hazards>0).all()) and bool((hm.last_hazards<1).all()))
        # conformal policy and antibiotic lead on synthetic predictions
        pred=pd.DataFrame({'Patient_ID':['a']*10+['b']*10,'Group_ID':['a']*10+['b']*10,'Hospital_ID':['h']*20,'Hour':list(range(1,11))*2,
            'y':[0]*4+[1]*6+[0]*10,'risk':np.r_[np.linspace(.1,.9,10),np.linspace(.05,.3,10)],'OnsetHour':[11.]*10+[np.nan]*10,
            'FirstAntibioticAroundOnset':[9.]*10+[np.nan]*10})
        cfgp={'false_alarm_budget':.5,'horizon':6,'alarm_cooldown':6}
        lead=antibiotic_lead(pred,.5,cfgp);check('antibiotic_lead_metric',lead['antibiotic_lead_n']==1 and lead['median_lead_vs_first_antibiotic_hours']==3. and lead['fraction_alarm_before_first_antibiotic']==1.)
        ood=pd.DataFrame({'Patient_ID':pred.Patient_ID,'Hour':pred.Hour,'ood':np.r_[np.zeros(19),[1.]]})
        tc,info=conformal_policy(pred,pred,ood,ood,cfgp,alpha=.1)
        check('conformal_abstains_outlier_and_bounds_threshold',info['conformal_abstained_fraction']>0 and tc.risk.iloc[-1]==0 and 0<info['conformal_threshold']<=1)
        # ---- stage 1b alarm policy and quantile operating point on synthetic predictions ----
        pp=pd.DataFrame({'Patient_ID':['a']*8,'Group_ID':['a']*8,'Hospital_ID':['h']*8,'Hour':list(range(1,9)),'y':[0]*8,
            'risk':[.1,.6,.1,.6,.6,.6,.1,.6],'OnsetHour':[np.nan]*8,'fresh':[True,True,True,False,True,True,True,True]})
        a1=alarm_records_v11(pp,.5,cooldown=1,horizon=6,persistence=1);a2=alarm_records_v11(pp,.5,cooldown=1,horizon=6,persistence=2)
        a3=alarm_records_v11(pp,.5,cooldown=1,horizon=6,persistence=1,fresh_only=True);a4=alarm_records_v11(pp,.5,cooldown=1,horizon=6,persistence=2,fresh_only=True)
        check('persistence_rule',int(a1.alarms[0])==5 and int(a2.alarms[0])==2)          # p=2: hours 5 and 6 only (hour 4 starts the run)
        check('fresh_only_rule',int(a3.alarms[0])==4 and int(a4.alarms[0])==2 and int(a1.at_risk_hours[0])==8)
        pa=pred.copy();check('evaluate_v11_identity_at_default_policy',evaluate_v11(pa,.5,cfgp)[0]['event_sensitivity']==evaluate_v11(pa,.5,cfgp,1,False)[0]['event_sensitivity'])
        big=pd.DataFrame({'risk':np.linspace(0,1,20000)});fr=alarm_fraction(big,.9);qt=quantile_threshold(big,fr,min_hours=10000)
        check('quantile_threshold_reproduces_alarm_fraction',abs(alarm_fraction(big,qt)-fr)<2e-4 and quantile_threshold(big.head(100),fr)is None and quantile_threshold(big,0.)>1)
        thr_abs,used_abs=operating_threshold(big,{'threshold':.9,'alarm_fraction':fr},{'operating_point':'absolute'})
        thr_q,used_q=operating_threshold(big,{'threshold':.9,'alarm_fraction':fr},{'operating_point':'quantile'})
        thr_f,used_f=operating_threshold(big.head(50),{'threshold':.9,'alarm_fraction':fr},{'operating_point':'quantile'})
        check('operating_point_selection_and_fallback',used_abs=='absolute' and thr_abs==.9 and used_q=='quantile' and abs(thr_q-.9)<1e-3 and used_f=='absolute')
        wf=with_fresh(pp.drop(columns='fresh'),pp[['Patient_ID','Hour','fresh']]);check('with_fresh_merge',wf.fresh.tolist()==pp.fresh.tolist())
        # parallel == sequential shard building (same records, index, schema)
        from v9_data import build_shards as bs
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);root=td/'miiv';(root/'icu').mkdir(parents=True);(root/'hosp').mkdir()
        T=lambda h:str(pd.Timestamp('2100-01-01')+pd.Timedelta(hours=h));ids=[1,2,3,4,5,6]
        pd.DataFrame({'stay_id':ids,'hadm_id':[i+10 for i in ids],'subject_id':[i+100 for i in ids],'intime':[T(0)]*6,'outtime':[T(30)]*6}).to_csv(root/'icu/icustays.csv',index=False)
        pd.DataFrame({'subject_id':[i+100 for i in ids],'anchor_age':[50+i for i in ids],'gender':['M','F']*3}).to_csv(root/'hosp/patients.csv',index=False)
        rows=[{'stay_id':i,'itemid':220045,'charttime':T(h),'storetime':T(h),'valuenum':80+i+h%3,'value':'x','valueuom':'bpm'} for i in ids for h in range(0,12)]
        pd.DataFrame(rows).to_csv(root/'icu/chartevents.csv',index=False)
        pd.DataFrame({'stay_id':ids,'itemid':[226559]*6,'charttime':[T(1)]*6,'storetime':[T(1)]*6,'value':[50.]*6,'valueuom':['mL']*6}).to_csv(root/'icu/outputevents.csv',index=False)
        sel,static=unlabelled_stays('miiv',root,[1],protected_group,max_hours=12)
        check('unlabelled_corpus_excludes_cohort_and_protected',1 not in set(sel.stay_id) and len(sel)>=1 and not sel.stay_id.map(lambda i:protected_group('miiv|'+str(i+100))).any())
        with contextlib.redirect_stdout(io.StringIO()):
            RawExtractor('miiv',root,sel,td/'st',12).extract()
            ix1,s1=bs('miiv',td/'st',None,td/'seq',12,6,batch=2,static=static,workers=1)
            ix2,s2=bs('miiv',td/'st',None,td/'par',12,6,batch=2,static=static,workers=2)
        a=pd.read_parquet(ix1.file.iloc[0]);bq=pd.read_parquet(ix2.file.iloc[0])
        check('parallel_shards_identical',s1==s2 and len(ix1)==len(ix2) and a.drop(columns='Patient_ID').equals(bq.drop(columns='Patient_ID')) and ix1.FirstAntibioticAroundOnset.isna().all())
        # supplementary stage -> prophylaxis features in the sequence; antibiotic metadata in the index
        sel2=pd.DataFrame({'stay_id':[1,2],'first_hour':[0.,0.],'followup_end':[24.,24.],'first_positive':[np.nan,np.nan],'OnsetHour':[np.nan,8.],'Outcome':[0,1]})
        pd.DataFrame({'subject_id':[101,102],'hadm_id':[11,12],'admittime':[T(-30)]*2,'dischtime':[T(60)]*2,'admission_type':['SURGICAL SAME DAY ADMISSION','EW EMER.'],'admission_location':['PHYSICIAN REFERRAL','EMERGENCY ROOM']}).to_csv(root/'hosp/admissions.csv',index=False)
        pd.DataFrame({'subject_id':[101],'hadm_id':[11],'transfer_id':[1],'eventtype':['transfer'],'careunit':['PACU'],'intime':[T(-1)]}).to_csv(root/'hosp/transfers.csv',index=False)
        pd.DataFrame({'subject_id':[101,101,102],'hadm_id':[11,11,12],'drug':['Cefazolin','Sulfamethoxazole-Trimethoprim','Piperacillin-Tazobactam'],'starttime':[T(-3),T(5),T(7)],'stoptime':[T(-2),T(100),T(120)],
            'doses_per_24_hrs':[1,1,3],'dose_val_rx':[2,1,4.5],'route':['IV','PO','IV']}).to_csv(root/'hosp/prescriptions.csv',index=False)
        pd.DataFrame({'subject_id':[102],'hadm_id':[12],'charttime':[T(6)],'spec_type_desc':['BLOOD CULTURE'],'org_name':[None]}).to_csv(root/'hosp/microbiologyevents.csv',index=False)
        with contextlib.redirect_stdout(io.StringIO()):
            SupplementExtractor('miiv',root,sel2,td/'supp',12).supplement()
            RawExtractor('miiv',root,sel2,td/'st2',12).extract()
            ix3,_=bs('miiv',td/'st2',None,td/'seq3',12,6,batch=4,static=pd.DataFrame({'stay_id':[1,2],'Age':[60.,70.],'Gender':[1.,0.]}),supplement=td/'supp',workers=1)
        f=pd.read_parquet(ix3.file.iloc[0]);s1_=f[f.Patient_ID.eq('miiv|1')];s2_=f[f.Patient_ID.eq('miiv|2')]
        check('prophylaxis_features_causal',s1_.Prophylaxis_Surgical_24h.iloc[0]==1 and s1_.Prophylaxis_Medical.iloc[:4].eq(0).all() and s1_.Prophylaxis_Medical.iloc[5]==1 and s2_.Prophylaxis_Surgical_24h.eq(0).all())
        check('first_antibiotic_metadata_for_septic_stay',float(ix3.set_index('stay_id').FirstAntibioticAroundOnset[2])==7. and np.isnan(ix3.set_index('stay_id').FirstAntibioticAroundOnset[1]))
    print('V11 engineering checks:',len(checks),'PASS')
    return checks
```

## Module v11_data.py: supplementary extraction, unlabelled stays

`dev/work/mods/v11_data.py` (198 lines)

```python
"""V11 data additions that leave the main raw stage (and its key) untouched.

1. SupplementExtractor: prophylactic-antibiotic events (MIMIC-IV) and antibiotic start times
   (both databases, evaluation metadata only), written to a separate supplementary stage.
2. unlabelled_stays: the self-supervised corpus (stays never labelled by YAIB, protected-hash
   patients excluded) with age/sex from the raw tables; no R label extraction is needed.

Antibiotic rule (user decision, 19 Oct 2026; ASHP/IDSA/SIS/SHEA 2013, CDC 2017, Seymour 2016):
- SURGICAL prophylaxis = prophylaxis agent AND first dose within the perioperative window of a
  surgical timestamp (PACU/OR transfer or ICU admission from the OR) AND the order lasts <= 24 h
  (48 h for cardiac surgery) AND no culture in the Seymour window [-72 h, +24 h] around the dose
  AND no other antibiotic started within 72 h after it.
- MEDICAL prophylaxis = agent/dose pattern typical of PJP, SBP, neutropenia or transplant
  prophylaxis AND no culture in the Seymour window.
- Everything else (empirical, culture-directed) is excluded: it defines the Sepsis-3 label.
- eICU: no prophylaxis features (its label is antibiotic-only).
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import duckdb
import os
from v9_data import RawExtractor,MED_CONTEXT,q,table,csv_scan

def atomic_json_path(path,data):
    path=Path(path);tmp=path.with_suffix('.partial.json');tmp.write_text(json.dumps(data,indent=2,default=str));os.replace(tmp,path)

SURGICAL_AGENTS=r'cefazolin|ancef|cefuroxime|cefoxitin|cefotetan|ampicillin-sulbactam|unasyn|clindamycin|vancomycin|gentamicin|metronidazole|ertapenem|neomycin|erythromycin'
MEDICAL_AGENTS={
 'pjp':r'sulfamethoxazole|trimethoprim|bactrim|dapsone|atovaquone|pentamidine',
 'antifungal':r'fluconazole|posaconazole|micafungin|caspofungin',
 'antiviral':r'acyclovir|valacyclovir|valganciclovir|ganciclovir',
 'sbp_neutropenia':r'norfloxacin|ciprofloxacin|levofloxacin|penicillin v'}
TOPICAL=r'cream|ointment|topical|ophth|otic|eye drop|lotion|enema|suppository|nasal|vaginal|irrig|flush|lock'
CARDIAC_SERVICE=r'csurg|cardiac surg|cardiothoracic|vsurg'
SURGICAL_UNIT=r'pacu|operating|recovery|procedure'

class SupplementExtractor(RawExtractor):
    """Subclass so RawExtractor's source (and therefore RAW_STAGE_KEY) is unchanged."""
    def supplement(self):
        self.antibiotic_starts()
        if self.ds=='miiv':self.prophylaxis()
        self.con.close()
        atomic_json_path(self.out/'supplement_complete.json',{'stays':int(len(self.meta)),'dataset':self.ds})

    def _antibiotics(self):
        """Systemic antibiotic order starts (hour, agent, stop hour, doses/day, route) per stay."""
        if self.ds=='miiv':
            rx=self.csv('hosp/prescriptions')
            if not rx:return None
            eh=self.hour('x.starttime');stop=self.hour('x.stoptime') if 'stoptime' in self.cols(rx) else 'NULL'
            dpd=f"TRY_CAST({self.col(rx,'doses_per_24_hrs')} AS DOUBLE)";dose=f"TRY_CAST({self.col(rx,'dose_val_rx')} AS DOUBLE)"
            route=f"lower(coalesce(CAST({self.col(rx,'route')} AS VARCHAR),''))"
            return self.con.execute(f'''SELECT s.stay_id,{eh} AS "event_hour",{stop} AS "stop_hour",lower(coalesce(x.drug,'')) AS "drug",
              {dpd} AS "doses_per_day",{dose} AS "dose",{route} AS "route"
              FROM {rx} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
              WHERE regexp_matches(lower(coalesce(x.drug,'')),{q(MED_CONTEXT['antimicrobial']+'|'+SURGICAL_AGENTS+'|'+'|'.join(MEDICAL_AGENTS.values()))})
              AND NOT regexp_matches(lower(coalesce(x.drug,''))||' '||{route},{q(TOPICAL)})''').df()
        parts=[]
        md=self.csv('medication')
        if md:
            start='TRY_CAST(x.drugstartoffset AS DOUBLE)/60';stop=f"TRY_CAST({self.col(md,'drugstopoffset')} AS DOUBLE)/60"
            parts.append(self.con.execute(f'''SELECT s.stay_id,{start} AS "event_hour",{stop} AS "stop_hour",lower(coalesce(x.drugname,'')) AS "drug",
              NULL AS "doses_per_day",NULL AS "dose",lower(coalesce(CAST({self.col(md,'routeadmin')} AS VARCHAR),'')) AS "route"
              FROM {md} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
              WHERE lower(coalesce({self.col(md,'drugordercancelled')},''))<>'yes'
              AND regexp_matches(lower(coalesce(x.drugname,'')),{q(MED_CONTEXT['antimicrobial'])})
              AND NOT regexp_matches(lower(coalesce(x.drugname,'')),{q(TOPICAL)})''').df())
        inf=self.csv('infusionDrug')
        if inf:
            parts.append(self.con.execute(f'''SELECT s.stay_id,TRY_CAST(x.infusionoffset AS DOUBLE)/60 AS "event_hour",NULL AS "stop_hour",
              lower(coalesce(x.drugname,'')) AS "drug",NULL AS "doses_per_day",NULL AS "dose",'iv' AS "route"
              FROM {inf} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
              WHERE regexp_matches(lower(coalesce(x.drugname,'')),{q(MED_CONTEXT['antimicrobial'])})''').df())
        return pd.concat(parts,ignore_index=True) if parts else None

    def antibiotic_starts(self):
        a=self._antibiotics()
        if a is None:a=pd.DataFrame(columns=['stay_id','event_hour'])
        a=a[np.isfinite(a.event_hour.astype(float))&(a.event_hour.astype(float)>=-24)&(a.event_hour.astype(float)<=self.max_hours+24)]
        a[['stay_id','event_hour']].astype({'stay_id':'int64','event_hour':'float64'}).to_parquet(self.out/'antibiotic_starts.parquet',index=False)
        self._abx=a

    def _cultures(self):
        mb=self.csv('hosp/microbiologyevents')
        if not mb:return pd.DataFrame(columns=['stay_id','hour'])
        return self.con.execute(f'''SELECT s.stay_id,{self.hour('x.charttime')} AS "hour" FROM {mb} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
          WHERE x.charttime IS NOT NULL''').df()

    def _surgical_times(self):
        """Hours (relative to ICU intime) of surgical timestamps: PACU/OR/recovery transfers, surgical
        service transfers, and the ICU admission itself when the patient came from the OR/PACU."""
        rows=[]
        tf=self.csv('hosp/transfers')
        if tf and {'careunit','intime','hadm_id'}<=self.cols(tf):
            rows.append(self.con.execute(f'''SELECT s.stay_id,{self.hour('x.intime')} AS "hour",'transfer' AS "kind"
              FROM {tf} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
              WHERE regexp_matches(lower(coalesce(x.careunit,'')),{q(SURGICAL_UNIT)})''').df())
        sv=self.csv('hosp/services')
        if sv and {'curr_service','transfertime','hadm_id'}<=self.cols(sv):
            rows.append(self.con.execute(f'''SELECT s.stay_id,{self.hour('x.transfertime')} AS "hour",'service' AS "kind"
              FROM {sv} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
              WHERE regexp_matches(lower(coalesce(x.curr_service,'')),'surg|ortho|\\bgu\\b|gyn|\\bent\\b|neuro|trauma|cardiac')''').df())
        adm=self.csv('hosp/admissions')
        if adm and 'admission_type' in self.cols(adm):
            rows.append(self.con.execute(f'''SELECT s.stay_id,0.0 AS "hour",'surgical_admission' AS "kind"
              FROM {adm} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
              WHERE lower(coalesce(x.admission_type,'')) LIKE '%surgical%' ''').df())
        t=pd.concat(rows,ignore_index=True) if rows else pd.DataFrame(columns=['stay_id','hour','kind'])
        return t[np.isfinite(t.hour.astype(float))]

    def _cardiac(self):
        sv=self.csv('hosp/services')
        if not sv or 'curr_service' not in self.cols(sv):return set()
        d=self.con.execute(f'''SELECT DISTINCT s.stay_id FROM {sv} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
          WHERE regexp_matches(lower(coalesce(x.curr_service,'')),{q(CARDIAC_SERVICE)})''').df()
        return set(d.stay_id.astype(int))

    def prophylaxis(self):
        a=getattr(self,'_abx',None)
        if a is None or a.empty:
            pd.DataFrame(columns=['stay_id','event_hour','available_hour','feature','value','unit','kind','end_hour']).to_parquet(self.out/'prophylaxis.parquet',index=False);return
        a=a.copy();a['event_hour']=a.event_hour.astype(float);a['stop_hour']=pd.to_numeric(a.stop_hour,errors='coerce')
        cultures=self._cultures();surg=self._surgical_times();cardiac=self._cardiac()
        cult={sid:g.hour.to_numpy(float) for sid,g in cultures.groupby('stay_id')}
        st={sid:g.hour.to_numpy(float) for sid,g in surg.groupby('stay_id')}
        starts={sid:g.event_hour.to_numpy(float) for sid,g in a.groupby('stay_id')}
        drugs={sid:g.drug.to_numpy() for sid,g in a.groupby('stay_id')}
        out=[]
        for r in a.itertuples(index=False):
            sid=int(r.stay_id);h=float(r.event_hour)
            # Seymour pairing: a culture in [-72 h, +24 h] around the dose makes it label-relevant -> never prophylaxis.
            c=cult.get(sid,np.empty(0))
            if ((c>=h-72)&(c<=h+24)).any():continue
            duration=(r.stop_hour-h) if np.isfinite(r.stop_hour) else np.nan
            others=starts.get(sid,np.empty(0));od=drugs.get(sid,np.empty(0))
            # Escalation = a NON-prophylaxis agent started within 72 h after this dose (a combination
            # prophylaxis partner or a chronic prophylaxis agent is not an escalation).
            proph=pd.Series(od).str.contains(SURGICAL_AGENTS+'|'+'|'.join(MEDICAL_AGENTS.values()),regex=True).to_numpy() if len(od) else np.zeros(0,bool)
            escalation=bool(((others>h)&(others<=h+72)&~proph).any())
            surgical=False
            if pd.Series([r.drug]).str.contains(SURGICAL_AGENTS,regex=True).iloc[0]:
                t=st.get(sid,np.empty(0))
                peri=((t>=h-1)&(t<=h+8)).any()  # dose 0-8 h before the end-of-surgery/transfer timestamp, or within 1 h after
                limit=48. if sid in cardiac else 24.
                short=(np.isfinite(duration) and duration<=limit) or (r.doses_per_day is not None and np.isfinite(r.doses_per_day) and r.doses_per_day<=1 and not np.isfinite(duration))
                surgical=bool(peri and short and not escalation)
            medical=False
            if not surgical:
                drug=str(r.drug);dpd=float(r.doses_per_day) if r.doses_per_day is not None and np.isfinite(r.doses_per_day) else np.nan;dose=float(r.dose) if r.dose is not None and np.isfinite(r.dose) else np.nan
                if pd.Series([drug]).str.contains(MEDICAL_AGENTS['pjp'],regex=True).iloc[0]:
                    medical=('pentamidine' in drug or 'dapsone' in drug or 'atovaquone' in drug or (np.isfinite(dpd) and dpd<=1))
                elif pd.Series([drug]).str.contains(MEDICAL_AGENTS['antifungal'],regex=True).iloc[0]:
                    medical=('fluconazole' not in drug) or (np.isfinite(dpd) and dpd<=1 and (not np.isfinite(dose) or dose<=400))
                elif pd.Series([drug]).str.contains(MEDICAL_AGENTS['antiviral'],regex=True).iloc[0]:
                    medical=np.isfinite(dpd) and dpd<=2
                elif pd.Series([drug]).str.contains(MEDICAL_AGENTS['sbp_neutropenia'],regex=True).iloc[0]:
                    medical=np.isfinite(dpd) and dpd<=1
                medical=bool(medical and not escalation)
            if surgical:out.append((sid,h,h,'Prophylaxis_Surgical',1.,'','exposure',np.nan))
            if medical:out.append((sid,h,h,'Prophylaxis_Medical',1.,'','exposure',np.nan))
        d=pd.DataFrame(out,columns=['stay_id','event_hour','available_hour','feature','value','unit','kind','end_hour'])
        d=d.astype({'stay_id':'int64','event_hour':'float64','available_hour':'float64','value':'float64','end_hour':'float64'})
        d.to_parquet(self.out/'prophylaxis.parquet',index=False)
        pd.DataFrame({'feature':['Prophylaxis_Surgical','Prophylaxis_Medical'],
            'n':[int(d.feature.eq('Prophylaxis_Surgical').sum()),int(d.feature.eq('Prophylaxis_Medical').sum())],
            'antibiotic_orders_considered':len(a)}).to_csv(self.out/'prophylaxis_counts.csv',index=False)

def unlabelled_stays(ds,root,exclude_stay_ids,protected,max_stays=None,seed=42,max_hours=120,min_hours=6):
    """Stays for self-supervised pretraining: every ICU stay in the raw release that is NOT in the labelled
    cohort and whose patient is NOT in the protected final holdout. Returns (selected, static): `selected`
    has the columns build_shards/RawExtractor expect (OnsetHour NaN; followup_end = stay length capped);
    `static` has Age and Gender from the raw tables. No labels of any kind are read."""
    con=duckdb.connect();con.execute("SET memory_limit='2GB'");con.execute('SET threads=2')
    try:
        if ds=='miiv':
            icu=csv_scan(table(root,'icu/icustays',True),True);pat=csv_scan(table(root,'hosp/patients',True),True)
            d=con.execute(f'''SELECT CAST(x.stay_id AS BIGINT) AS "stay_id",CAST(x.subject_id AS VARCHAR) AS "person",
              epoch(TRY_CAST(x.outtime AS TIMESTAMP)-TRY_CAST(x.intime AS TIMESTAMP))/3600.0 AS "los",
              TRY_CAST(p.anchor_age AS DOUBLE) AS "Age",lower(coalesce(p.gender,'')) AS "sex"
              FROM {icu} x LEFT JOIN {pat} p ON x.subject_id=p.subject_id''').df()
        else:
            pt=csv_scan(table(root,'patient',True),True)
            d=con.execute(f'''SELECT CAST(x.patientunitstayid AS BIGINT) AS "stay_id",CAST(x.uniquepid AS VARCHAR) AS "person",
              TRY_CAST(x.unitdischargeoffset AS DOUBLE)/60 AS "los",
              CASE WHEN lower(CAST(x.age AS VARCHAR)) LIKE '%>%' THEN 90.0 ELSE TRY_CAST(x.age AS DOUBLE) END AS "Age",
              lower(coalesce(x.gender,'')) AS "sex" FROM {pt} x''').df()
    finally:con.close()
    d=d[~d.stay_id.isin(set(int(i) for i in exclude_stay_ids))&d.person.notna()&(d.los>=min_hours)]
    d=d[~d.person.map(lambda p:protected(ds+'|'+str(p)))]
    if max_stays is not None and len(d)>max_stays:d=d.sample(max_stays,random_state=seed)
    d=d.sort_values('stay_id').reset_index(drop=True)
    d['Gender']=d.sex.map({'male':1.,'m':1.,'female':0.,'f':0.}).astype(float)
    selected=pd.DataFrame({'stay_id':d.stay_id.astype('int64'),'first_hour':0.,'followup_end':np.minimum(d.los,float(max_hours)),
        'first_positive':np.nan,'OnsetHour':np.nan,'Outcome':0})
    static=d[['stay_id','Age','Gender']].copy()
    return selected,static
```

## Builder dev/tools/build12.py

`dev/tools/build12.py` (69 lines)

```python
"""Build Sepsis_V11_Improved_MIMIC_eICU_12_stage1b.ipynb from the _11 notebook (protocol section 10b).
Re-embeds only the three changed v11 modules (models, train, tests); v9/v10 modules, the worker and the
preflight stay exactly as embedded in _11, so DATA_KEY / RAW_STAGE_KEY / cohort keys do not move."""
import json,gzip,base64,hashlib,io,ast
from pathlib import Path
R=Path('/home/user/datasciencecoursera1');M=R/'dev/work/mods';C=R/'dev/work/cells'
nb=json.load(open(R/'Sepsis_V11_Improved_MIMIC_eICU_11_architectures.ipynb'));cells=nb['cells']
def src(i):return ''.join(cells[i]['source'])
def setsrc(i,s):cells[i]['source']=s
def rep(s,a,b):
    assert s.count(a)==1,a[:70];return s.replace(a,b)
def embed(raw):
    buf=io.BytesIO()
    with gzip.GzipFile(fileobj=buf,mode='wb',mtime=0,filename='') as g:g.write(raw)
    return {'sha256':hashlib.sha256(raw).hexdigest(),'data':base64.b64encode(buf.getvalue()).decode()}
# --- cell 3: embedded modules ---
s3=src(3).splitlines();k=[i for i,l in enumerate(s3) if l.startswith('EMBEDDED_MODULES = ')][0]
emb=ast.literal_eval(s3[k][len('EMBEDDED_MODULES = '):])
for n in ['v11_models.py','v11_train.py','v11_tests.py']:emb[n]=embed((M/n).read_bytes())
s3[k]='EMBEDDED_MODULES = '+repr(emb);setsrc(3,'\n'.join(s3))
# --- cell 2: configuration ---
c=src(2)
c=rep(c,"RUN_NO_PROXY_SENSITIVITY = True                    # osta without hydrocortisone / imaging / prophylaxis (clinician-suspicion proxies)",
        "RUN_NO_PROXY_SENSITIVITY = True                    # osta without hydrocortisone / imaging / prophylaxis (clinician-suspicion proxies)\n"
        +(C/'v11_config_block.py').read_text().split('# ---- STAGE 1b')[1].join(['# ---- STAGE 1b','']).rstrip('\n'))
a=c.index("STUDY_STAGE = (");b=c.index("DATA_SOURCE = ")
c=c[:a]+"""STUDY_STAGE = ('STAGE 1b (protocol section 10b, 24 Oct 2026) on the same prespecified 10,000-stay samples, 1 seed: flat OSTA vs flat OSTA '
    'with seven organ heads (uncertainty-weighted), input dropout 0/0.1/0.2, plain BCE. The quantile operating point and the alarm policy '
    '(persistence 1/2 h, all/fresh hours) are evaluated on the VALIDATION split only. Rules 10b.2.1-4 decide the stage-2 model, '
    'operating point and policy. Test-split rows are written to test_rows_sealed.json and never printed; no transfer, conformal or '
    'ensemble rows; the sealed holdout is untouched.')
"""+c[b:]
c=rep(c,"""    'No result with RELEASE_FINAL_HOLDOUT=True has ever been produced or viewed.')""",
"""    'Development TEST-split results of run 4cd752bef2ccbd42 (_11, both databases) were viewed on 19-22 Oct 2026. Stage 1b (protocol 10b) was '
    'written after that and before any stage-1b code ran: it is blind to the test splits (validation only) but not to stage 1. '
    'No result with RELEASE_FINAL_HOLDOUT=True has ever been produced or viewed.')""")
setsrc(2,c)
# --- cells 16..21 ---
assert src(16).startswith('# 5c. Unlabelled corpus');setsrc(16,(C/'ssl_corpus_v11.py').read_text().rstrip('\n'))
assert src(17).startswith('# 6. Resolve');setsrc(17,(C/'main_14_v11.py').read_text().rstrip('\n'))
assert src(18).startswith('# 7. V11 matched');setsrc(18,(C/'main_15_v11.py').read_text().rstrip('\n'))
assert src(19).startswith('# 7b. Team summary')
t7b=(C/'team_summary_v11.py').read_text().rstrip('\n').splitlines()
setsrc(19,'# 7b. Team summary (stage 1 layout; skipped in stage 1b, see 7a).\nif not STAGE_1B:\n'+'\n'.join('    '+l for l in t7b))
cells.insert(19,{'cell_type':'code','execution_count':None,'id':'c019s1b','metadata':{},'outputs':[],'source':(C/'team_summary_stage1b.py').read_text().rstrip('\n')})
assert src(22).startswith('# Concise summary');setsrc(22,(C/'main_17_v11.py').read_text().rstrip('\n'))
# --- markdown ---
setsrc(0,src(0).replace('notebook `_11`','notebook `_12_stage1b`',1))
setsrc(1,"""## Stage 1b (this `_12_stage1b`, 24 Oct 2026; protocol section 10b)

Decided after the stage-1 development results of run `4cd752bef2ccbd42` had been seen, before any stage-1b code ran; blind to the test splits.

| Item | What this notebook does |
|---|---|
| Arms | `flat_osta` (reference) and `flat_osta_heads` (same flat backbone + seven organ heads at the output: six SOFA organs and any-organ, each predicting a component rise within 6/12/24 h; losses combined by learned uncertainty weighting, Kendall et al. 2018) |
| Input dropout | 0, 0.1, 0.2 (a predictor's value, flag and age hidden together, training only): six trainings per database |
| Loss | plain BCE for every training (the stage-2 loss by the section 10 rule) |
| Operating point | absolute (V11) vs quantile: the calibration-split alarm fraction carried to the scored population as a quantile of its own scores (label-free; needs 10,000 scored hours, else absolute) |
| Alarm policy | persistence 1 vs 2 h; cooldown 6 h kept; all hours vs fresh-information hours only; false alarms always counted over every hour |
| What is reported | the VALIDATION grid (7a) and rules 10b.2.1-4. Test-split rows are computed, written to `test_rows_sealed.json` and never printed. No transfer, conformal, trajectory-rich or ensemble rows. No self-supervised corpus. The sealed holdout is untouched |
| Reuse | labels, raw scans, supplementary stage and features are reused unchanged (v9/v10 modules identical to `_11`); only training runs |

---
"""+src(1))
for cl in cells:
    if cl['cell_type']=='code':ast.parse(''.join(cl['source']));cl['outputs']=[];cl['execution_count']=None
nb['metadata']['sepsis_validation']={'status':'fixture run before release'}
out=R/'Sepsis_V11_Improved_MIMIC_eICU_12_stage1b.ipynb'
out.write_text(json.dumps(nb,indent=1,ensure_ascii=False));print('written',out.stat().st_size//1024,'KB','cells',len(cells))
```

## Unchanged v9/v10 layer (not reproduced here)

| File | Lines | Role |
|---|---|---|
| `v9_data.py` | 1313 | raw-table extraction (DuckDB), harmonisation, feature building |
| `v10_features.py` | 219 | derived clinical features |
| `v9_train.py` | 373 | SequenceStore, normaliser, base trainer, calibration, thresholds, evaluate, bootstraps |
| `v10_train.py` | 141 | tabular arms, utility block, hospital-cluster CI, v10 fold runner |
| `v10_evaluation.py` | 104 | PhysioNet utility scorer wrapper |
| `v10_protocol.py` | 82 | splits and the sealed holdout hash |
| `v9_models.py` | 174 | OSTA family, observer bank, ExperimentModel |
| `v9_osta_base.py` | 248 | original OSTA-Transformer |
| `v9_cnn_base.py` | 201 | original CNN-Transformer |
| `v9_yaib_worker.py` | 450 | YAIB/ricu label worker (pinned; never change) |
| `v10_preflight.py` | 154 | data checks |
| `v10_fixture.py` | 122 | synthetic fixture for engineering runs |
| `v10_tests.py` | 183 | v10 engineering checks (calls the v11 checks) |
| `official_evaluate_sepsis_score.py` | 485 | PhysioNet 2019 official scorer |
