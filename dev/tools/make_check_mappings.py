"""Build Sepsis_V11_Improved_MIMIC_eICU_14_check_mappings.ipynb (3 Nov 2026).

Read-only aggregate check after the stage-2 data build (data key 7a70b04ae69347b0), before notebook 15:
  A. predictors mapped by name/pattern that found zero rows: which item names actually exist in the raw tables
     (dictionary names and picklist strings with row counts; strings seen fewer than 11 times are dropped);
  B. cohort stays that are not in the feature index (arrival stays with onset at or before hour 1, short
     follow-up), counted by onset group.
Nothing is written to Drive. Usage: python3 dev/tools/make_check_mappings.py
"""
import nbformat as nbf
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / 'Sepsis_V11_Improved_MIMIC_eICU_14_check_mappings.ipynb'

INTRO = """# Read-only check: zero-row mappings and the arrival-sepsis gap (3 Nov 2026)

Runs after the stage-2 data build (data key `7a70b04ae69347b0`) and before notebook 15. **Nothing is written to Drive.**
Only aggregates are shown: item names from the data dictionaries, picklist strings and row counts. Strings seen fewer
than 11 times are dropped; counts from 1 to 10 are shown as `<11` (zero is shown as 0).

* **Part A** — predictors that are mapped by name or pattern but found no rows (eICU procalcitonin, D-dimer, NT-proBNP,
  high-flow oxygen, atrial fibrillation, capillary refill, skin colour, arterial line, dialysis catheter; MIMIC
  procalcitonin, BNP) and the eICU predictors with no source at all (urine dipstick, cardiac output, ScvO2): which
  names exist in the raw tables.
* **Part B** — cohort stays that are not in the feature index, by onset group.

Runtime: CPU (High-RAM is fine). Use **Run all**; about 15–30 minutes, mostly reading the large raw tables from Drive.
Then File → Download → Download .ipynb from this tab."""

SETUP = r'''# Setup: paths, checks that the expected caches exist (read-only).
import os,sys,json,time,re,importlib.util,subprocess
from pathlib import Path
PROJECT_PATH=os.environ.get('SEPSIS_PROJECT_ROOT','/content/drive/.shortcut-targets-by-id/1A7VFDTLnevMBChDvADRU2QJBzHf3s9pF/sepsis_colab_project')
COHORT_KEY='e2dbca97e122e6bc';DATA_KEY='7a70b04ae69347b0';DATASETS=['miiv','eicu']
if importlib.util.find_spec('google') is not None and importlib.util.find_spec('google.colab') is not None:
    from google.colab import drive;drive.mount('/content/drive')
if importlib.util.find_spec('duckdb') is None:subprocess.check_call([sys.executable,'-m','pip','install','-q','duckdb'])
import duckdb,numpy as np,pandas as pd,pyarrow.parquet as pq
pd.set_option('display.max_rows',300);pd.set_option('display.max_colwidth',90);pd.set_option('display.width',200)
PROJECT=Path(PROJECT_PATH);VALIDATION_ROOT=PROJECT/'validation_v10'
COHORT_ROOT=PROJECT/'cohorts_v9'/COHORT_KEY/'sepsis';DATA_ROOT=VALIDATION_ROOT/'data'/DATA_KEY
manifest=json.loads((VALIDATION_ROOT/'resolved_raw_sources.json').read_text())
RAW={ds:Path(manifest['sources'][ds]['raw_source']) for ds in DATASETS}
for ds in DATASETS:
    for f in [COHORT_ROOT/ds/'outc.parquet',COHORT_ROOT/ds/'v10_onset_audit.parquet',DATA_ROOT/ds/'completed.json']:
        if not f.is_file():raise FileNotFoundError(f'Expected cache file is missing: {f}')
    if json.loads((DATA_ROOT/ds/'completed.json').read_text()).get('data_key')!=DATA_KEY:raise ValueError(f'{ds}: data cache is not {DATA_KEY}')
if not (DATA_ROOT/'index.parquet').is_file():raise FileNotFoundError(DATA_ROOT/'index.parquet')
def table(root,stem):
    p=Path(root)/Path(stem).parent;base=Path(stem).name.lower()
    return next((f for f in p.iterdir() if f.is_file() and f.name.lower() in {base+'.csv',base+'.csv.gz'}),None) if p.is_dir() else None
def q(s):return "'"+str(s).replace("'","''")+"'"
con=duckdb.connect();con.execute('SET threads=4');con.execute("SET memory_limit='8GB'")
def src(path):return f'read_csv({q(path)},header=true,all_varchar=true,ignore_errors=true)'
def cols(path):return [r[0].lower() for r in con.execute(f'DESCRIBE SELECT * FROM {src(path)}').fetchall()]
def counts(sql):
    """Name/string counts: strings seen fewer than 11 times are dropped (rare strings may be free text)."""
    d=con.execute(sql).df()
    if d.empty:return d,0
    d['rows']=d['rows'].astype('int64');rare=int((d.rows<11).sum());d=d[d.rows>=11].copy()
    for c in d.columns:
        if d[c].dtype==object:d[c]=d[c].astype(str).str.slice(0,80)
    d['rows']=d.rows.map(lambda n:f'{n:,}');return d.reset_index(drop=True),rare
def show(title,sql):
    t0=time.time();d,rare=counts(sql)
    print(f'\n{title}  ({time.time()-t0:.0f} s; {rare} rare strings with fewer than 11 rows not shown)')
    display(d) if len(d) else print('  no matching names')
def mask(n):return '0' if int(n)==0 else '<11' if n<11 else f'{int(n):,}'
print('Raw sources:',{k:str(v) for k,v in RAW.items()});print('Cohort',COHORT_KEY,'| data',DATA_KEY,'| read-only')
'''

