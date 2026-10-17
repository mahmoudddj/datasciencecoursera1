# Feature registry for EVERY predictor column (kind, organ group, unit, source) and coverage gates.
from v9_models import ORGAN_FEATURES
def feature_kind(f):
    if f.endswith('_observed'):return 'observed-value mask'
    if f.endswith('_age'):return 'hours since latest known measurement'
    if f in ENGINEERED:return 'handcrafted (v10_features '+FEATURE_VERSION+')'
    if f in COMORBID:return 'chronic comorbidity flag (from its documentation time)'
    if f in AIRWAY:return 'invasive airway (ETT/tracheostomy) state'
    if f in EXPOSURES:return 'documented exposure (device, medication, imaging, fluids) from its own time'
    if f in ADMISSION:return 'admission context (known at ICU admission / admitting diagnosis entry)'
    if f in RENAL:return 'renal window (availability-aware)'
    if f in DERIVED:return 'derived criterion/ratio'
    return 'raw measurement'
mapping,_=organ_mapping(FEATURES)
REGISTRY=pd.DataFrame([{'feature':f,'kind':feature_kind(f),'organ_group':mapping[f],'base':base_name(f),
   'unit':str(SPEC.get(base_name(f),{}).get('unit','derived/see definition')),
   'source_mapping':json.dumps(SPEC.get(base_name(f),{}).get('sources',{}))} for f in FEATURES])
REGISTRY=pd.concat([REGISTRY,pd.DataFrame(
   [{'feature':'PostoperativeAdmission','kind':'metadata only (not comparably available; never a predictor)'}]+
   [{'feature':'Phenotype_'+f,'kind':'retrospective documentation subgroup only'} for f in PHENO]+
   [{'feature':'TreatmentContext_'+f,'kind':'retrospective order proxy only'} for f in MED_CONTEXT]+
   [{'feature':'SpecimenSite_*','kind':'specimen collection site (not a confirmed source)'},
    {'feature':'ClinicianSuspectedSite_*','kind':'eICU care-plan suspected site (not confirmed)'}])],ignore_index=True)
REGISTRY.to_csv(DATA_ROOT/'feature_registry.csv',index=False)
display(REGISTRY.groupby(['kind'],as_index=False).size())
if DATA_SOURCE == 'clinical':
    COVERAGE=pd.concat([pd.read_csv(DATA_ROOT/ds/'shards/coverage.csv') for ds in DATASETS],ignore_index=True)
    COVERAGE.to_csv(DATA_ROOT/'coverage_all.csv',index=False)
    display(COVERAGE.groupby('dataset',as_index=False).agg(features=('feature','size'),mean_missing_fraction=('missing_fraction','mean')).round(3))
    for ds in DATASETS:
        print(ds,'audit files:',RAW_STAGE_ROOT/ds/'extraction_counts.csv',DATA_ROOT/ds/'shards/units.csv')
    empty=COVERAGE[COVERAGE.observed_rows.eq(0)]
    if len(empty):print('Never observed (inspect mappings/optional tables before training):',empty.groupby('dataset').feature.apply(list).to_dict())
    critical=['HR','SBP','Resp','Temp','Creatinine','Platelets','UrineOutput','GCS']
    bad=empty[empty.feature.isin(critical)]
    if len(bad):raise ValueError('Core channel never captured: '+str(bad[['dataset','feature']].values.tolist())+
        '. Check the optional raw tables (eICU GCS needs nurseCharting) and units; do not accept an all-missing core channel.')
else:
    print("Synthetic engineering run: clinical coverage audit skipped.")
