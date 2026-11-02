# ---- Stage 2: what still needs the YAIB extraction environment (cohort OR label variant), per database ----
# The environment setup, the ricu import check and 4d all use this one rule, so a finished cohort with
# unfinished label variants still gets the environment (fix of 2 Nov 2026).
def stage2_variant_root(ds,si_mode):
    return PROJECT/'cohorts_v9'/f"{COHORT_KEY}_variant_{signature({'cohort':COHORT_KEY,'si_mode':si_mode,'ds':ds})[:16]}"/'sepsis'/ds
def stage2_variant_complete(ds):
    si_mode=(STAGE2_LABEL_VARIANTS or {}).get(ds)
    return (not si_mode) or (stage2_variant_root(ds,si_mode)/'variant_complete.json').is_file()
def stage2_extraction_pending(ds):
    return bool(FORCE_YAIB_REEXTRACT) or not cohort_complete(ds) or not stage2_variant_complete(ds)
if DATA_SOURCE == 'clinical':
    print('Still needs the YAIB environment:',{ds:('cohort' if not cohort_complete(ds) else 'label variant' if not stage2_variant_complete(ds) else 'nothing') for ds in DATASETS})