EICU = r'''# Part A1. eICU: which names exist for the zero-row predictors (aggregates only).
root=RAW['eicu']
lab=table(root,'lab')
show('eICU lab: names matching procalcitonin / D-dimer / BNP / troponin / urine / venous saturation',
     f"""SELECT labname,count(*) AS rows FROM {src(lab)} WHERE regexp_matches(lower(coalesce(labname,'')),'procalc|\\bpct\\b|dimer|bnp|natriur|troponin|urin|nitrite|leuk|esterase|cardiac output|svo2|scvo2|mixed venous|venous')
         GROUP BY 1 ORDER BY rows DESC""")
exact=con.execute(f"""SELECT lower(labname) AS name,count(*) AS rows FROM {src(lab)} WHERE lower(labname) IN ('procalcitonin','d-dimer','probnp','nt-probnp','bnp','troponin - i')
    GROUP BY 1""").df()
print('Names the code maps (exact, lower case):',{n:mask(exact.set_index('name').rows.get(n,0)) for n in ['procalcitonin','d-dimer','probnp','nt-probnp','bnp','troponin - i']})
cl=table(root,'customLab')
if cl:show('eICU customLab (site-typed lab names; not used by the code): matching names',
     f"""SELECT labothername,count(*) AS rows FROM {src(cl)} WHERE regexp_matches(lower(coalesce(labothername,'')),'procalc|\\bpct\\b|dimer|bnp|natriur|urin|nitrite|leuk|esterase|svo2|scvo2|mixed venous')
         GROUP BY 1 ORDER BY rows DESC LIMIT 60""")
else:print('eICU customLab table not present')
va=table(root,'vitalAperiodic')
if va:
    c=cols(va);want=[x for x in ['cardiacoutput','cardiacinput','svr','svri','pvr','pvri','paop'] if x in c]
    r=con.execute('SELECT '+','.join(f'count(TRY_CAST({x} AS DOUBLE)) AS {x}' for x in want)+f' FROM {src(va)}').df() if want else pd.DataFrame()
    print('\neICU vitalAperiodic: rows with a numeric value per column (cardiac output has no eICU mapping in the code):')
    print({x:mask(int(r[x].iloc[0])) for x in want} if want else 'none of the columns exist')
vp=table(root,'vitalPeriodic')
if vp:print('eICU vitalPeriodic columns:',cols(vp))
tr=table(root,'treatment')
if tr:show('eICU treatment strings: high-flow oxygen / arterial line / dialysis catheter / other catheters (top 100)',
     f"""SELECT treatmentstring,count(*) AS rows FROM {src(tr)} WHERE regexp_matches(lower(coalesce(treatmentstring,'')),'high flow|hfnc|optiflow|vapotherm|nasal cannula|arterial|art line|a-line|dialysis|hemodialysis|crrt|catheter')
         GROUP BY 1 ORDER BY rows DESC LIMIT 100""")
rc=table(root,'respiratoryCharting')
if rc:
    show('eICU respiratoryCharting labels about oxygen devices / flow',
     f"""SELECT respchartvaluelabel,count(*) AS rows FROM {src(rc)} WHERE regexp_matches(lower(coalesce(respchartvaluelabel,'')),'o2 device|oxygen|delivery|device|flow|hfnc|cannula')
         GROUP BY 1 ORDER BY rows DESC LIMIT 60""")
    show('eICU respiratoryCharting values that name high-flow / nasal cannula devices',
     f"""SELECT respchartvaluelabel,respchartvalue,count(*) AS rows FROM {src(rc)} WHERE regexp_matches(lower(coalesce(respchartvalue,'')),'high flow|hfnc|optiflow|vapotherm|airvo|nasal cannula|\\bnc\\b')
         GROUP BY 1,2 ORDER BY rows DESC LIMIT 60""")
nc=table(root,'nurseCharting')
if nc:
    show('eICU nurseCharting labels/names about rhythm, capillary refill, skin, lines, oxygen (top 100)',
     f"""SELECT nursingchartcelltypevallabel AS label,nursingchartcelltypevalname AS name,count(*) AS rows FROM {src(nc)}
         WHERE regexp_matches(lower(coalesce(nursingchartcelltypevallabel,'')||' | '||coalesce(nursingchartcelltypevalname,'')),'rhythm|capillary|cap refill|skin|mottl|arterial|a-line|art line|dialysis|o2|oxygen|delivery device|flow')
         GROUP BY 1,2 ORDER BY rows DESC LIMIT 100""")
    show('eICU nurseCharting values under rhythm / capillary / skin / oxygen labels (picklist words only)',
     f"""SELECT nursingchartcelltypevallabel AS label,nursingchartcelltypevalname AS name,nursingchartvalue AS value,count(*) AS rows FROM {src(nc)}
         WHERE regexp_matches(lower(coalesce(nursingchartcelltypevallabel,'')||' | '||coalesce(nursingchartcelltypevalname,'')),'rhythm|capillary|cap refill|skin|o2 device|oxygen|delivery device')
           AND regexp_matches(lower(coalesce(nursingchartvalue,'')),'fib|flutter|sinus|paced|brisk|delay|sluggish|normal|second|mottl|pale|pink|cyan|dusky|warm|cool|high flow|hfnc|cannula|nasal')
         GROUP BY 1,2,3 ORDER BY rows DESC LIMIT 80""")
pe=table(root,'physicalExam')
if pe:show('eICU physicalExam paths about rhythm, capillary refill, skin (top 80)',
     f"""SELECT physicalexampath,count(*) AS rows FROM {src(pe)} WHERE regexp_matches(lower(coalesce(physicalexampath,'')),'rhythm|fibril|capillary|cap refill|skin|mottl|cyano')
         GROUP BY 1 ORDER BY rows DESC LIMIT 80""")
pt=table(root,'patient')
for c in ['unitadmitsource','hospitaladmitsource']:
    if c in cols(pt):show(f'eICU patient.{c} values (admission from a nursing facility is never observed in eICU)',
        f"SELECT {c},count(*) AS rows FROM {src(pt)} GROUP BY 1 ORDER BY rows DESC")
'''

