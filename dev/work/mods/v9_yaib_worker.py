"""Run inside the preserved YAIB Python/R environment, one bounded cohort batch.

This is an adapter for the pinned YAIB code, not a replacement sepsis
definition. The v9 dictionary bridge preserves the pinned ricu base
dictionary and the pinned YAIB extension JSONs, but performs their documented
`sources`-only extension merge deterministically in Python before handing the
result back to ricu:::parse_dictionary().
"""
import os,sys,json,argparse,hashlib,copy
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def _json_object(path, label):
    path = Path(path)
    obj = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(obj, dict):
        raise RuntimeError(
            f'{label} must decode to a named JSON object; '
            f'got {type(obj).__name__}: {path}'
        )
    return obj


def _merge_extension(base, patch, owner):
    """Mirror ricu's documented custom-dictionary extension rule.

    Existing concepts may only be extended through a `sources` object.
    Extension source entries take precedence for duplicate source names.
    New concepts are copied in full.
    """
    for name, spec in patch.items():
        if name not in base:
            base[name] = copy.deepcopy(spec)
            continue

        current = base[name]
        if not isinstance(current, dict) or not isinstance(spec, dict):
            raise RuntimeError(
                f'{owner}: concept {name!r} is not an object and cannot be merged safely'
            )

        if current.get('class') == 'rec_cncpt':
            raise RuntimeError(
                f'{owner}: attempts to extend recursive concept {name!r}; '
                'refusing to change pinned ricu semantics'
            )

        if set(spec.keys()) != {'sources'} or not isinstance(spec.get('sources'), dict):
            raise RuntimeError(
                f'{owner}: existing concept {name!r} must be extended only by '
                'a named `sources` object'
            )

        old_sources = current.get('sources')
        if not isinstance(old_sources, dict):
            raise RuntimeError(
                f'{owner}: base concept {name!r} has no mergeable `sources` object'
            )

        merged = copy.deepcopy(current)
        sources = copy.deepcopy(old_sources)
        # Same intended precedence as ricu: extension source entries win.
        sources.update(copy.deepcopy(spec['sources']))
        merged['sources'] = sources
        base[name] = merged

    return base


def _build_ricu_dictionary(ro, out):
    # Load YAIB's ricu wrapper first so its pinned callback registration occurs.
    import src.ricu as yaib_ricu

    base_path = str(ro.r(
        'system.file("extdata", "config", "concept-dict.json", package="ricu")'
    )[0])
    if not base_path or not Path(base_path).is_file():
        raise RuntimeError(
            'Could not locate the pinned ricu base concept-dict.json: ' + base_path
        )

    merged = _json_object(base_path, 'ricu base concept dictionary')

    ext_root = Path(__file__).resolve().parents[1] / 'ricu-extensions' / 'configs'
    if not ext_root.is_dir():
        raise RuntimeError(f'YAIB extension config directory not found: {ext_root}')

    extension_files = sorted(ext_root.glob('*/concept-dict.json'))
    if not extension_files:
        raise RuntimeError(f'No YAIB concept-dict.json files found below {ext_root}')

    owners = {}
    for cfg in extension_files:
        patch = _json_object(cfg, 'YAIB extension concept dictionary')
        for concept_name in patch:
            owners.setdefault(concept_name, []).append(str(cfg.parent.name))
        _merge_extension(merged, patch, str(cfg))

    # Ambiguous duplicate ownership across separate YAIB extension folders would
    # make directory order scientifically meaningful, so do not silently invent it.
    duplicates = {k:v for k,v in owners.items() if len(v) > 1}
    if duplicates:
        sample = dict(list(sorted(duplicates.items()))[:10])
        raise RuntimeError(
            'YAIB concept names occur in multiple extension dictionaries; '
            f'review required before extraction. Examples: {sample}'
        )

    payload = json.dumps(
        merged, ensure_ascii=False, separators=(',', ':'), sort_keys=False
    )
    digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    cfg_dir = Path(out) / '_v9_ricu_dictionary'
    cfg_dir.mkdir(parents=True, exist_ok=True)
    merged_path = cfg_dir / 'concept-dict.full.json'
    merged_path.write_text(payload, encoding='utf-8')

    # Use the same pinned ricu parser that load_dictionary() ultimately calls.
    # Only read_dictionary()/get_config() multi-file merging is bypassed.
    parse_dictionary = ro.r(r"""
        function(path, src, concepts) {
            x <- jsonlite::read_json(
                path,
                simplifyVector = TRUE,
                simplifyDataFrame = FALSE,
                simplifyMatrix = FALSE
            )
            if (!is.list(x) || is.null(names(x))) {
                stop("V9 merged concept dictionary did not decode as a named list")
            }
            ricu:::parse_dictionary(x, src, concepts)
        }
    """)

    print(
        'V9_RICU_DICTIONARY_READY',
        f'concepts={len(merged)}',
        f'extensions={len(extension_files)}',
        f'sha256={digest[:16]}',
        flush=True
    )
    return yaib_ricu, parse_dictionary, merged_path


