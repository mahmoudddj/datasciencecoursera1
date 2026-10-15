if DATA_SOURCE == 'clinical':
    # Release check FIRST (read-only stay counts): a demo or partial copy stops here,
    # before any cohort key, environment setup or import.
    from v9_runtime import raw_ids
    from v10_preflight import check_files,check_release,gate_report
    # Per-file audit first (names and sizes only): catches demo files mixed into a full folder.
    RAW_FILE_AUDIT=pd.DataFrame(check_files({ds:str(p) for ds,p in resolved_raw.items()},ALLOW_DEMO_DATA,RUN_MODE))
    display(RAW_FILE_AUDIT[['dataset','table','MB','full_release_min_MB','status']])
    SOURCE_COUNTS={ds:len(raw_ids(ds,resolved_raw[ds],None,RANDOM_STATE)) for ds in DATASETS}
    print('Raw candidate stay counts:',SOURCE_COUNTS)
    for note in check_release(SOURCE_COUNTS,{ds:str(p) for ds,p in resolved_raw.items()},ALLOW_DEMO_DATA,RUN_MODE):print(' ',note)
    RAW_FINGERPRINTS={ds:fingerprint(resolved_raw[ds]) for ds in DATASETS}
    COHORT_PROTOCOL={'version':'v9_balanced_2','raw':RAW_FINGERPRINTS,'yaib':YAIB_COHORTS_COMMIT,
     'patch':'grouped_outcome_fill_v1+ricu_dictionary+interval_namespace+balanced_batches','mode':RUN_MODE,
     'candidate_n':SMOKE_STAYS_PER_DATASET if RUN_MODE=='smoke' else None,
     'seed':RANDOM_STATE,'worker_sha':EMBEDDED_MODULES['v9_yaib_worker.py']['sha256']}
    COHORT_KEY=signature(COHORT_PROTOCOL)[:16]
    COHORT_BASE=PROJECT/'cohorts_v9'/COHORT_KEY;COHORT_ROOT=COHORT_BASE/'sepsis'
    COHORT_ROOT.mkdir(parents=True,exist_ok=True)
    atomic_json(COHORT_BASE/'source_protocol.json',COHORT_PROTOCOL)
    def cohort_complete(ds):
        folder=COHORT_ROOT/ds
        return (folder/'v9_complete.json').is_file() and all((folder/f).is_file() for f in ['dyn.parquet','sta.parquet','outc.parquet'])
    print('Cohort cache:',COHORT_BASE)
    # Reuse requires the original label protocol and raw source fingerprints.
    if REUSE_COHORT_ROOT:
        candidate=Path(REUSE_COHORT_ROOT).expanduser().resolve()
        pp=candidate.parent/'source_protocol.json'
        if not pp.is_file():raise ValueError('Selected cohort needs original source_protocol.json')
        previous=json.loads(pp.read_text())
        for field in ['raw','yaib','mode','candidate_n','seed']:
            if previous.get(field)!=COHORT_PROTOCOL.get(field):raise ValueError('Incompatible cohort field: '+field)
        if previous.get('worker_sha')!=COHORT_PROTOCOL['worker_sha']:
            # A live v9 dictionary repair may have retained an old key. Require its on-disk
            # checksum audit rather than treating an unknown worker as equivalent.
            raise ValueError('Worker hash differs. Restore the recorded patched protocol/checksum before reusing this cache; raw ricu imports remain reusable.')
        COHORT_ROOT=candidate;COHORT_BASE=candidate.parent;COHORT_KEY=candidate.parent.name
        COHORT_PROTOCOL=previous
    print('Reuse-safe label cache:',COHORT_ROOT)
    atomic_json(COHORT_BASE/'v10_candidate_counts.json',{'counts':SOURCE_COUNTS,'raw_paths':resolved_raw,'mode':RUN_MODE})
    GATE_ROWS,GATE_TODO,DRIVE_FREE_GB=gate_report(DATASETS,resolved_raw,PROJECT,cohort_complete)
    display(pd.DataFrame(GATE_ROWS))
    if GATE_TODO:
        print('Cohorts to build (smoke-capped label extraction):',GATE_TODO,
              '| verified ricu imports are reused; if any raw table is new or changed, the import step names it and asks for ALLOW_FULL_RAW_IMPORT=True.')

else:
    print("Synthetic engineering run: clinical extraction skipped.")