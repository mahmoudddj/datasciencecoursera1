# 4b. Fast local copy of the raw data (Colab only; set LOCAL_DATA_COPY in Section 1).
# Reading the large tables through the Google Drive mount is slow. This copies both raw
# folders (CSV files plus the ricu .fst imports inside them) to Colab's local disk with their
# original timestamps, then checks that the copy is identical by the same fingerprints the
# cohort key and import markers use. Nothing is written back to Drive; outputs still go to PROJECT.
import os,shutil,time
from concurrent.futures import ThreadPoolExecutor
if DATA_SOURCE=='clinical' and LOCAL_DATA_COPY and MOUNT_GOOGLE_DRIVE:
    LOCAL_DATA_ROOT.mkdir(parents=True,exist_ok=True)
    def _copy_one(job):
        src,dst=job;st=src.stat()
        if dst.is_file():
            d=dst.stat()
            if d.st_size==st.st_size and d.st_mtime_ns==st.st_mtime_ns:return 0
        dst.parent.mkdir(parents=True,exist_ok=True)
        tmp=dst.with_name(dst.name+'.partial')
        shutil.copyfile(src,tmp);os.utime(tmp,ns=(st.st_atime_ns,st.st_mtime_ns));os.replace(tmp,dst)
        return st.st_size
    local_raw={}
    DRIVE_RAW_SOURCES={ds:Path(p) for ds,p in resolved_raw.items()}  # the locate cell re-resolves from these
    for ds in DATASETS:
        src_root=Path(resolved_raw[ds]);dst_root=LOCAL_DATA_ROOT/ds
        jobs=[(f,dst_root/f.relative_to(src_root)) for f in src_root.rglob('*') if f.is_file() and not f.name.endswith('.partial')]
        total=sum(f.stat().st_size for f,_ in jobs);need=sum(f.stat().st_size for f,d in jobs
            if not (d.is_file() and d.stat().st_size==f.stat().st_size and d.stat().st_mtime_ns==f.stat().st_mtime_ns))
        free=shutil.disk_usage(LOCAL_DATA_ROOT).free
        if need>free-20*1024**3:raise RuntimeError(f'{ds}: local copy needs {need/1e9:.0f} GB but only {free/1e9:.0f} GB free (keeping 20 GB spare).')
        print(f'{ds}: {len(jobs)} files, {total/1e9:.1f} GB; copying {need/1e9:.1f} GB to {dst_root}',flush=True)
        t0=time.time();done=0;next_report=5e9
        with ThreadPoolExecutor(8) as pool:
            for size in pool.map(_copy_one,jobs):
                done+=size
                if done>=next_report:print(f'  {done/1e9:.0f} GB copied ({(time.time()-t0)/60:.1f} min)',flush=True);next_report+=5e9
        # Same file set, sizes and timestamps; CSV fingerprints identical (cohort key / import markers unchanged).
        for f,d in jobs:
            if not d.is_file() or d.stat().st_size!=f.stat().st_size or d.stat().st_mtime_ns!=f.stat().st_mtime_ns:
                raise RuntimeError(f'{ds}: local copy differs for {f.relative_to(src_root)}; rerun this cell.')
        if fingerprint(dst_root)!=fingerprint(src_root):raise RuntimeError(f'{ds}: local CSV fingerprints differ from Drive; not using the copy.')
        print(f'{ds}: local copy verified ({(time.time()-t0)/60:.1f} min)',flush=True)
        local_raw[ds]=dst_root
    # Point this session (and the ricu data links) at the verified local copies.
    resolved_raw.update(local_raw)
    for ds,src in local_raw.items():
        link=RICU_MOUNT/ds
        if link.is_symlink():link.unlink()
        elif link.exists():raise RuntimeError(f'{link} is a real folder, not a link; refusing to replace it.')
        link.symlink_to(Path(src).resolve(),target_is_directory=True)
    print('Using local raw data for this session:',{k:str(v) for k,v in resolved_raw.items()})
else:
    print('Local data copy off: raw data is read from Google Drive.')
