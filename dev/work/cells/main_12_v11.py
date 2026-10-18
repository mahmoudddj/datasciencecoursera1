if DATA_SOURCE=='clinical':
    # Raw-table event stage: keyed only by cohort + extraction code, shared with the legacy notebook and reused from _10.
    RAW_STAGE_KEY=raw_stage_key(COHORT_KEY,MAX_HOURS);RAW_STAGE_ROOT=PROJECT/'raw_stage_v10'/RAW_STAGE_KEY
    # v11 supplementary stage (prophylaxis events, antibiotic start times): its own key, so the main stage is never rescanned.
    SUPP_KEY=signature({'raw_stage':RAW_STAGE_KEY,'code':EMBEDDED_MODULES['v11_data.py']['sha256'],'max_hours':MAX_HOURS})[:16]
    DATA_KEY=signature({'cohort':COHORT_KEY,'raw_stage':RAW_STAGE_KEY,'supplement':SUPP_KEY,'code':signature({k:EMBEDDED_MODULES[k]['sha256'] for k in ['v9_data.py','v10_features.py','v10_protocol.py','v11_data.py','feature_specs.json']}),'max_hours':MAX_HOURS,
                        'horizon':HORIZON_HOURS,'feature_batch':FEATURE_BATCH_STAYS,
                        'data_runtime':{k:RUNTIME_VERSIONS[k] for k in ['numpy','pandas','pyarrow','duckdb']}})[:16]
    DATA_ROOT=VALIDATION_ROOT/'data'/DATA_KEY;DATA_ROOT.mkdir(parents=True,exist_ok=True)
    indexes=[];schemas=[]
    for ds in DATASETS:
        dest=DATA_ROOT/ds;stage=RAW_STAGE_ROOT/ds;shards=dest/'shards';dest.mkdir(parents=True,exist_ok=True)
        supp=stage/('supplement_'+SUPP_KEY);complete=dest/'completed.json'
        if complete.is_file():
            ix=pd.read_parquet(shards/'index.parquet');features=json.loads((shards/'schema.json').read_text())
            if not all(Path(p).is_file() for p in ix.file.unique()):raise RuntimeError('A cached feature shard is missing; remove only this data cache and rerun Section 5.')
            print('Reuse feature cache:',ds)
        else:
            selected=cohort_index(COHORT_ROOT/ds,None,RANDOM_STATE)
            if selected.empty:raise ValueError(f'{ds}: no eligible YAIB stays; increase smoke sample and inspect attrition.')
            if not (stage/'raw_complete.json').is_file():
                stage.mkdir(parents=True,exist_ok=True)
                print(f'{ds}: one raw-table scan for {len(selected)} {RUN_MODE} cohort stays. DuckDB streams whole CSV files '
                      f'(bounded memory {DUCKDB_MEMORY}) but keeps only these stays; reused afterwards.',flush=True)
                extractor=RawExtractor(ds,resolved_raw[ds],selected,stage,MAX_HOURS,
                    memory=DUCKDB_MEMORY,temp=str(RUNTIME_ROOT/'v10_duckdb_temp'))
                extractor.extract();del extractor
                atomic_json(stage/'raw_complete.json',{'raw_stage_key':RAW_STAGE_KEY,'stays':len(selected),'mode':RUN_MODE})
            else:print(ds,': reuse raw-table stage',stage)
            if not (supp/'supplement_complete.json').is_file():
                supp.mkdir(parents=True,exist_ok=True);print(ds,': supplementary stage (prophylaxis, antibiotic times)',flush=True)
                SupplementExtractor(ds,resolved_raw[ds],selected,supp,MAX_HOURS,memory=DUCKDB_MEMORY,temp=str(RUNTIME_ROOT/'v10_duckdb_temp')).supplement()
            else:print(ds,': reuse supplementary stage',supp)
            # Feature shards resume per batch after an interruption; batches are built in parallel.
            ix,features=build_shards(ds,stage,COHORT_ROOT/ds,shards,MAX_HOURS,HORIZON_HOURS,FEATURE_BATCH_STAYS,supplement=supp,workers=V11_FEATURE_WORKERS)
            if ix.empty:raise ValueError(f'{ds}: no evaluable pre-onset stays')
            atomic_json(complete,{'data_key':DATA_KEY,'raw_stage_key':RAW_STAGE_KEY,'supplement_key':SUPP_KEY,'stays':len(ix),'features':features})
        indexes.append(ix);schemas.append(features);gc.collect()
    assert schemas[0]==schemas[1], 'Cross-dataset feature schemas must match.'
    INDEX=pd.concat(indexes,ignore_index=True);FEATURES=schemas[0];del indexes
    assert INDEX.Patient_ID.is_unique
    INDEX.to_parquet(DATA_ROOT/'index.parquet',index=False)
    display(INDEX[~INDEX.Group_ID.map(protected_group)].groupby('Dataset').agg(stays=('Patient_ID','size'),patient_groups=('Group_ID','nunique'),
        hospitals=('Hospital_ID','nunique'),stays_with_prediction_window=('eligible_positive','sum'),
        septic_stays_with_antibiotic_time=('FirstAntibioticAroundOnset',lambda s:int(s.notna().sum()))))
    print('Predictor columns including masks and observation ages:',len(FEATURES))
else:
    from v10_fixture import make_fixture
    DATA_ROOT=VALIDATION_ROOT/'synthetic_fixture'
    INDEX,FEATURES=make_fixture(DATA_ROOT)
    MAX_HOURS=24
    DATA_KEY=signature({'synthetic':True,'code':CODE_SIGNATURE})[:16]
    print('Created synthetic fixtures for both source schemas; no clinical observations.')
# Every predictor must have an explicit organ group; retrospective context is never a predictor.
organ_mapping(FEATURES)
assert not any(f.startswith(('Phenotype_','SpecimenSite_','TreatmentContext_','ClinicianSuspectedSite_','PostoperativeAdmission')) for f in FEATURES)
assert 'FirstAntibioticAroundOnset' not in FEATURES  # evaluation metadata only
