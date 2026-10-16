"""Bounded subprocess runner and batch coordinator for low-memory Colab."""
from pathlib import Path
import os,sys,json,time,threading,subprocess,signal,gc,copy
import psutil
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import duckdb
from v9_data import table,q,signature,csv_scan

def prepare_import_config(baseline,roots,config_dir,target_rows=250000,legacy_logs=None):
    """Partition unfinished large WHOLE-TABLE imports by numeric patient ID.
    Preserve default partitions and already imported whole-table files. A saved
    config must also be supplied to every subsequent ricu loading subprocess.
    No source CSVs are edited and no rows are sampled for these imports.
    """
    config_dir=Path(config_dir);config_dir.mkdir(parents=True,exist_ok=True)
    target=config_dir/'data-sources.json'
    if target.is_file():return target,json.loads((config_dir/'partition_plan.json').read_text())
    source=json.loads(Path(baseline).read_text());configs=[];plan=[]
    con=duckdb.connect();con.execute("SET memory_limit='1GB'");con.execute('SET threads=1')
    try:
        for original in source:
            ds=original['name']
            if ds not in roots:continue
            cfg=copy.deepcopy(original);root=Path(roots[ds])
            for name,t in cfg['tables'].items():
                rawname=t.get('files')
                if not isinstance(rawname,str):continue
                stem=rawname[:-7] if rawname.endswith('.csv.gz') else rawname[:-4] if rawname.endswith('.csv') else rawname
                raw=table(root,stem)
                if raw is None:continue
                t['files']=str(raw.relative_to(root)) # support actual CSV/gzip and filename case
                already=(root/(name+'.fst')).is_file()
                oldlog=Path(legacy_logs)/f'ricu_import_{ds}_{name}.log' if legacy_logs else None
                if already and oldlog and oldlog.is_file() and 'RICU TABLE COMPLETE:' not in oldlog.read_text(errors='replace'):already=False
                large=(t.get('num_rows') or 0)>=2_000_000 or raw.stat().st_size>=128*1024**2
                if t.get('partitioning') or already or not large:continue
                key=next((k for k in ['subject_id','patientunitstayid','stay_id','hadm_id'] if k in t.get('cols',{})),None)
                if key is None:continue
                rawkey=t['cols'][key].get('name',key)
                if not re_identifier(rawkey):raise ValueError('Unexpected partition identifier')
                print(ds,name,': planning smaller disk partitions; scanning ID counts only',flush=True)
                counts=con.execute(f'SELECT TRY_CAST("{rawkey}" AS BIGINT) id,COUNT(*) n FROM {csv_scan(raw)} GROUP BY 1 ORDER BY 1').df()
                if counts.id.isna().any():raise ValueError(f'{ds}/{name}: missing/nonnumeric partition IDs require review; refusing to lose rows.')
                cumulative=counts.n.cumsum().to_numpy();total=int(cumulative[-1]) if len(counts) else 0
                positions=np.searchsorted(cumulative,np.arange(target_rows,total,target_rows))
                breaks=sorted(set(int(counts.id.iloc[i])+1 for i in positions if i<len(counts)-1))
                if not breaks:continue
                t['partitioning']={'col':key,'breaks':breaks}
                # Raw releases may differ from the historical source row count.
                t['num_rows']=total
                plan.append({'dataset':ds,'table':name,'column':key,'rows':total,
                    'partitions':len(breaks)+1,'target_rows':target_rows,'largest_patient_rows':int(counts.n.max())})
            configs.append(cfg)
        if {c['name'] for c in configs}!=set(roots):raise ValueError('Both source configurations are required')
        tmp=target.with_suffix('.partial.json');tmp.write_text(json.dumps(configs,indent=2))
        (config_dir/'partition_plan.json').write_text(json.dumps(plan,indent=2));os.replace(tmp,target)
    finally:con.close()
    return target,plan

