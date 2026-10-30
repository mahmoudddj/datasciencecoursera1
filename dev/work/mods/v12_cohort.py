"""Stage-2 label and cohort extraction (protocol 10c.2 items 1, 10, 19) on top of v9_runtime.

extract_cohort_batched_v12 keeps the v9 batch plan, worker, memory watchdog and merge, and adds:
  * label-batch reuse: completed LABELS batches of an earlier plan (the 20,000 already-labelled candidates) are carried
    into the new plan as their own batches, so the pinned sep3 computation is not repeated for them; the COHORT phase
    runs again for every batch, because its criteria (exclusion 7 dropped) and the eICU hospital prevalence (now over
    the full release) differ from the earlier plan;
  * worker options through the environment: V12_SI_MODE (ricu sep3 si_mode for the sep3_alt load: 'abx' for the
    antibiotic-only MIMIC-IV label variant, 'and' for the culture-paired eICU variant) and V12_KEEP_EARLY_ONSET=1
    (YAIB exclusion 7, onset before ICU hour 6, is not applied; the stays are kept with their onset so the index can
    flag incident versus arrival sepsis). Without these variables the worker is the stage-1 worker.
cohort_index_v12 adds the Incident flag to the v9 cohort index.
"""
from pathlib import Path
import os,json,shutil,time,gc
import numpy as np
import pandas as pd
import psutil
from v9_data import signature
from v9_runtime import raw_ids,run_logged,merge_parquets,stop_active,RUN_STATS,TIMING_LOCK

LABEL_FILES=['labels.parquet','hospitals.parquet','hospital_counts.csv','labels_complete.json']

def completed_label_batches(previous_roots):
    """Folders of completed labels batches below the given cohort roots (.../sepsis/<ds>/batches/<plan>/<n>)."""
    out=[]
    for root in previous_roots or []:
        for p in sorted(Path(root).glob('batches/*/*')):
            if all((p/f).is_file() for f in LABEL_FILES) and (p/'ids.json').is_file():out.append(p)
    return out