MIMIC = r'''# Part A2. MIMIC-IV: is there a procalcitonin or BNP lab item at all (dictionary), and how many rows does each have.
root=RAW['miiv'];dl=table(root,'hosp/d_labitems')
items=con.execute(f"""SELECT itemid,label,fluid,category FROM {src(dl)} WHERE regexp_matches(lower(coalesce(label,'')),'procalc|natriur|\\bbnp\\b|probnp|troponin|dimer')
    ORDER BY label""").df()
print('MIMIC d_labitems entries matching procalcitonin / natriuretic peptide / BNP / troponin / D-dimer (dictionary, no patient data):');display(items)
if len(items):
    le=table(root,'hosp/labevents');t0=time.time()
    n=con.execute(f"""SELECT itemid,count(*) AS rows,count(TRY_CAST(valuenum AS DOUBLE)) AS numeric_rows FROM {src(le)}
        WHERE itemid IN ({','.join(q(i) for i in items.itemid.astype(str))}) GROUP BY 1""").df()
    n['itemid']=n.itemid.astype(str);out=items.assign(itemid=items.itemid.astype(str)).merge(n,on='itemid',how='left').fillna({'rows':0,'numeric_rows':0})
    out['rows']=out.rows.map(mask);out['numeric_rows']=out.numeric_rows.map(mask)
    print(f'Rows in labevents per item ({time.time()-t0:.0f} s):');display(out)
'''

