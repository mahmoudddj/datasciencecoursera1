# Usage: python3 -I dev/tools/check_extraction_pending.py <notebook.ipynb>   (no data, no R; stubbed files in a temp folder)
"""Replays cells 8 (tail), 4a need_extract, 4 (ricu skip) and 4d of the rebuilt notebook on stub state; no R, no data."""
import json,ast,sys,types,shutil,tempfile,gc,io,contextlib,re
from pathlib import Path
import pandas as pd
R=Path('/home/user/datasciencecoursera1');sys.path.insert(0,str(R/'dev/work/mods'))
from v9_data import signature,hour_values
NB=sys.argv[1]
nb=json.load(open(R/NB));cells=nb['cells']
def src(i):return ''.join(cells[i]['source'])
s3=src(3).splitlines();emb=ast.literal_eval([l for l in s3 if l.startswith('EMBEDDED_MODULES = ')][0][len('EMBEDDED_MODULES = '):])
import gzip,base64
mod=lambda n:gzip.decompress(base64.b64decode(emb[n]['data'])).decode()
c8=src(8);tail=c8[c8.index('# ---- Stage 2: what still needs the YAIB'):]
envsetup=mod('v9_environment_setup.py');need_src=envsetup[envsetup.index('# Stage 2 (2 Nov 2026)'):envsetup.index('print("Need YAIB extraction:", need_extract)')]
rawimp=mod('v9_raw_import.py');m=re.search(r"\n        _pending = .*\n        if not _pending\(ds\):\n",rawimp);assert m
skip_src="skipped=[]\nfor ds in YAIB_DATASETS:\n"+m.group(0).lstrip('\n')+"            skipped.append(ds); continue\n"
c12=src(12)
calls=[]
def fake_extract(ds,raw,out,worker,py,py_dir,env,**kw):
    calls.append({'ds':ds,'out':str(out),'phases':kw.get('phases',('labels','cohort')),'si':env.get('V12_SI_MODE'),'early':env.get('V12_KEEP_EARLY_ONSET'),'worker_exists':Path(worker).is_file()})
    b=Path(out)/'batches'/'plan'/'00000';b.mkdir(parents=True,exist_ok=True)
    if 'cohort' in kw.get('phases',('labels','cohort')):
        for n in ['dyn.parquet','sta.parquet','outc.parquet']:(Path(out)/n).write_text('x')
    pd.DataFrame({'stay_id':[1,1,2,3],'time':pd.to_timedelta([5,7,None,9],unit='h'),'sep3_alt':[True,True,None,True]}).to_parquet(b/'labels.parquet')
