"""Release and import-status preflight, run BEFORE cohort keys, environment setup or imports.

Read-only: it counts ICU stays in the stay table and lists existing ricu .fst files and
import markers. It never imports, extracts or modifies data.
"""
from pathlib import Path
import json,shutil

# Stay-table sizes of the PhysioNet demo releases (MIMIC-IV Clinical Database Demo:
# 100 patients / 140 ICU stays; eICU-CRD Demo: 2,520 unit stays).
KNOWN_DEMO_STAYS={'miiv':140,'eicu':2520}
# Full releases are far larger (MIMIC-IV v2.2 ~73k, v3.x ~94k ICU stays; eICU-CRD 200,859).
MIN_FULL_STAYS={'miiv':50000,'eicu':150000}
FULL_NAMES={'miiv':'MIMIC-IV','eicu':'eICU-CRD'}

# Conservative lower bounds (bytes, gzip) for core tables of the FULL releases; uncompressed
# CSVs are larger, so they pass too. Demo files are 100-1000x smaller. Observed full sizes
# (MIMIC-IV 3.1 / eICU-CRD 2.0) are well above these limits.
FULL_MIN_BYTES={
 'miiv':{'icu/icustays':1_000_000,'icu/chartevents':1_000_000_000,'hosp/patients':500_000,'hosp/admissions':5_000_000,
         'hosp/labevents':500_000_000,'icu/outputevents':10_000_000,'icu/inputevents':100_000_000},
 'eicu':{'patient':2_000_000,'vitalPeriodic':500_000_000,'lab':100_000_000,'intakeOutput':50_000_000,'nurseCharting':500_000_000}}

def table_sizes(ds,root):
    """Per-file size audit of core raw tables (names/sizes only; no records read)."""
    from v9_data import table
    rows=[]
    for stem,minimum in FULL_MIN_BYTES[ds].items():
        p=table(root,stem);size=p.stat().st_size if p else None
        rows.append({'dataset':ds,'table':stem,'file':str(p) if p else None,'MB':None if size is None else round(size/1e6,2),
                     'full_release_min_MB':minimum/1e6,'status':'missing' if p is None else ('ok' if size>=minimum else 'DEMO-SIZED')})
    return rows

def check_files(paths,allow_demo=False,mode='smoke'):
    """Refuse folders mixing full-release and demo-sized core tables (always), and fully
    demo-sized folders unless ALLOW_DEMO_DATA in smoke. Returns the audit rows."""
    rows=[r for ds,root in paths.items() for r in table_sizes(ds,root)]
    msgs=[]
    for ds in paths:
        mine=[r for r in rows if r['dataset']==ds and r['status']!='missing'];small=[r for r in mine if r['status']=='DEMO-SIZED']
        if not small:continue
        listing='\n'.join(f"    {r['file']}  ({r['MB']} MB; full release >= {r['full_release_min_MB']:g} MB)" for r in small)
        if len(small)<len(mine):
            msgs.append(f"{ds}: MIXED folder — these core tables are demo-sized while others are full-size:\n{listing}\n"
                        f"  Fix in one step: set REPAIR_FROM_PHYSIONET=True and PHYSIONET_USERNAME in Section 1 and rerun; the notebook downloads\n"
                        f"  these files from PhysioNet, verifies their official SHA-256 and quarantines the demo copies.\n"
                        f"  (Or replace them manually with the full {FULL_NAMES[ds]} files, same names and subfolders.)")
        elif not (allow_demo and mode=='smoke'):
            msgs.append(f"{ds}: every core table is demo-sized (demo release):\n{listing}")
    if msgs:
        raise ValueError('Raw files are not a consistent full release:\n'+'\n'.join(msgs)+
            '\nNothing was imported or extracted. After replacing files, rerun from the top: the changed tables are detected by '
            'their fingerprints and only those tables are re-imported into ricu (requires ALLOW_FULL_RAW_IMPORT=True).')
    return rows

def check_release(counts,paths,allow_demo=False,mode='smoke'):
    """Stop on a demo/partial release unless demo data were explicitly allowed (smoke only)."""
    problems=[];notes=[]
    for ds,n in counts.items():
        name=FULL_NAMES.get(ds,ds)
        if n==KNOWN_DEMO_STAYS.get(ds):
            msg=(f"{ds}: {paths.get(ds)} contains {n:,} ICU stays — exactly the {name} DEMO release, not the full database "
                 f"(full release: {MIN_FULL_STAYS[ds]:,}+ stays).")
        elif n<MIN_FULL_STAYS.get(ds,0):
            msg=f"{ds}: {paths.get(ds)} contains only {n:,} ICU stays; a full {name} release has {MIN_FULL_STAYS[ds]:,}+ (partial copy or demo?)."
        else:
            notes.append(f"{ds}: {n:,} ICU stays (consistent with the full {name} release)");continue
        if allow_demo and mode=='smoke':notes.append(msg+' Continuing only because ALLOW_DEMO_DATA=True (engineering smoke; never study results).')
        else:problems.append(msg)
    if problems:
        raise ValueError('Raw source is not a full release:\n  '+'\n  '.join(problems)+
            "\nSet RAW_SOURCE_PATHS[...] in Section 1 to the FULL release folder (MIMIC-IV: the folder containing hosp/ and icu/;"
            " eICU: the folder containing patient.csv.gz), then rerun from the top. Nothing was imported or extracted.")
    return notes

