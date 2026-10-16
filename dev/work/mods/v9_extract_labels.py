if need_extract:
    py_dir=COHORT_REPO/'Python'
    worker=py_dir/'v9_yaib_worker.py'
    worker.write_bytes((CODE_DIR/'v9_yaib_worker.py').read_bytes())
    extract_env=YAIB_RUNTIME_ENV.copy()
    extract_env.update({'RICU_DATA_PATH':str(RICU_MOUNT),
        'PYTHONPATH':str(py_dir),'PYTHONUNBUFFERED':'1',
        'R_LIBS_USER':YAIB_R_LIB,'RENV_PROJECT':str(py_dir)})
    for ds in DATASETS:
        if cohort_complete(ds) and not FORCE_YAIB_REEXTRACT:
            print('Reuse completed cohort:',ds);continue
        if FORCE_YAIB_REEXTRACT and (COHORT_ROOT/ds).exists():shutil.rmtree(COHORT_ROOT/ds)
        ds_extract_env=extract_env.copy()
        ds_extract_env['RICU_SRC_LOAD']=ds
        extract_cohort_batched(ds,resolved_raw[ds],COHORT_ROOT/ds,worker,YAIB_PYTHON,py_dir,
            ds_extract_env,batch_size=COHORT_BATCH_STAYS,
            smoke_n=COHORT_PROTOCOL['candidate_n'],  # smoke cap, prespecified full-mode sample, or None (all stays)
            seed=RANDOM_STATE,log_root=LOG_ROOT)
        atomic_json(COHORT_ROOT/ds/'v9_complete.json',{'protocol':COHORT_KEY})
        gc.collect()
for ds in DATASETS:
    if not cohort_complete(ds):raise RuntimeError(f'{ds}: no complete v9 cohort; enable extraction and run Sections 4–5.')
print('Both v9 cohort caches are ready.')