def _install_eicu_nested_dictionary_bridge(ro, merged_path):
    """Make eICU's nested default lookups use the same pinned merged dictionary.

    ricu's eICU ett_gcs callback uses fwd_concept('rass'), which re-enters
    load_dictionary() from inside R. Fixing steps.concepts alone does not cover
    that lookup. Leave load_dictionary(), its source-availability checks, the
    parser, callbacks, patient restriction and explicit custom dictionaries intact.
    """
    install = ro.r(r'''
        function(path) {
            ns <- asNamespace("ricu")
            original <- get("read_dictionary", envir = ns, inherits = FALSE)
            if (!identical(names(formals(original)), c("name", "cfg_dirs"))) {
                stop("V9 nested dictionary bridge: unexpected ricu reader signature")
            }
            full <- jsonlite::read_json(
                path, simplifyVector = TRUE,
                simplifyDataFrame = FALSE, simplifyMatrix = FALSE
            )
            if (!is.list(full) || is.null(names(full)) ||
                !all(c("rass", "sep3_alt") %in% names(full))) {
                stop("V9 nested dictionary bridge: incomplete merged dictionary")
            }
            replacement <- function(name, cfg_dirs = NULL) {
                if (identical(name, "concept-dict") && is.null(cfg_dirs)) {
                    return(full)
                }
                original(name = name, cfg_dirs = cfg_dirs)
            }
            attr(replacement, "v9_eicu_nested_dictionary") <- TRUE
            was_locked <- bindingIsLocked("read_dictionary", ns)
            if (was_locked) unlockBinding("read_dictionary", ns)
            assign("read_dictionary", replacement, envir = ns)
            if (was_locked) lockBinding("read_dictionary", ns)

            # Exercise the R-internal lookup used by fwd_concept('rass').
            # This parses definitions only; it does not load patient tables.
            probe <- ricu::load_dictionary(
                src = "eicu", concepts = c("rass", "sep3_alt")
            )
            if (!identical(names(probe), c("rass", "sep3_alt"))) {
                stop("V9 nested dictionary bridge: preflight lookup failed")
            }
            if (!identical(ricu:::read_dictionary("concept-dict"), full)) {
                stop("V9 nested dictionary bridge: namespace lookup differs")
            }
            message("V9_EICU_NESTED_DICTIONARY_OK concepts=", length(full))
            invisible(TRUE)
        }
    ''')
    install(str(merged_path))



