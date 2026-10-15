# 4c. YAIB abx_cont fix for batches with no antibiotic record before death (eICU).
# Pinned YAIB abx_cont() crashes ("Object 'max_gap' not found") when the batch has no
# antibiotic rows: ricu::slide() then returns its empty input without the max_gap column.
# The fix returns the same EMPTY result the normal path would give; batches with antibiotic
# rows run unchanged code. Already-completed batches never reached this path, so they stay valid.
import hashlib
_cb = COHORT_REPO/'ricu-extensions'/'callbacks'/'callback-sepsis.R'
_PINNED = 'f88c1007c2cc739160e63d26ac1aa199ae2dcf08749973cb42a825b0107cb4ad'   # YAIB-cohorts 74ac699f
_PATCHED = 'b42caa9806fdbff4931d40c19ded370819c5c9dda5efea923a6b55d10fe6fdc5'
_OLD = "  res <- res[max_gap <= abx_max_gap]\n"
_NEW = (
"  # V11_EMPTY_ABX_FIX: ricu::slide() returns its input unchanged when no antibiotic\n"
"  # record precedes death in this batch (0 rows, no max_gap column). Return the same\n"
"  # empty result shape as the normal path (id, index, abx_cont); non-empty input is untouched.\n"
"  if (!\"max_gap\" %in% colnames(res)) {\n"
"    if (nrow(res) != 0L) stop(\"V11_EMPTY_ABX_FIX: slide() result without max_gap has rows\")\n"
"    res <- ricu::rm_cols(res, ricu::data_vars(res), by_ref = TRUE)\n"
"    res[, c(\"abx_cont\") := logical(0)]\n"
"    return(res)\n"
"  }\n" + _OLD)
if DATA_SOURCE == 'clinical' and _cb.is_file():
    _sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    if _sha(_cb) == _PINNED:
        _cb.write_text(_cb.read_text().replace(_OLD, _NEW))
    if _sha(_cb) != _PATCHED:
        raise RuntimeError(f'Unexpected {_cb} (sha {_sha(_cb)}); not patching an unknown YAIB version.')
    atomic_json(COHORT_BASE/'yaib_callback_amendment.json', {
        'file': 'ricu-extensions/callbacks/callback-sepsis.R', 'function': 'abx_cont',
        'pinned_sha256': _PINNED, 'patched_sha256': _PATCHED,
        'change': 'empty slide() result (no antibiotic before death in batch) returns an empty abx_cont '
                  'table instead of crashing; non-empty batches unchanged',
        'tested': 'ricu 0.6.0 sources: empty batch reproduces the crash and is fixed; non-empty batch identical; '
                  'susp_inf_alt/sep3_alt accept the empty table'})
    print('YAIB abx_cont fix active:', _cb)
else:
    print('YAIB repo not present (labels already complete or synthetic run); no fix needed.')