def re_identifier(name):
    import re
    return bool(re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',name))

LAST_RUN={}  # wall time and peak machine RAM in use during the latest run_logged call
RUN_STATS={}  # the same, per log path (safe when batches run in parallel)
TIMING_LOCK=threading.Lock()
ACTIVE_PROCS=set()  # running subprocesses, stopped together if a parallel batch fails or is interrupted

def run_logged(cmd,log_path,cwd=None,env=None,reserve_gb=1.5):
    log_path=Path(log_path);log_path.parent.mkdir(parents=True,exist_ok=True)
    run_env=os.environ.copy();run_env.update({k:str(v) for k,v in (env or {}).items()})
    run_env.update({'MAKEFLAGS':'-j1','CMAKE_BUILD_PARALLEL_LEVEL':'1','OMP_NUM_THREADS':'1',
                    'OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','R_DATATABLE_NUM_THREADS':'1',
                    'RENV_CONFIG_INSTALL_PARALLEL':'FALSE'})
    print('Running:', ' '.join(map(str,cmd)),'\nLog:',log_path,flush=True)
    stopped=[];done=threading.Event();started=time.time();peak=[0.]
    with log_path.open('w') as f:
        proc=subprocess.Popen(list(map(str,cmd)),cwd=cwd,env=run_env,stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True)
        ACTIVE_PROCS.add(proc)
        def watch():
            while not done.wait(.5):
                vm=psutil.virtual_memory();peak[0]=max(peak[0],(vm.total-vm.available)/1024**3)
                if vm.available<reserve_gb*1024**3:
                    stopped.append(True)
                    try:os.killpg(proc.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                    if not done.wait(3):
                        try:os.killpg(proc.pid,signal.SIGKILL)
                        except ProcessLookupError:pass
                    return
        thread=threading.Thread(target=watch,daemon=True);thread.start();last=0.
        try:
            for line in proc.stdout:
                f.write(line);f.flush()
                if time.time()-last>10 or any(s in line for s in ['Error','ERROR','COMPLETE','Failed','Traceback']):
                    print(line.rstrip(),flush=True);last=time.time()
            rc=proc.wait()
        finally:done.set();thread.join(timeout=1);ACTIVE_PROCS.discard(proc)
    LAST_RUN.update(minutes=(time.time()-started)/60,peak_used_gb=peak[0])
    RUN_STATS[str(log_path)]=dict(LAST_RUN)
    if stopped:
        raise MemoryError('Stopped the subprocess to preserve Colab RAM. Completed batches remain saved. '
                          'Lower COHORT_BATCH_STAYS (e.g. 64 to 32) or R_IMPORT_CHUNK_ROWS, then rerun. Log: '+str(log_path))
    if rc:
        print('\n'.join(log_path.read_text(errors='replace').splitlines()[-60:]))
        raise RuntimeError(f'Subprocess failed ({rc}). See {log_path}')
    return log_path

def raw_ids(ds,root,smoke_n,seed):
    con=duckdb.connect();con.execute("SET memory_limit='1GB'");con.execute('SET threads=1')
    p=table(root,'icu/icustays' if ds=='miiv' else 'patient',True)
    col='stay_id' if ds=='miiv' else 'patientunitstayid'
    ids=con.execute(f'SELECT DISTINCT TRY_CAST({col} AS BIGINT) id FROM {csv_scan(p)} WHERE id IS NOT NULL ORDER BY id').df().id.to_numpy()
    con.close()
    if smoke_n and len(ids)>smoke_n:ids=np.sort(np.random.default_rng(seed).choice(ids,smoke_n,replace=False))
    return ids

def merge_parquets(paths,target):
    target=Path(target);tmp=target.with_suffix('.partial.parquet');writer=None
    try:
        for path in paths:
            pf=pq.ParquetFile(path)
            for batch in pf.iter_batches(batch_size=20000):
                import pyarrow as pa
                data=pa.Table.from_batches([batch]).replace_schema_metadata(None)
                if writer is None:writer=pq.ParquetWriter(tmp,data.schema,compression='zstd')
                writer.write_table(data.cast(writer.schema))
        if writer is None:
            # Every batch can be empty in a very small smoke cohort.
            first=pq.read_table(paths[0]).replace_schema_metadata(None)
            pq.write_table(first,tmp,compression='zstd')
        else:writer.close();writer=None
        os.replace(tmp,target)
    finally:
        if writer is not None:writer.close()

def stop_active():
    for proc in list(ACTIVE_PROCS):
        try:os.killpg(proc.pid,signal.SIGTERM)
        except ProcessLookupError:pass

def extract_cohort_batched(ds,root,output,worker,python,py_dir,env,batch_size=64,smoke_n=1200,seed=42,log_root=None,parallel=1):
    """Build the YAIB cohort in balanced, bounded subprocess batches.

    The original plan used fixed slices and could leave a very small final
    remainder (e.g. 140 -> 64+64+12). Recursive ricu concepts can become
    unstable on such sparse tail batches. The balanced plan keeps every batch
    <= batch_size while distributing stays as evenly as possible
    (e.g. 140 -> 47+47+46).

    Batch boundaries are computational only: no stay is duplicated, sampled
    away, or clinically redefined.
    """
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    batchroot=output/'batches';batchroot.mkdir(exist_ok=True)

    ids=np.asarray(raw_ids(ds,root,smoke_n,seed))

    if len(ids)==0:
        raise RuntimeError(f'{ds}: no candidate stays were found.')

    n_batches=max(1,int(np.ceil(len(ids)/batch_size)))
    chunks=[np.asarray(x,dtype=ids.dtype) for x in np.array_split(ids,n_batches) if len(x)]
    sizes=[int(len(x)) for x in chunks]

    if not sizes or max(sizes)>batch_size:
        raise RuntimeError(f'{ds}: invalid balanced batch plan: {sizes}')
    if sum(sizes)!=len(ids):
        raise RuntimeError(f'{ds}: balanced batching lost candidate stays.')

    reconstructed=np.concatenate(chunks)
    if len(reconstructed)!=len(ids) or set(reconstructed.tolist())!=set(ids.tolist()):
        raise RuntimeError(f'{ds}: balanced batch integrity check failed.')

    print(f'{ds}: balanced batch plan ({len(ids)} candidate stays): {sizes}',flush=True)

    # Strategy + exact sizes are part of the plan signature, so an old
    # 64+64+12 partial plan is never silently reused.
    plan=batchroot/signature({
        'ids':ids.tolist(),
        'batch_strategy':'balanced_v2',
        'max_batch_size':int(batch_size),
        'sizes':sizes
    })[:16]
    plan.mkdir(exist_ok=True)

    folders=[]
    for n,chunk in enumerate(chunks):
        p=plan/f'{n:05d}'
        p.mkdir(exist_ok=True)
        folders.append(p)
        (p/'ids.json').write_text(json.dumps([int(v) for v in chunk.tolist()]))

    for mode in ['labels','cohort']:

        if mode=='cohort':
            missing=[p for p in folders if not (p/'hospital_counts.csv').is_file()]
            if missing:
                raise RuntimeError(
                    f'{ds}: hospital counts missing before cohort phase: '
                    f'{[p.name for p in missing]}'
                )

            counts=pd.concat([
                pd.read_csv(p/'hospital_counts.csv',dtype={'hospital_id':str})
                for p in folders
            ],ignore_index=True)

            counts=counts.groupby('hospital_id',as_index=False)[['sum','count']].sum()
            counts['prevalence']=counts['sum']/counts['count']
            counts.to_csv(plan/'hospital_prevalence.csv',index=False)

        def run_batch(n,p):
            batch_ids=json.loads((p/'ids.json').read_text())
            print(f'{ds}: {mode} batch {n}/{len(folders)} ({len(batch_ids)} stays; {len(ids)} total candidates)',flush=True)
            cmd=[python,worker,'--mode',mode,'--src',ds,'--ids',p/'ids.json','--out',p]
            if mode=='cohort':cmd+=['--hospital-map',plan/'hospital_prevalence.csv']
            log=Path(log_root or output)/f'{ds}_{mode}_{n:05d}.log'
            run_logged(cmd,log,cwd=str(py_dir),env=env)
            # Timing record for planning full mode (aggregate only: counts, minutes, GB).
            st=RUN_STATS.get(str(log),{});timing=Path(log_root or output)/'batch_timing.csv'
            row=pd.DataFrame([{'finished':time.strftime('%Y-%m-%d %H:%M:%S'),'dataset':ds,'mode':mode,
                'batch':n,'batches':len(folders),'stays':len(batch_ids),'max_batch_size':int(batch_size),
                'minutes':round(st.get('minutes',float('nan')),2),'peak_ram_used_gb':round(st.get('peak_used_gb',float('nan')),1),
                'parallel_batches':workers,'data_root':str(root)}])
            with TIMING_LOCK:row.to_csv(timing,mode='a',header=not timing.is_file(),index=False)
            print(f"BATCH_TIMING {ds} {mode} {n}/{len(folders)}: {len(batch_ids)} stays, "
                  f"{st.get('minutes',0):.1f} min, peak RAM in use {st.get('peak_used_gb',0):.1f} GB",flush=True)
        pending=[]
        for n,p in enumerate(folders,1):
            if (p/(mode+'_complete.json')).is_file():print(f'{ds}: reuse completed {mode} batch {n}/{len(folders)}',flush=True)
            else:pending.append((n,p))
        # Batches are independent within a phase (each writes only its own folder), so they may run in
        # parallel. Capped by CPU count; the RAM watchdog in run_logged still guards every process.
        # ~16 GB headroom per batch (largest measured: eICU cohort, 500 stays, about 11-15 GB machine-wide).
        ram_cap=max(1,int(psutil.virtual_memory().available/1024**3//16))
        workers=max(1,min(int(parallel),len(pending) or 1,max(1,(os.cpu_count() or 2)-1),ram_cap))
        if workers>1:print(f'{ds}: {mode}: running up to {workers} batches in parallel (CPUs: {os.cpu_count()}, RAM cap: {ram_cap})',flush=True)
        if workers==1:
            for n,p in pending:run_batch(n,p);gc.collect()
        else:
            from concurrent.futures import ThreadPoolExecutor,as_completed
            pool=ThreadPoolExecutor(workers);futures=[]
            try:
                futures=[pool.submit(run_batch,n,p) for n,p in pending]
                for f in as_completed(futures):f.result()
            except BaseException:
                # One failure (or a manual interrupt) stops the others; completed batches stay saved.
                for f in futures:f.cancel()
                stop_active();raise
            finally:pool.shutdown(wait=True,cancel_futures=True)
            gc.collect()

    for name in ['outc','dyn','sta']:
        merge_parquets(
            [p/(name+'.parquet') for p in folders],
            output/(name+'.parquet')
        )

    pd.concat(
        [pd.read_csv(p/'attrition.csv').assign(batch=p.name) for p in folders],
        ignore_index=True
    ).to_csv(output/'attrition_by_batch.csv',index=False)

    (output/'batch_protocol.json').write_text(json.dumps({
        'batch_strategy':'balanced_v2',
        'maximum_batch_size':int(batch_size),
        'actual_batch_sizes':sizes,
        'candidate_stays':int(len(ids)),
        'smoke_sample_before_extraction':bool(smoke_n),
        'hospital_exclusion':'global across selected candidate population',
        'dynamic_grid_only':True
    },indent=2))
