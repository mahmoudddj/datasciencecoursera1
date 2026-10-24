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