def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['labels','cohort'],required=True)
    for name in ['src','ids','out','hospital-map']:p.add_argument('--'+name,required=name!='hospital-map')
    args=p.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    ids=[int(v) for v in json.loads(Path(args.ids).read_text())]
    if not ids:raise ValueError('Empty batch')

    # Select one source before ricu is imported.
    os.environ['RICU_SRC_LOAD'] = args.src

    # renv activation is essential when rpy2 embeds R rather than starting Rscript.
    import rpy2.robjects as ro
    ro.r('source("renv/activate.R"); data.table::setDTthreads(1L)')

    # ------------------------------------------------------------------
    # V9_RICU_INTERVAL_NAMESPACE_FIX
    #
    # ricu 0.6.x can infer a too-coarse interval from sparse multi-stay
    # vectors (e.g. 2 h although all timestamps lie on a 1 h grid).
    #
    # The original pinned ricu implementation is always attempted first.
    # Fallback is used ONLY for its specific interval-compatibility error,
    # changes no timestamps, and still requires ricu:::obeys_interval().
    # ------------------------------------------------------------------
    ro.r(r"""
        ns <- asNamespace("ricu")

        .v9_original_interval_difftime <-
            get("interval.difftime", envir = ns, inherits = FALSE)

        .v9_gcd2 <- function(a, b) {
            a <- abs(as.numeric(a))
            b <- abs(as.numeric(b))

            while (b > 0) {
                z <- b
                b <- a %% b
                a <- z
            }

            a
        }

        .v9_interval_difftime <- function(x) {

            tryCatch(

                .v9_original_interval_difftime(x),

                error = function(e) {

                    msg <- conditionMessage(e)

                    if (!grepl(
                        "not compatible with an interval",
                        msg,
                        fixed = TRUE
                    )) {
                        stop(e)
                    }

                    sec <- as.numeric(x, units = "secs")
                    sec <- sec[is.finite(sec)]

                    if (length(sec) < 2L) {
                        stop(e)
                    }

                    sec_int <- round(sec)

                    # Refuse fallback if timestamps are not exact to whole seconds.
                    if (any(abs(sec - sec_int) > 1e-6)) {
                        stop(e)
                    }

                    vals <- abs(sec_int[sec_int != 0])

                    if (!length(vals)) {
                        stop(e)
                    }

                    grid_sec <- Reduce(.v9_gcd2, vals)

                    if (!is.finite(grid_sec) || grid_sec <= 0) {
                        stop(e)
                    }

                    res <- as.difftime(grid_sec, units = "secs")
                    # Return the interval in the SAME units as the time column, exactly
                    # like ricu's interval.difftime(); a seconds-valued interval makes
                    # re_time()/sep3 windows convert some tables to secs and others not.
                    units(res) <- units(x)

                    # Preserve ricu's own compatibility criterion.
                    if (!isTRUE(ricu:::obeys_interval(x, res))) {
                        stop(e)
                    }

                    message(
                        "V9_INTERVAL_NAMESPACE_FALLBACK: ",
                        format(res),
                        " instead of sparse inferred interval"
                    )

                    res
                }
            )
        }

        # Replace the exact private namespace binding.
        was_locked <- bindingIsLocked("interval.difftime", ns)

        if (was_locked) {
            unlockBinding("interval.difftime", ns)
        }

        assign(
            "interval.difftime",
            .v9_interval_difftime,
            envir = ns
        )

        if (was_locked) {
            lockBinding("interval.difftime", ns)
        }

        # Keep S3 dispatch aligned with the namespace binding.
        registerS3method(
            "interval",
            "difftime",
            .v9_interval_difftime,
            envir = ns
        )

        # Regression self-test: sparse 1 h grid observed at 1,3,5 h.
        test_x <- as.difftime(c(1, 3, 5), units = "hours")

        test_res <- get(
            "interval.difftime",
            envir = ns,
            inherits = FALSE
        )(test_x)

        if (
            abs(
                as.numeric(test_res, units = "hours") - 1
            ) > 1e-12 ||
            !identical(units(test_res), "hours")
        ) {
            stop("V9 ricu interval namespace patch self-test failed")
        }

        message(
            "V9_INTERVAL_PATCH_SELFTEST_OK: ",
            format(test_res)
        )
    """)


    yaib_ricu, parse_dictionary, merged_dict_path = _build_ricu_dictionary(ro, out)
    if args.src == 'eicu':
        _install_eicu_nested_dictionary_bridge(ro, merged_dict_path)

    # Patch the symbol used by LoadStep.__init__, not the clinical loading logic.
    import src.steps as steps
    original_concepts = steps.concepts

    def v9_concepts(x, dict=None):
        if dict is not None:
            return original_concepts(x, dict=dict)
        names = [x] if isinstance(x, str) else list(x)
        if not names or not all(isinstance(v, str) for v in names):
            raise ValueError(f'Invalid concept request: {names!r}')
        print('V9_RICU_PARSE', args.src, ','.join(names), flush=True)
        return parse_dictionary(
            str(merged_dict_path),
            ro.StrVector([args.src]),
            ro.StrVector(names)
        )

    steps.concepts = v9_concepts
    LoadStep = steps.LoadStep

    original_init=LoadStep.__init__;original_do=LoadStep.do_perform
    def scoped_init(self,concept,src,cache=False,**kwargs):
        kwargs['patient_ids']=ro.IntVector(ids)
        original_init(self,concept,src,cache=cache,**kwargs)
        self._v9_names=[concept] if isinstance(concept,str) else list(concept)
    LoadStep.__init__=scoped_init

    def bounded_do(self,input):
        cached={'sep3_alt':'labels.parquet','hospital_id':'hospitals.parquet'}
        if args.mode=='cohort' and len(self._v9_names)==1 and self._v9_names[0] in cached:
            result=pd.read_parquet(out/cached[self._v9_names[0]])
        else:result=original_do(self,input)
        if 'stay_id' in result and not result.stay_id.isin(ids).all():
            raise RuntimeError('ricu patient_ids restriction was not respected; refusing an unbounded cohort.')
        return result
    LoadStep.do_perform=bounded_do

    if args.mode=='labels':
        kw={'si_mode':'abx'} if args.src=='eicu' else {}
        labels=LoadStep('sep3_alt',args.src,**kw).perform()
        hospitals=LoadStep('hospital_id',args.src).perform() if args.src=='eicu' else pd.DataFrame({'stay_id':ids,'hospital_id':'BIDMC'})
        labels.to_parquet(out/'labels.parquet',index=False);hospitals.to_parquet(out/'hospitals.parquet',index=False)
        positive=set(labels.loc[labels.sep3_alt.notna(),'stay_id'])
        hospitals['has_sepsis']=hospitals.stay_id.isin(positive)
        hospitals.groupby('hospital_id',dropna=False).has_sepsis.agg(['sum','count']).reset_index().to_csv(out/'hospital_counts.csv',index=False)
    else:
        import sepsis
        original_windows=sepsis.stay_windows
        def bounded_windows(src):
            d=original_windows(src);return d[d.stay_id.isin(ids)].copy()
        sepsis.stay_windows=bounded_windows
        class EmptySelectedBatch(Exception):
            def __init__(self,attrition):self.attrition=attrition
        original_select=sepsis.Cohort.select
        def checked_select(self,*a,**kw):
            selected,attrition=original_select(self,*a,**kw)
            if selected.empty:raise EmptySelectedBatch(attrition)
            return selected,attrition
        sepsis.Cohort.select=checked_select
        if args.src=='eicu':
            if not args.hospital_map:raise ValueError('Global eICU hospital prevalence is required')
            h=pd.read_csv(args.hospital_map,dtype={'hospital_id':str})
            prevalence=h.set_index('hospital_id').prevalence
            def global_prevalence(var):
                def calc(parts):
                    _,hospital=parts;hospital=hospital.copy()
                    hospital['prevalence']=hospital.hospital_id.astype(str).map(prevalence)
                    if hospital.prevalence.isna().any():raise ValueError('Hospital missing from global prepass')
                    return hospital[['stay_id','prevalence']]
                return calc
            sepsis.make_prevalence_calculator=global_prevalence
        try:(outc,dyn,sta),attrition=sepsis.create_sepsis_task(args)
        except EmptySelectedBatch as empty:
            attrition=empty.attrition
            outc=pd.DataFrame({k:pd.Series(dtype='int64') for k in ['stay_id','time','label']})
            dyn=outc[['stay_id','time']].copy()
            sta=pd.DataFrame({'stay_id':pd.Series(dtype='int64'),'age':pd.Series(dtype='float64'),
                'sex':pd.Series(dtype='str'),'height':pd.Series(dtype='float64'),'weight':pd.Series(dtype='float64')})
        for name,d in [('outc',outc),('sta',sta),('dyn',dyn[['stay_id','time']])]:
            d.to_parquet(out/(name+'.parquet'),index=False)
        attrition.to_csv(out/'attrition.csv',index=False)

    (out/(args.mode+'_complete.json')).write_text(json.dumps({'mode':args.mode,'count':len(ids)}))
    print('V9_BATCH_COMPLETE',args.src,args.mode,len(ids),flush=True)

if __name__=='__main__':main()
