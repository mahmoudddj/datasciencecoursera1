# 4. Source prerequisites are resolved BEFORE any target extraction.
from v10_legacy import load_bundle,source_files,reproduce,score_target,source_preflight,import_original_outputs
from v10_fixture import make_legacy_fixture
BUNDLE_KEY=signature({'code':CODE_SIGNATURE,'mode':RUN_MODE,'data':DATA_SOURCE,'source':PHYSIONET_SOURCE,'legacy_mode':LEGACY_MODE,
   'feature_policy':LEGACY_FEATURE_POLICY,'original_outputs':ORIGINAL_OUTPUT_DIRS,'representation':HISTORICAL_SOURCE_REPRESENTATION,
   'units':HISTORICAL_SOURCE_UNITS,'osta_seeds':OSTA_HISTORICAL_SEEDS,'osta_ensemble':OSTA_HISTORICAL_ENSEMBLE,'frozen':HISTORICAL_BUNDLES})[:16]
BUNDLE_ROOT=VALIDATION_ROOT/'source_bundles'/BUNDLE_KEY;BUNDLE_ROOT.mkdir(parents=True,exist_ok=True)
BUNDLES={};SOURCE_PREFLIGHT=None;DEVICE='cuda' if torch.cuda.is_available() else 'cpu'
if DATA_SOURCE=='fixture':
    SOURCE_INDEX,TARGET_INDEX=make_legacy_fixture(VALIDATION_ROOT/'synthetic_fixture')
elif LEGACY_MODE in ('reproduce','import_original') and PHYSIONET_SOURCE:
    # import_original only needs a sample to verify representation/units; reproduction stages the source.
    SOURCE_INDEX=source_files(PHYSIONET_SOURCE,BUNDLE_ROOT/'source_stays',RUN_MODE,cap=400 if LEGACY_MODE=='import_original' else None)
elif LEGACY_MODE=='reproduce':
    raise FileNotFoundError('Set PHYSIONET_SOURCE to your PhysioNet PSV folder or cleaned CSV. No weights were included in the supplied archive. Target extraction has not started.')
if DATA_SOURCE=='fixture' or (LEGACY_MODE in ('reproduce','import_original') and PHYSIONET_SOURCE):
    SOURCE_PREFLIGHT=source_preflight(SOURCE_INDEX,LEGACY_FEATURE_POLICY)
    atomic_json(BUNDLE_ROOT/'source_preflight.json',SOURCE_PREFLIGHT)
    print('Source:',len(SOURCE_INDEX),'stays |',SOURCE_PREFLIGHT['source_representation'],'| units',SOURCE_PREFLIGHT['source_units'],
          '| base features',len(SOURCE_PREFLIGHT['base_features']),'| target-unsupported (kept missing):',SOURCE_PREFLIGHT['target_unsupported'])
for arm in ['osta','cnn']:
    with (LOG_ROOT/('legacy_'+arm+'_source.log')).open('a') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        if DATA_SOURCE=='fixture' or LEGACY_MODE=='reproduce':
            BUNDLES[arm]=reproduce(SOURCE_INDEX,arm,BUNDLE_ROOT/arm,RUN_MODE,synthetic=DATA_SOURCE=='fixture',preflight=SOURCE_PREFLIGHT,device=DEVICE)
        elif LEGACY_MODE=='import_original':
            if not ORIGINAL_OUTPUT_DIRS[arm]:raise FileNotFoundError(f'Set ORIGINAL_OUTPUT_DIRS["{arm}"] to the folder written by the original script.')
            rep=HISTORICAL_SOURCE_REPRESENTATION or (SOURCE_PREFLIGHT or {}).get('source_representation','')
            units=HISTORICAL_SOURCE_UNITS or (SOURCE_PREFLIGHT or {}).get('source_units',{})
            BUNDLES[arm]=import_original_outputs(arm,ORIGINAL_OUTPUT_DIRS[arm],BUNDLE_ROOT/arm,rep,units,
                OSTA_HISTORICAL_ENSEMBLE if arm=='osta' else None,OSTA_HISTORICAL_SEEDS if arm=='osta' else None,RUN_MODE)
        else:
            if not HISTORICAL_BUNDLES[arm]:raise FileNotFoundError('Set HISTORICAL_BUNDLES['+arm+'] to its complete source bundle.')
            BUNDLES[arm]=load_bundle(HISTORICAL_BUNDLES[arm],arm,RUN_MODE)
    m=BUNDLES[arm][1]
    assert m['max_hours']==MAX_HOURS, 'Both frozen models must use the same declared target trajectory length'
    print(f"Source bundle verified: {arm} | {m['provenance']} | members {len(m['members'])} | threshold {m['threshold']} | policy {m['policy']}"
          +(f" | source internal test utility {m['source_internal_test']['normalized_utility']:.3f}" if m.get('source_internal_test') else ''))