sys.modules['v12_cohort']=types.SimpleNamespace(extract_cohort_batched_v12=fake_extract)
def scenario(name,cohorts_done,variants_done,env_ready,variants={'miiv':'abx','eicu':'and'},force=False,expect_error=False,done_only=None):
    calls.clear();tmp=Path(tempfile.mkdtemp());PROJECT=tmp/'proj';COHORT_KEY='e2dbca97e122e6bc'
    COHORT_ROOT=PROJECT/'cohorts_v9'/COHORT_KEY/'sepsis';CODE_DIR=tmp/'code';CODE_DIR.mkdir(parents=True);(CODE_DIR/'v9_yaib_worker.py').write_text('# worker')
    for ds in ['miiv','eicu']:
        if cohorts_done:
            f=COHORT_ROOT/ds;f.mkdir(parents=True)
            for n in ['v9_complete.json','dyn.parquet','sta.parquet','outc.parquet']:(f/n).write_text('x')
    G=dict(Path=Path,pd=pd,gc=gc,shutil=shutil,json=json,signature=signature,DATA_SOURCE='clinical',DATASETS=['miiv','eicu'],YAIB_DATASETS=['miiv','eicu'],
           PROJECT=PROJECT,COHORT_KEY=COHORT_KEY,COHORT_ROOT=COHORT_ROOT,CODE_DIR=CODE_DIR,COHORT_REPO=tmp/'YAIB-cohorts',RICU_MOUNT=tmp/'ricu',
           STAGE2_LABEL_VARIANTS=variants,STAGE2_KEEP_EARLY_ONSET=True,STAGE2_REUSE_LABEL_ROOTS=[],FORCE_YAIB_REEXTRACT=force,RUN_EXTRACTION=True,
           resolved_raw={'miiv':'/raw/m','eicu':'/raw/e'},YAIB_PYTHON='py',COHORT_BATCH_STAYS=500,COHORT_PROTOCOL={'candidate_n':None},RANDOM_STATE=42,
           LOG_ROOT=tmp/'logs',LABEL_PARALLEL_BATCHES=3,atomic_json=lambda p,d:(Path(p).parent.mkdir(parents=True,exist_ok=True),Path(p).write_text(json.dumps(d))))
    G['cohort_complete']=lambda ds:(COHORT_ROOT/ds/'v9_complete.json').is_file() and all((COHORT_ROOT/ds/f).is_file() for f in ['dyn.parquet','sta.parquet','outc.parquet'])
    out=io.StringIO()
    with contextlib.redirect_stdout(out):exec(tail,G)
    if variants_done:
        for ds,si in variants.items():
            if done_only and ds not in done_only:continue
            v=G['stage2_variant_root'](ds,si);old=PROJECT/'cohorts_v9'/f"{COHORT_KEY}_variant_{signature({'cohort':COHORT_KEY,'si_mode':si,'ds':ds})[:16]}"/'sepsis'/ds
            assert v==old,'variant path changed';v.mkdir(parents=True,exist_ok=True);(v/'variant_complete.json').write_text('{}')
            b=v/'batches'/'plan'/'00000';b.mkdir(parents=True)
            pd.DataFrame({'stay_id':[10,11],'time':pd.to_timedelta([3,4],unit='h'),'sep3_alt':[True,True]}).to_parquet(b/'labels.parquet')
    out=io.StringIO()
    with contextlib.redirect_stdout(out):exec(tail,G)
    exec(need_src,G);need=G['need_extract']
    exec(skip_src.replace('print(','(lambda *a,**k:None)('),G);skipped=G['skipped']
    if env_ready:
        (G['COHORT_REPO']/'Python'/'renv').mkdir(parents=True);(G['COHORT_REPO']/'Python'/'renv'/'activate.R').write_text('#');G['YAIB_RUNTIME_ENV']={'X':'1'};G['YAIB_R_LIB']='/lib'
    else:G['YAIB_RUNTIME_ENV']={}   # what 4a leaves behind when it skips
    err=None;out4=io.StringIO()
    try:
        with contextlib.redirect_stdout(out4):exec(c12,G)
    except Exception as e:err=f'{type(e).__name__}: {e}'
    res={'cell8':out.getvalue().strip(),'need_extract':need,'ricu_skipped':skipped,'extract_calls':[(c['ds'],c['phases'],c['si'],c['early'],c['worker_exists']) for c in calls],
         'alt_onsets':{k:len(v) for k,v in G.get('ALT_ONSETS',{}).items()},'error':err}
    ok=(err is not None)==expect_error
    print(('PASS ' if ok else 'FAIL ')+name);[print('   ',k,'=',v) for k,v in res.items()]
    if not ok:raise SystemExit(1)
    return res
# 1. the user's state on 2 Nov: both cohorts done, variants not; 4a runs (need_extract must be True), env built
r=scenario('A cohorts done, variants pending, environment built (the next real session)',True,False,True)
assert r['need_extract'] and r['ricu_skipped']==[] and [c[:3] for c in r['extract_calls']]==[('miiv',('labels',),'abx'),('eicu',('labels',),'and')] and all(c[3]=='1' and c[4] for c in r['extract_calls'])
# 2. same state but 4a skipped anyway (must stop with a clear message, not FileNotFoundError)
r=scenario('B cohorts done, variants pending, environment NOT built (guard)',True,False,False,expect_error=True)
assert 'not set up in this session' in r['error'] and r['need_extract']
# 3. everything done (later sessions: features, notebook 15): no environment, no error, onsets read
r=scenario('C cohorts and variants done, no environment (later sessions, notebook 15)',True,True,False)
assert not r['need_extract'] and r['ricu_skipped']==['miiv','eicu'] and r['extract_calls']==[] and r['alt_onsets']=={'miiv':2,'eicu':2}
# 4. variants switched off, cohorts done
r=scenario('D cohorts done, variants off',True,False,False,variants={})
assert not r['need_extract'] and r['extract_calls']==[] and r['alt_onsets']=={}
# 5. cohorts not done (a fresh project): old behaviour kept
r=scenario('E nothing done, environment built',False,False,True)
assert r['need_extract'] and r['ricu_skipped']==[] and [c[2] for c in r['extract_calls']]==[None,None,'abx','and'] and r['extract_calls'][0][1]==('labels','cohort')
# 6. FORCE flag still forces
r=scenario('F everything done but FORCE_YAIB_REEXTRACT (old behaviour kept)',True,True,True,force=True)
assert r['need_extract']
# 7. one variant done, the other not (a session stopping between the two)
def half(name):
    pass
r=scenario('G cohorts done, MIMIC variant done, eICU variant pending, environment built',True,True,True,done_only=['miiv'])
assert r['need_extract'] and r['ricu_skipped']==['miiv'] and [c[:3] for c in r['extract_calls']]==[('eicu',('labels',),'and')] and r['cell8'].endswith("{'miiv': 'nothing', 'eicu': 'label variant'}")
print('ALL SCENARIOS PASS')
