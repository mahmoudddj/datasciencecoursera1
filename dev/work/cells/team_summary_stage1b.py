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
    print('RULE 4 inputs (chosen model, chosen operating point; mean sensitivity over databases, max false alarms per patient-day):');display(agg.round(3))
    ok=agg[agg.fa<=budget]
    if len(ok):
        ok=ok.sort_values(['sens','persistence','fresh_only'],ascending=[False,True,True]);pol=ok.iloc[0]
    else:pol=agg.sort_values(['fa']).iloc[0];print('[rule 4] no policy met the budget on both databases; the lowest-burden policy is recorded and reported as found')
    print(f'[rule 4] stage-2 policy: persistence {int(pol.persistence)} h, '+('fresh-information hours only' if bool(pol.fresh_only) else 'all hours')+f' | mean sensitivity {pol.sens:.3f}, max FA/patient-day {pol.fa:.3f}')
    decision.update(persistence=int(pol.persistence),fresh_only=bool(pol.fresh_only))
    atomic_json(RESULTS_ROOT/'stage1b_decision.json',decision)
    print('\nSTAGE 2 SETTINGS to copy into Section 1 (and into PROTOCOL.md 10b outcome, dated):')
    print(f"  STAGE_1B = False; project model = {project_model}; STAGE2_OPERATING_POINT = '{op}'; STAGE2_PERSISTENCE = {int(pol.persistence)}; STAGE2_FRESH_ONLY = {bool(pol.fresh_only)}")
    print('Saved:',RESULTS_ROOT/'stage1b_validation_grid.csv','and stage1b_decision.json')
else:print('Stage 1b summary skipped (STAGE_1B is False).')