GAP = r'''# Part B. Cohort stays that are not in the feature index, by onset group (counts only).
# The hourly grid starts at hour 1 and a stay is kept only if it has an eligible hour: hour 1 must be before onset,
# and (without an onset) the 6-hour horizon must be followed up (follow-up of at least 7 hours).
index=pd.read_parquet(DATA_ROOT/'index.parquet',columns=['Dataset','stay_id'])
rows=[]
for ds in DATASETS:
    parts=[]
    for b in pq.ParquetFile(COHORT_ROOT/ds/'outc.parquet').iter_batches(batch_size=500000,columns=['stay_id','time']):
        d=b.to_pandas();t=d.time.dt.total_seconds()/3600 if pd.api.types.is_timedelta64_dtype(d.time) else pd.to_numeric(d.time).astype(float)
        parts.append(pd.DataFrame({'stay_id':d.stay_id,'h':t}).groupby('stay_id').h.max())
    follow=pd.concat(parts).groupby(level=0).max().rename('followup_end')
    audit=pd.read_parquet(COHORT_ROOT/ds/'v10_onset_audit.parquet',columns=['stay_id','OnsetHour']).set_index('stay_id')
    if set(audit.index)!=set(follow.index):raise ValueError(f'{ds}: onset audit and outcome table cover different stays')
    z=audit.join(follow);z['in_index']=z.index.isin(set(index.loc[index.Dataset.eq(ds),'stay_id']))
    o=z.OnsetHour
    z['group']=np.select([o.isna()&(z.followup_end<7),o.isna(),o<=1,o<6],['no onset, follow-up < 7 h','no onset, follow-up >= 7 h','onset at or before hour 1','onset after hour 1, before hour 6'],'onset at or after hour 6')
    for g,s in z.groupby('group'):rows.append({'database':ds,'group':g,'cohort_stays':len(s),'in_index':int(s.in_index.sum()),'not_in_index':int((~s.in_index).sum())})
    print(f"{ds}: cohort {mask(len(z))} stays, index {mask(int(z.in_index.sum()))}, not in the index {mask(int((~z.in_index).sum()))}")
G=pd.DataFrame(rows)
order=['no onset, follow-up < 7 h','no onset, follow-up >= 7 h','onset at or before hour 1','onset after hour 1, before hour 6','onset at or after hour 6']
G['group']=pd.Categorical(G.group,order,ordered=True);G=G.sort_values(['database','group'])
display(G.assign(**{c:G[c].map(mask) for c in ['cohort_stays','in_index','not_in_index']}).reset_index(drop=True))
expected=G.group.isin(['no onset, follow-up < 7 h','onset at or before hour 1'])
print('Stays missing from the index for a reason other than the two expected ones:',{ds:mask(int(G[(G.database==ds)&~expected].not_in_index.sum())) for ds in DATASETS})
print('Arrival sepsis (onset before hour 6) in the cohort:',{ds:mask(int(G[(G.database==ds)&G.group.isin(order[2:4])].cohort_stays.sum())) for ds in DATASETS},
      '| of which onset at or before hour 1 (not in the index):',{ds:mask(int(G[(G.database==ds)&(G.group==order[2])].cohort_stays.sum())) for ds in DATASETS})
'''

END = r'''print('CHECK COMPLETE (read-only; nothing was written). Download this notebook and send it back.')'''

def write(cells, out):
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    nb.metadata = {'kernelspec': {'name': 'python3', 'display_name': 'Python 3'}, 'language_info': {'name': 'python'},
                   'colab': {'provenance': []}}
    nbf.validate(nb)
    nbf.write(nb, out)
    print('wrote', out)


if __name__ == '__main__':
    write([nbf.v4.new_markdown_cell(INTRO), nbf.v4.new_code_cell(SETUP), nbf.v4.new_code_cell(EICU),
           nbf.v4.new_code_cell(MIMIC), nbf.v4.new_code_cell(GAP), nbf.v4.new_code_cell(END)], OUT)
