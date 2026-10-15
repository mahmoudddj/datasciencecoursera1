# 4. Import each missing raw source into ricu — table-by-table, resume-safe
#
# Full MIMIC-IV/eICU imports are long and resource-intensive. Importing one table
# per fresh R process makes this much more robust in Colab: completed tables are
# reused, memory is released between tables, and any failure is attributed to one
# exact table.

import os
import signal
import shutil
import subprocess
from pathlib import Path

if need_extract:
    config_root=PROJECT/'ricu_partition_config_v9'/signature({'raw':RAW_FINGERPRINTS,'target':R_IMPORT_PARTITION_ROWS})[:16]
    probe=subprocess.check_output([str(YAIB_RSCRIPT),'--vanilla','-e',
        'source("renv/activate.R"); cat("__CONFIG__=", system.file("extdata/config/data-sources.json",package="ricu"),sep="")'],
        cwd=str(COHORT_REPO/'Python'),env=YAIB_RUNTIME_ENV,text=True)
    baseline=Path(probe.split('__CONFIG__=',1)[1].splitlines()[0].strip())
    config_file,partition_plan=prepare_import_config(baseline,resolved_raw,config_root,
        target_rows=R_IMPORT_PARTITION_ROWS,legacy_logs=PROJECT/'pipeline_logs_rich_v1')
    YAIB_RUNTIME_ENV['RICU_CONFIG_PATH']=str(config_root)
    partition_tables={row['dataset']+'|'+row['table'] for row in partition_plan}
    display(pd.DataFrame(partition_plan))
    py_dir = COHORT_REPO / 'Python'
    config_path = COHORT_REPO / 'config.yaml'
    config_text = (
        f'ricu_data_path: "{RICU_MOUNT}"\n'
        f'out_dir: "{COHORT_BASE}"\n'
    )
    config_path.write_text(config_text)
    print('YAIB config.yaml:')
    print(config_text)

    # Use the exact R 4.2.2 interpreter created in Section 4A.
    if 'YAIB_RSCRIPT' not in globals():
        raise RuntimeError('YAIB_RSCRIPT is missing. Run Section 4A first.')
    YAIB_RSCRIPT = Path(YAIB_RSCRIPT)
    if not YAIB_RSCRIPT.is_file():
        raise FileNotFoundError(f'Pinned YAIB Rscript not found: {YAIB_RSCRIPT}')

    print('Pinned Rscript:', YAIB_RSCRIPT)
    r_ver = subprocess.check_output(
        [str(YAIB_RSCRIPT), '--vanilla', '-e', 'cat(R.version.string)'],
        text=True,
        env=YAIB_RUNTIME_ENV,
    ).strip()
    print('Cell 4 R:', r_ver)
    if '4.2.2' not in r_ver:
        raise RuntimeError(f'Cell 4 must use R 4.2.2, got: {r_ver}')

    def _disk_snapshot(path):
        try:
            total, used, free = shutil.disk_usage(path)
            return {
                'path': str(path),
                'total_GB': round(total / 1024**3, 1),
                'used_GB': round(used / 1024**3, 1),
                'free_GB': round(free / 1024**3, 1),
            }
        except Exception as exc:
            return {'path': str(path), 'error': repr(exc)}

    print('Local disk:', _disk_snapshot('/content'))
    print('Drive disk:', _disk_snapshot('/content/drive/MyDrive'))

    # Carry the pinned conda/R/compiler environment from Section 4A forward.
    import_env = YAIB_RUNTIME_ENV.copy()
    import_env.update({
        'RICU_DATA_PATH': str(RICU_MOUNT),
        'RICU_SRC_LOAD': '',
        'RENV_PATHS_CACHE': str(PROJECT / 'renv_cache_r422_unified'),
        'PIP_CACHE_DIR': str(PROJECT / 'pip_cache'),
        'OMP_NUM_THREADS': '1',
        'OPENBLAS_NUM_THREADS': '1',
        'MKL_NUM_THREADS': '1',
        'VECLIB_MAXIMUM_THREADS': '1',
        'NUMEXPR_NUM_THREADS': '1',
        'R_IMPORT_CHUNK_ROWS': str(R_IMPORT_CHUNK_ROWS),
        'R_DATATABLE_NUM_THREADS': '1',
    })

    # Activate the exact YAIB renv project restored in Section 4A and expose its
    # project library to every later R / rpy2 subprocess.
    activate_script = py_dir / 'renv' / 'activate.R'
    if not activate_script.is_file():
        raise FileNotFoundError(f'YAIB renv activation script missing: {activate_script}')

    lib_probe = subprocess.run(
        [
            str(YAIB_RSCRIPT), '--vanilla', '-e',
            'source("renv/activate.R"); cat("__YAIB_LIB__=", .libPaths()[1], sep="")'
        ],
        cwd=str(py_dir),
        env=import_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if lib_probe.returncode != 0 or '__YAIB_LIB__=' not in lib_probe.stdout:
        print(lib_probe.stdout)
        raise RuntimeError('Could not activate YAIB renv project library in Cell 4')
    YAIB_R_LIB = lib_probe.stdout.split('__YAIB_LIB__=', 1)[1].splitlines()[0].strip()
    if not Path(YAIB_R_LIB).is_dir():
        raise FileNotFoundError(f'YAIB renv project library not found: {YAIB_R_LIB}')
    import_env['R_LIBS_USER'] = YAIB_R_LIB
    import_env['RENV_PROJECT'] = str(py_dir)
    YAIB_RUNTIME_ENV.update({'R_LIBS_USER':YAIB_R_LIB,'RENV_PROJECT':str(py_dir)})
    print('YAIB renv project library:', YAIB_R_LIB)

    # R helper: activate renv, then list configured tables, import exactly one table, or validate source.
    r_script = py_dir / 'import_raw_to_ricu_one_table.R'
    r_script.write_text(r'''args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2L) stop("Usage: script <src> <mode/table> [force]")

src <- args[[1L]]
mode <- args[[2L]]
force_flag <- if (length(args) >= 3L) identical(args[[3L]], "TRUE") else FALSE

data_root <- Sys.getenv("RICU_DATA_PATH")
if (identical(data_root, "")) stop("RICU_DATA_PATH is empty")
Sys.setenv(RICU_SRC_LOAD = "")

activate <- file.path(getwd(), "renv", "activate.R")
if (!file.exists(activate)) stop(paste("Missing renv activation script:", activate))
source(activate)

suppressPackageStartupMessages(library(ricu))

dd <- file.path(data_root, src)
if (!dir.exists(dd)) stop(paste("Missing data directory", dd))

if (identical(mode, "__LIST__")) {
    cfgs <- load_src_cfg(src)
    cfg <- cfgs[[src]]
    if (is.null(cfg)) stop(paste("No ricu source configuration for", src))
    tbls <- names(as_tbl_cfg(cfg))
    cat(paste(tbls, collapse = "\n"), "\n", sep = "")
    quit(save = "no", status = 0L)
}

if (identical(mode, "__VALIDATE__")) {
    # RICU_SRC_LOAD is deliberately empty in this helper, so src_data_avail()
    # MUST receive the source explicitly.  Calling it with no argument makes
    # it use auto_attach_srcs(), which is character(0) here and returns NULL.
    attach_src(src, data_dir = dd)
    status <- src_data_avail(src)
    print(status)
    row <- status[status$name == src, , drop = FALSE]
    if (nrow(row) != 1L || !isTRUE(row$available[[1L]])) {
        stop(paste(
            "ricu import did not make", src, "fully available:",
            if (nrow(row) == 1L) paste0(row$tables[[1L]], "/", row$total[[1L]], " tables available")
            else "source absent from availability report"
        ))
    }
    cat("RICU IMPORT COMPLETE:", src, "\n")
    quit(save = "no", status = 0L)
}

cat("SOURCE:", src, "\n")
cat("TABLE:", mode, "\n")
cat("DATA DIRECTORY:", dd, "\n")

# Dispatch on src_cfg: import_src.character does not forward chunk_length
# to the table importer in the pinned ricu version.
cfg <- load_src_cfg(src)[[src]]
tbl <- as_tbl_cfg(cfg)[mode]
chunk_rows <- as.integer(Sys.getenv("R_IMPORT_CHUNK_ROWS", "250000"))
stopifnot(!is.na(chunk_rows), chunk_rows >= 1000L)
data.table::setDTthreads(1L)
if (requireNamespace("fst", quietly=TRUE)) fst::threads_fst(1L)
kwargs <- list(x=cfg, data_dir=dd, tables=mode, force=force_flag,
               verbose=TRUE, cleanup=FALSE)
if (ricu:::n_part(tbl) > 1L) kwargs$chunk_length <- chunk_rows
cat("CSV chunk rows for partitioned tables:", chunk_rows, "\n")
do.call(import_src, kwargs)


gc(verbose = FALSE)
cat("RICU TABLE COMPLETE:", src, mode, "\n")
''')

    def _run_table_logged(cmd,log_name,cwd=None,env=None):
        return guarded_run(cmd,LOG_ROOT/log_name,cwd=cwd,env=env)

    def _validate_ricu_source(ds):
        return _run_table_logged(
            [str(YAIB_RSCRIPT), '--vanilla', str(r_script), ds, '__VALIDATE__', 'FALSE'],
            f'ricu_import_{ds}_validate.log',
            cwd=py_dir,
            env=import_env,
        )

    def _table_import_fingerprint(ds, table):
        return signature({
            'raw': {
                k: v for k, v in RAW_FINGERPRINTS[ds].items()
                if Path(k).name.lower() in {table.lower()+'.csv', table.lower()+'.csv.gz'}
            },
            'config': json.loads(config_file.read_text())
        })

    def _configured_tables(ds):
        proc = subprocess.run(
            [str(YAIB_RSCRIPT), '--vanilla', str(r_script), ds, '__LIST__', 'FALSE'],
            cwd=str(py_dir),
            env=import_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            print(proc.stdout)
            print(proc.stderr)
            raise RuntimeError(f'Could not list ricu tables for {ds}')
        tbls = [x.strip() for x in proc.stdout.splitlines() if x.strip()]
        tbls = [x for x in tbls if ' ' not in x and not x.startswith('──')]
        if not tbls:
            raise RuntimeError(f'No configured ricu tables discovered for {ds}')
        return tbls

    # Put the biggest tables last so progress is saved before resource-heavy work.
    heavy_last = [
        'chartevents', 'labevents', 'emar', 'emar_detail',
        'microbiologyevents', 'prescriptions', 'poe', 'poe_detail',
        'inputevents', 'outputevents', 'procedureevents',
        'vitalperiodic', 'nursecharting', 'medication',
    ]

    for ds in YAIB_DATASETS:
        if cohort_complete(ds) and not FORCE_YAIB_REEXTRACT:
            print(ds, ': cohort already complete; ricu import skipped')
            continue
        if ds not in resolved_raw:
            raise FileNotFoundError(f'{ds}: raw source was not resolved')

        tables = _configured_tables(ds)
        rank = {name: i for i, name in enumerate(heavy_last)}
        tables = sorted(tables, key=lambda x: (x.lower() in rank, rank.get(x.lower(), -1)))

        # Fast resume after a crash in source-level validation.  If every table
        # marker is complete and bound to the current raw/config fingerprint,
        # validate the existing ricu source first.  A successful validation
        # avoids launching all per-table R subprocesses again.
        current_markers = True
        if not FORCE_RICU_REIMPORT:
            for table in tables:
                marker = PROJECT/'ricu_import_status_v9'/ds/(table+'.json')
                fp = _table_import_fingerprint(ds, table)
                previous = json.loads(marker.read_text()) if marker.is_file() else None
                if not (previous and previous.get('status') == 'complete' and previous.get('source') == fp):
                    current_markers = False
                    break
        else:
            current_markers = False

        if current_markers:
            print(f'{ds}: all table markers are current; validating existing ricu source before any re-import')
            try:
                _validate_ricu_source(ds)
            except RuntimeError:
                print(f'{ds}: source validation failed despite current markers; falling back to per-table ricu checks')
            else:
                print(f'{ds}: existing ricu import validated; per-table import loop skipped')
                continue

        print('\n' + '=' * 78)
        print(f'{ds.upper()} — {len(tables)} configured ricu tables')
        print('=' * 78)
        print(', '.join(tables))

        # V10: name the tables that actually need a (re)import and require explicit consent.
        def _needs_import(table):
            marker=PROJECT/'ricu_import_status_v9'/ds/(table+'.json')
            prev=json.loads(marker.read_text()) if marker.is_file() else None
            return bool(FORCE_RICU_REIMPORT or not prev or prev.get('status')!='complete' or prev.get('source')!=_table_import_fingerprint(ds,table))
        pending=[t for t in tables if _needs_import(t)]
        print(f'{ds}: tables needing ricu (re)import: {pending or "none (only verification)"}')
        if pending and not globals().get('ALLOW_FULL_RAW_IMPORT',False):
            raise RuntimeError(f'{ds}: {len(pending)} ricu table(s) are new or changed since their last verified import: {pending}. '
                'Re-importing them reads those WHOLE raw tables once (large tables such as chartevents take hours). '
                'Set ALLOW_FULL_RAW_IMPORT=True in Section 1 and rerun from the top; already verified tables are reused.')
        for i, table in enumerate(tables, 1):
            print('\n' + '-' * 78)
            print(f'{ds}: table {i}/{len(tables)} — {table}')
            print('-' * 78)
            # Completion records bind each table to the selected CSV fingerprints.
            marker=PROJECT/'ricu_import_status_v9'/ds/(table+'.json')
            marker.parent.mkdir(parents=True,exist_ok=True)
            table_fp=_table_import_fingerprint(ds, table)
            previous=json.loads(marker.read_text()) if marker.is_file() else None
            # Logs from the old Cell 4 identify interrupted imports without rerunning successful tables.
            oldlog=PROJECT/'pipeline_logs_rich_v1'/f'ricu_import_{ds}_{table}.log'
            old_incomplete=previous is None and oldlog.is_file() and 'RICU TABLE COMPLETE:' not in oldlog.read_text(errors='replace')
            retry=bool(FORCE_RICU_REIMPORT or old_incomplete or
                       (previous and (previous.get('status')!='complete' or previous.get('source')!=table_fp)))
            atomic_json(marker,{'status':'started','source':table_fp,'table':table})
            _run_table_logged(
                [
                    str(YAIB_RSCRIPT), '--vanilla', str(r_script),
                    ds, table, str(retry).upper()
                ],
                f'ricu_import_{ds}_{table}.log',
                cwd=py_dir,
                env=import_env,
            )
            atomic_json(marker,{'status':'complete','source':table_fp,'table':table})

        _validate_ricu_source(ds)

else:
    print('ricu import skipped because all cohorts already exist.')