def extract_cohort_batched_v12(ds,root,output,worker,python,py_dir,env,batch_size=500,smoke_n=None,seed=42,log_root=None,parallel=1,reuse_label_roots=None,phases=('labels','cohort')):
    """`phases`: ('labels','cohort') for a cohort; ('labels',) for a label variant whose onsets alone are needed."""
    output=Path(output);output.mkdir(parents=True,exist_ok=True);batchroot=output/'batches';batchroot.mkdir(exist_ok=True)
    ids=np.asarray(raw_ids(ds,root,smoke_n,seed))
    if len(ids)==0:raise RuntimeError(f'{ds}: no candidate stays were found.')
    wanted=set(int(v) for v in ids.tolist())
    # reusable label batches: whole batches whose every stay is a candidate here, no stay twice
    reused=[];covered=set()
    for p in completed_label_batches(reuse_label_roots):
        bid=[int(v) for v in json.loads((p/'ids.json').read_text())]
        if len(bid)<=batch_size and set(bid)<=wanted and not (set(bid)&covered):reused.append((p,bid));covered|=set(bid)
    remaining=np.asarray(sorted(wanted-covered),dtype=ids.dtype)
    n_new=max(1,int(np.ceil(len(remaining)/batch_size))) if len(remaining) else 0
    chunks=[np.asarray(x,dtype=ids.dtype) for x in np.array_split(remaining,n_new) if len(x)] if n_new else []
    sizes=[len(b) for _,b in reused]+[int(len(x)) for x in chunks]
    if sum(sizes)!=len(ids):raise RuntimeError(f'{ds}: batching lost candidate stays ({sum(sizes)} vs {len(ids)})')
    if sizes and max(sizes)>batch_size:raise RuntimeError(f'{ds}: a batch exceeds the maximum size: {max(sizes)}')
    plan=batchroot/signature({'ids':[int(v) for v in ids.tolist()],'batch_strategy':'v12_reuse_labels','max_batch_size':int(batch_size),'sizes':sizes,
        'reused':[str(p) for p,_ in reused],'env':{k:env.get(k) for k in ('V12_SI_MODE','V12_KEEP_EARLY_ONSET')}})[:16]
    plan.mkdir(exist_ok=True);folders=[]
    for n,(src,bid) in enumerate(reused):
        p=plan/f'{n:05d}';p.mkdir(exist_ok=True);folders.append(p)
        (p/'ids.json').write_text(json.dumps(bid))
        for f in LABEL_FILES:
            if not (p/f).is_file():shutil.copyfile(src/f,p/f)
        (p/'labels_reused_from.json').write_text(json.dumps({'source':str(src)}))
    for n,chunk in enumerate(chunks,start=len(reused)):
        p=plan/f'{n:05d}';p.mkdir(exist_ok=True);folders.append(p);(p/'ids.json').write_text(json.dumps([int(v) for v in chunk.tolist()]))
    print(f'{ds}: {len(ids)} candidate stays; {len(reused)} label batches reused ({len(covered)} stays), {len(chunks)} new batches of <= {batch_size}',flush=True)
    for mode in [m for m in ['labels','cohort'] if m in phases]:
        if mode=='cohort':
            missing=[p for p in folders if not (p/'hospital_counts.csv').is_file()]
            if missing:raise RuntimeError(f'{ds}: hospital counts missing before cohort phase: {[p.name for p in missing]}')
            counts=pd.concat([pd.read_csv(p/'hospital_counts.csv',dtype={'hospital_id':str}) for p in folders],ignore_index=True)
            counts=counts.groupby('hospital_id',as_index=False)[['sum','count']].sum();counts['prevalence']=counts['sum']/counts['count']
            counts.to_csv(plan/'hospital_prevalence.csv',index=False)
        def run_batch(n,p):
            batch_ids=json.loads((p/'ids.json').read_text())
            print(f'{ds}: {mode} batch {n}/{len(folders)} ({len(batch_ids)} stays)',flush=True)
            cmd=[python,worker,'--mode',mode,'--src',ds,'--ids',p/'ids.json','--out',p]
            if mode=='cohort':cmd+=['--hospital-map',plan/'hospital_prevalence.csv']
            log=Path(log_root or output)/f'{ds}_{mode}_{plan.name}_{n:05d}.log'
            run_logged(cmd,log,cwd=str(py_dir),env=env)
            st=RUN_STATS.get(str(log),{});timing=Path(log_root or output)/'batch_timing.csv'
            row=pd.DataFrame([{'finished':time.strftime('%Y-%m-%d %H:%M:%S'),'dataset':ds,'mode':mode,'batch':n,'batches':len(folders),'stays':len(batch_ids),
                'max_batch_size':int(batch_size),'minutes':round(st.get('minutes',float('nan')),2),'peak_ram_used_gb':round(st.get('peak_used_gb',float('nan')),1),'parallel_batches':workers,'data_root':str(root)}])
            with TIMING_LOCK:row.to_csv(timing,mode='a',header=not timing.is_file(),index=False)
        pending=[(n,p) for n,p in enumerate(folders,1) if not (p/(mode+'_complete.json')).is_file()]
        print(f'{ds}: {mode}: {len(folders)-len(pending)} batches complete, {len(pending)} pending',flush=True)
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
                for f in futures:f.cancel()
                stop_active();raise
            finally:pool.shutdown(wait=True,cancel_futures=True)
            gc.collect()
    if 'cohort' not in phases:
        (output/'labels_phase_complete.json').write_text(json.dumps({'batches':len(folders),'candidate_stays':int(len(ids))}));return
    for name in ['outc','dyn','sta']:merge_parquets([p/(name+'.parquet') for p in folders],output/(name+'.parquet'))
    pd.concat([pd.read_csv(p/'attrition.csv').assign(batch=p.name) for p in folders],ignore_index=True).to_csv(output/'attrition_by_batch.csv',index=False)
    (output/'batch_protocol.json').write_text(json.dumps({'batch_strategy':'v12_reuse_labels','maximum_batch_size':int(batch_size),'actual_batch_sizes':sizes,'candidate_stays':int(len(ids)),
        'reused_label_batches':len(reused),'reused_label_stays':len(covered),'smoke_sample_before_extraction':bool(smoke_n),'si_mode':env.get('V12_SI_MODE','pinned default'),
        'early_onset_kept':env.get('V12_KEEP_EARLY_ONSET')=='1','hospital_exclusion':'global across selected candidate population','dynamic_grid_only':True},indent=2))

def cohort_index_v12(folder,smoke_n,seed,early_onset_hours=6.):
    """v9 cohort index plus Incident (no onset, or onset at or after ICU hour `early_onset_hours`) and ArrivalSepsis
    (onset before that hour; YAIB exclusion 7 would have removed these stays)."""
    from v9_data import cohort_index
    z=cohort_index(folder,smoke_n,seed)
    z['ArrivalSepsis']=(z.OnsetHour.notna()&(z.OnsetHour<early_onset_hours)).astype(int);z['Incident']=(1-z.ArrivalSepsis).astype(int)
    return z
