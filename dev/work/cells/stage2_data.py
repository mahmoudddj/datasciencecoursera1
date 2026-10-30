# 5. Stage-2 data build (protocol 10c.2 item 19): raw-table stage, v11 supplement, v12 supplement (antibiotic courses,
# culture times, outcomes, anchor-year group), hourly feature shards; the index flags Incident vs ArrivalSepsis; the
# stay-level tables for the stage-2 driver are assembled here (aggregates only are printed).
from v12_cohort import cohort_index_v12
from v12_data import CourseExtractor,first_treatment_hours
from v12_labels import suspicion_events,documentation_prior
if DATA_SOURCE=='clinical':
    RAW_STAGE_KEY=raw_stage_key(COHORT_KEY,MAX_HOURS);RAW_STAGE_ROOT=PROJECT/'raw_stage_v10'/RAW_STAGE_KEY
    SUPP_KEY=signature({'raw_stage':RAW_STAGE_KEY,'code':EMBEDDED_MODULES['v11_data.py']['sha256'],'max_hours':MAX_HOURS})[:16]
    SUPP2_KEY=signature({'raw_stage':RAW_STAGE_KEY,'code':EMBEDDED_MODULES['v12_data.py']['sha256'],'max_hours':MAX_HOURS})[:16]
    DATA_KEY=signature({'cohort':COHORT_KEY,'raw_stage':RAW_STAGE_KEY,'supplement':SUPP_KEY,'supplement2':SUPP2_KEY,'code':signature({k:EMBEDDED_MODULES[k]['sha256'] for k in ['v9_data.py','v10_features.py','v10_protocol.py','v11_data.py','v12_cohort.py','feature_specs.json']}),
                        'max_hours':MAX_HOURS,'horizon':HORIZON_HOURS,'feature_batch':FEATURE_BATCH_STAYS,'data_runtime':{k:RUNTIME_VERSIONS[k] for k in ['numpy','pandas','pyarrow','duckdb']}})[:16]
    DATA_ROOT=VALIDATION_ROOT/'data'/DATA_KEY;DATA_ROOT.mkdir(parents=True,exist_ok=True)
    indexes=[];schemas=[];SUPP2={}
    for ds in DATASETS:
        dest=DATA_ROOT/ds;stage=RAW_STAGE_ROOT/ds;shards=dest/'shards';dest.mkdir(parents=True,exist_ok=True)
        supp=stage/('supplement_'+SUPP_KEY);supp2=stage/('supplement2_'+SUPP2_KEY);complete=dest/'completed.json';SUPP2[ds]=supp2
        selected=cohort_index_v12(COHORT_ROOT/ds,None,RANDOM_STATE)
        if selected.empty:raise ValueError(f'{ds}: no eligible YAIB stays; inspect attrition.')
        if complete.is_file():
            ix=pd.read_parquet(shards/'index.parquet');features=json.loads((shards/'schema.json').read_text())
            if not all(Path(p).is_file() for p in ix.file.unique()):raise RuntimeError('A cached feature shard is missing; remove only this data cache and rerun Section 5.')
            print('Reuse feature cache:',ds)
        else:
            if not (stage/'raw_complete.json').is_file():
                stage.mkdir(parents=True,exist_ok=True)
                print(f'{ds}: one raw-table scan for {len(selected)} cohort stays (all comers). DuckDB streams whole CSV files (bounded memory {DUCKDB_MEMORY}).',flush=True)
                extractor=RawExtractor(ds,resolved_raw[ds],selected,stage,MAX_HOURS,memory=DUCKDB_MEMORY,temp=str(RUNTIME_ROOT/'v10_duckdb_temp'));extractor.extract();del extractor
                atomic_json(stage/'raw_complete.json',{'raw_stage_key':RAW_STAGE_KEY,'stays':len(selected),'mode':RUN_MODE})
            else:print(ds,': reuse raw-table stage',stage)
            if not (supp/'supplement_complete.json').is_file():
                supp.mkdir(parents=True,exist_ok=True);print(ds,': supplementary stage (prophylaxis, antibiotic times)',flush=True)
                SupplementExtractor(ds,resolved_raw[ds],selected,supp,MAX_HOURS,memory=DUCKDB_MEMORY,temp=str(RUNTIME_ROOT/'v10_duckdb_temp')).supplement()
            ix,features=build_shards(ds,stage,COHORT_ROOT/ds,shards,MAX_HOURS,HORIZON_HOURS,FEATURE_BATCH_STAYS,supplement=supp,workers=V11_FEATURE_WORKERS)
            if ix.empty:raise ValueError(f'{ds}: no evaluable pre-onset stays')
            atomic_json(complete,{'data_key':DATA_KEY,'raw_stage_key':RAW_STAGE_KEY,'supplement_key':SUPP_KEY,'supplement2_key':SUPP2_KEY,'stays':len(ix),'features':features})
        if not (supp2/'supplement2_complete.json').is_file():
            supp2.mkdir(parents=True,exist_ok=True);print(ds,': stage-2 supplementary stage (antibiotic courses, cultures, outcomes, anchor-year group)',flush=True)
            CourseExtractor(ds,resolved_raw[ds],selected,supp2,MAX_HOURS,memory=DUCKDB_MEMORY,temp=str(RUNTIME_ROOT/'v10_duckdb_temp')).supplement2()
        else:print(ds,': reuse stage-2 supplementary stage',supp2)
        for c in ['Incident','ArrivalSepsis']:
            if c not in ix:ix=ix.merge(selected[['stay_id',c]],on='stay_id',how='left')
        indexes.append(ix);schemas.append(features);gc.collect()
    assert schemas[0]==schemas[1],'Cross-dataset feature schemas must match.'
    INDEX=pd.concat(indexes,ignore_index=True);FEATURES=schemas[0];del indexes
    assert INDEX.Patient_ID.is_unique
    INDEX.to_parquet(DATA_ROOT/'index.parquet',index=False)
    # ---- stay-level tables for the driver (Patient_ID keyed) ----
    tabs={'suspicion_hour':{},'first_treatment':{},'documented':{},'abx_starts':{},'anchor_year_group':{}};doc_rows=[]
    for ds in DATASETS:
        pre=ds+'|';courses=pd.read_parquet(SUPP2[ds]/'courses.parquet');cultures=pd.read_parquet(SUPP2[ds]/'cultures.parquet');outc=pd.read_parquet(SUPP2[ds]/'outcomes.parquet').set_index('stay_id')
        ev=suspicion_events(courses,outc.death_hour);ev.to_parquet(DATA_ROOT/ds/'suspicion_events.parquet',index=False)
        tabs['suspicion_hour'].update({pre+str(int(s)):float(h) for s,h in zip(ev.stay_id,ev.suspicion_hour)})
        ft=first_treatment_hours(courses,cultures);tabs['first_treatment'].update({pre+str(int(s)):float(h) for s,h in zip(ft.stay_id,ft.first_treatment_hour)})
        tabs['documented'].update({pre+str(int(s)):bool(v==1) for s,v in outc.sepsis_documented.items() if pd.notna(v)})
        for s,g in courses.groupby('stay_id'):tabs['abx_starts'][pre+str(int(s))]=sorted(float(x) for x in g.start)
        if 'anchor_year_group' in outc:tabs['anchor_year_group'].update({pre+str(int(s)):v for s,v in outc.anchor_year_group.items() if isinstance(v,str)})
        sub=INDEX[INDEX.Dataset.eq(ds)];doc_rows.append(pd.DataFrame({'Dataset':ds,'operational_positive':sub.OnsetHour.notna().astype(int),'documented':sub.Patient_ID.astype(str).map(tabs['documented']).fillna(False).astype(int)}))
        print(f"{ds}: suspicion events {int(ev.suspicion_hour.notna().sum())} of {len(ev)} stays | rejection reasons: {ev.reason.value_counts().to_dict()} | documented among operational positives: "
              f"{doc_rows[-1].query('operational_positive==1').documented.mean():.2f}")
    tabs['arrival']={p:float(a) for p,a in zip(INDEX.Patient_ID.astype(str),INDEX.ArrivalSepsis.fillna(0))}
    tabs['doc_prior']=documentation_prior(pd.concat(doc_rows,ignore_index=True));tabs['alt_onsets']=ALT_ONSETS
    STAGE2_TABLES=tabs
    atomic_json(DATA_ROOT/'stage2_tables_summary.json',{k:(len(v) if isinstance(v,dict) else str(v)) for k,v in tabs.items()})
    display(INDEX[~INDEX.Group_ID.map(protected_group)].groupby(['Dataset','Incident']).agg(stays=('Patient_ID','size'),patient_groups=('Group_ID','nunique'),hospitals=('Hospital_ID','nunique'),
        stays_with_prediction_window=('eligible_positive','sum')))
    print('Predictor columns including masks and observation ages:',len(FEATURES))