def ricu_status(ds,raw_root,project):
    """What ricu import work already exists for this source (read-only)."""
    root=Path(raw_root)
    fst=sorted(str(p.relative_to(root)) for p in list(root.glob('*.fst'))+list(root.glob('*/*.fst'))) if root.is_dir() else []
    markers=sorted((Path(project)/'ricu_import_status_v9'/ds).glob('*.json'))
    states=[json.loads(m.read_text()).get('status') for m in markers]
    return {'fst_files':len(fst),'tables_with_fst':len({f.split('/')[0].removesuffix('.fst') for f in fst}),
            'import_markers_complete':states.count('complete'),'import_markers_started_only':states.count('started')}

def gate_report(datasets,raw,project,cohort_complete):
    rows=[];todo=[]
    for ds in datasets:
        s=ricu_status(ds,raw[ds],project);done=cohort_complete(ds)
        if done:step='cohort complete -> reused (no import needed)'
        elif s['fst_files']:step=(f"ricu import partly/fully present ({s['tables_with_fst']} tables imported, {s['import_markers_complete']} verified markers);"
                                  " remaining tables are imported, existing ones reused; then smoke-capped label extraction")
        else:step='no ricu import yet -> one-time WHOLE-TABLE import of this database, then smoke-capped label extraction'
        rows.append({'dataset':ds,'cohort_complete':done,**s,'next_step':step})
        if not done:todo.append(ds)
    try:
        u=shutil.disk_usage(Path(raw[todo[0]]) if todo else Path(project));free=round(u.free/1024**3,1)
    except Exception:free=None
    return rows,todo,free

PHYSIONET_BASE={'miiv':'https://physionet.org/files/mimiciv/{version}/','eicu':'https://physionet.org/files/eicu-crd/{version}/'}

def _open(url,user,password,start=0):
    import urllib.request,base64
    req=urllib.request.Request(url,headers={'User-Agent':'Wget/1.21','Authorization':'Basic '+base64.b64encode(f'{user}:{password}'.encode()).decode()})
    if start:req.add_header('Range',f'bytes={start}-')
    return urllib.request.urlopen(req,timeout=120)

def repair_from_physionet(ds,root,user,password,version='3.1',stems=None,base=None,log=print):
    """Replace demo-sized core tables with the official full files from PhysioNet.

    Downloads with YOUR credentials (resumable), verifies SHA-256 against the release's
    SHA256SUMS.txt, then swaps the file in atomically. Replaced demo copies are MOVED to
    <root>/_quarantined_demo_files/, never deleted. Returns a list of actions.
    """
    import hashlib,os,shutil
    from v9_data import table
    root=Path(root);base=(base or PHYSIONET_BASE[ds]).format(version=version)
    stems=stems or [r['table'] for r in table_sizes(ds,root) if r['status']=='DEMO-SIZED']
    if not stems:log(f'{ds}: no demo-sized core tables; nothing to repair.');return []
    with _open(base+'SHA256SUMS.txt',user,password) as r:sums=dict(reversed(l.split(None,1)) for l in r.read().decode().splitlines() if l.strip())
    sums={k.strip().lstrip('*'):v for k,v in sums.items()}
    actions=[];quarantine=root/'_quarantined_demo_files'
    for stem in stems:
        rel=stem+'.csv.gz'
        if rel not in sums:raise ValueError(f'{rel} is not listed in PhysioNet SHA256SUMS for version {version}')
        dest=root/rel;part=dest.with_name(dest.name+'.partial');dest.parent.mkdir(parents=True,exist_ok=True)
        start=part.stat().st_size if part.exists() else 0
        log(f'{ds}: downloading {rel} from PhysioNet'+(f' (resuming at {start/1e6:.0f} MB)' if start else ''))
        with _open(base+rel,user,password,start) as r:
            if start and getattr(r,'status',200)!=206:start=0
            total=start+int(r.headers.get('Content-Length') or 0)
            with open(part,'ab' if start else 'wb') as f:
                done=start;last=0
                try:
                    while True:
                        b=r.read(8*1024*1024)
                        if not b:break
                        f.write(b);done+=len(b)
                        if done-last>=500*1024*1024:log(f'   {done/1e9:.1f} GB');last=done
                except Exception as e:
                    raise IOError(f'{rel}: connection dropped at {done/1e6:.0f} MB ({e}); the partial file is kept — rerun this cell to resume.')
            if total and done<total:raise IOError(f'{rel}: received {done/1e6:.0f} of {total/1e6:.0f} MB; partial file kept — rerun this cell to resume.')
        h=hashlib.sha256()
        with open(part,'rb') as f:
            for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
        if h.hexdigest()!=sums[rel]:
            part.unlink();raise ValueError(f'{rel}: SHA-256 mismatch after download; partial file removed, rerun to retry.')
        old=table(root,stem)
        if old is not None and old.exists():
            q=quarantine/stem;q.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(old),str(q.parent/old.name))
        os.replace(part,dest)
        actions.append({'dataset':ds,'table':stem,'bytes':dest.stat().st_size,'sha256':sums[rel],'quarantined_old_file':str(old) if old else None})
        log(f'{ds}: {rel} replaced and verified ({dest.stat().st_size/1e6:.1f} MB).')
    return actions
