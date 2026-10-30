# 4d. Stage-2 label and cohort extraction (protocol 10c.2 items 1, 10, 19): all comers (exclusion 7 dropped), completed
# label batches of the earlier 20,000-candidate plans carried over, batches in parallel, resumable per batch; then the
# two label VARIANTS (labels phase only, own caches) for the item-10 sensitivity passes.
if DATA_SOURCE == 'clinical':
    from v12_cohort import extract_cohort_batched_v12
    py_dir=COHORT_REPO/'Python';worker=py_dir/'v9_yaib_worker.py';worker.write_bytes((CODE_DIR/'v9_yaib_worker.py').read_bytes())
    extract_env=YAIB_RUNTIME_ENV.copy()
    extract_env.update({'RICU_DATA_PATH':str(RICU_MOUNT),'PYTHONPATH':str(py_dir),'PYTHONUNBUFFERED':'1','R_LIBS_USER':YAIB_R_LIB,'RENV_PROJECT':str(py_dir)})
    if STAGE2_KEEP_EARLY_ONSET:extract_env['V12_KEEP_EARLY_ONSET']='1'
    reuse_roots=[Path(p).expanduser() for p in STAGE2_REUSE_LABEL_ROOTS if Path(p).expanduser().is_dir()]
    for ds in DATASETS:
        if cohort_complete(ds) and not FORCE_YAIB_REEXTRACT:print('Reuse completed cohort:',ds);continue
        if FORCE_YAIB_REEXTRACT and (COHORT_ROOT/ds).exists():shutil.rmtree(COHORT_ROOT/ds)
        ds_env=extract_env.copy();ds_env['RICU_SRC_LOAD']=ds
        extract_cohort_batched_v12(ds,resolved_raw[ds],COHORT_ROOT/ds,worker,YAIB_PYTHON,py_dir,ds_env,batch_size=COHORT_BATCH_STAYS,
            smoke_n=COHORT_PROTOCOL['candidate_n'],seed=RANDOM_STATE,log_root=LOG_ROOT,parallel=LABEL_PARALLEL_BATCHES,reuse_label_roots=[r/ds for r in reuse_roots])
        atomic_json(COHORT_ROOT/ds/'v9_complete.json',{'protocol':COHORT_KEY,'stage2':True});gc.collect()
    for ds in DATASETS:
        if not cohort_complete(ds):raise RuntimeError(f'{ds}: no complete cohort; enable extraction and run Sections 4-5.')
    print('Both all-comers cohort caches are ready:',COHORT_ROOT)
    # ---- label variants (item 10a, 10b): labels phase only; onsets read from the batches' labels.parquet ----
    ALT_ONSETS={}
    for ds,si_mode in (STAGE2_LABEL_VARIANTS or {}).items():
        vkey=signature({'cohort':COHORT_KEY,'si_mode':si_mode,'ds':ds})[:16];vroot=PROJECT/'cohorts_v9'/f'{COHORT_KEY}_variant_{vkey}'/'sepsis'/ds;vroot.mkdir(parents=True,exist_ok=True)
        if not (vroot/'variant_complete.json').is_file():
            ds_env=extract_env.copy();ds_env.update({'RICU_SRC_LOAD':ds,'V12_SI_MODE':si_mode})
            extract_cohort_batched_v12(ds,resolved_raw[ds],vroot,worker,YAIB_PYTHON,py_dir,ds_env,batch_size=COHORT_BATCH_STAYS,smoke_n=COHORT_PROTOCOL['candidate_n'],
                seed=RANDOM_STATE,log_root=LOG_ROOT,parallel=LABEL_PARALLEL_BATCHES,reuse_label_roots=[],phases=('labels',))
            atomic_json(vroot/'variant_complete.json',{'si_mode':si_mode,'cohort':COHORT_KEY})
        from v9_data import hour_values
        ev=[]
        for p in sorted(vroot.glob('batches/*/*/labels.parquet')):
            z=pd.read_parquet(p);z=z[z.sep3_alt.notna()];ev.append(pd.DataFrame({'stay_id':z.stay_id.astype('int64'),'OnsetHour':hour_values(z.time)}))
        ev=pd.concat(ev,ignore_index=True).groupby('stay_id').OnsetHour.min() if ev else pd.Series(dtype=float)
        ALT_ONSETS[ds]={f'{ds}|{int(s)}':float(h) for s,h in ev.items()}
        print(f'{ds}: label variant si_mode={si_mode}: {len(ALT_ONSETS[ds])} stays with an onset (all candidates)')
else:
    ALT_ONSETS={}
    print("Synthetic engineering run: clinical extraction skipped.")