else:
    from v12_fixture import make_stage2_fixture
    DATA_ROOT=VALIDATION_ROOT/'synthetic_fixture_stage2'
    INDEX,FEATURES,STAGE2_TABLES,_fixture_corpus=make_stage2_fixture(DATA_ROOT)
    INDEX['Incident']=1;INDEX['ArrivalSepsis']=0
    MAX_HOURS=24;DATA_KEY=signature({'synthetic':True,'stage2':True,'code':CODE_SIGNATURE})[:16]
    print('Created synthetic stage-2 fixtures for both source schemas; no clinical observations.')
# Primary cohort = incident stays; arrival-sepsis stays enter only the pretraining corpus (item 3) and the all-comers strata.
TRAIN_INDEX=INDEX[INDEX.Incident.eq(1)].copy();ARRIVAL_INDEX=INDEX[INDEX.ArrivalSepsis.eq(1)].copy()
organ_mapping(FEATURES)
assert not any(f.startswith(('Phenotype_','SpecimenSite_','TreatmentContext_','ClinicianSuspectedSite_','PostoperativeAdmission')) for f in FEATURES)
assert 'FirstAntibioticAroundOnset' not in FEATURES
from v12_manifest import manifest as two_channel_manifest,audit as manifest_audit
MANIFEST=two_channel_manifest(FEATURES);display(manifest_audit(MANIFEST,FEATURES));MANIFEST.to_csv(DATA_ROOT/'two_channel_manifest.csv',index=False)
print('Incident (primary) stays:',len(TRAIN_INDEX),'| arrival-sepsis stays (pretraining corpus only):',len(ARRIVAL_INDEX))
