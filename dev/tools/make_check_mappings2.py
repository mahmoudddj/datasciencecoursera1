"""Build Sepsis_V11_Improved_MIMIC_eICU_14_check_mappings2.ipynb (5 Nov 2026).

Second read-only aggregate check, to design the eICU mapping fix decided on 5 Nov 2026 (fix before the freeze):
high-flow oxygen, arterial line, dialysis catheter, cardiac output, SvO2/ScvO2, urine WBC, and whether eICU
records atrial fibrillation anywhere; plus MIMIC D-dimer units and the 22 eICU stays missing from the index.
Same setup and masking rules as the first check. Nothing is written to Drive.
Usage: python3 dev/tools/make_check_mappings2.py
"""
import nbformat as nbf
from pathlib import Path
from make_check_mappings import SETUP, END, write

OUT = Path(__file__).resolve().parents[2] / 'Sepsis_V11_Improved_MIMIC_eICU_14_check_mappings2.ipynb'

INTRO = """# Read-only check 2: designing the eICU mapping fix (5 Nov 2026)

Decided on 5 Nov 2026: the eICU predictors that exist in the raw data but were missed by the mapping (high-flow oxygen,
arterial line, dialysis catheter, cardiac output, SvO2/ScvO2, urine WBC) are fixed **before the freeze**. This check shows
the value formats, units, ranges and timing columns needed to write that fix, and settles atrial fibrillation in eICU,
the MIMIC D-dimer units and the 22 eICU stays missing from the index. **Nothing is written to Drive.** Aggregates only:
strings seen fewer than 11 times are dropped; counts from 1 to 10 are shown as `<11`; value ranges are percentiles.

Runtime: CPU. Use **Run all**; about 15–25 minutes. Then File → Download → Download .ipynb from this tab."""

EICU = r'''# Part A. eICU sources for the fix (value formats, units, ranges, timing columns).
root=RAW['eicu']
_counts=counts
def counts(sql):
    d,r=_counts(sql)
    if 'stays' in d:d['stays']=d.stays.map(mask)
    return d,r
def dist(title,frm,expr,where):
    """Count and percentiles of a numeric expression (aggregate only)."""
    r=con.execute(f"""SELECT count(v) AS n,count(DISTINCT sid) AS stays,quantile_cont(v,0.01) p01,quantile_cont(v,0.05) p05,quantile_cont(v,0.5) p50,
        quantile_cont(v,0.95) p95,quantile_cont(v,0.99) p99 FROM (SELECT TRY_CAST({expr} AS DOUBLE) AS v,patientunitstayid AS sid FROM {frm} WHERE {where}) t""").df().iloc[0]
    n=int(r.n);print(f"\n{title}: {mask(n)} numeric values in {mask(int(r.stays))} stays"+
        (f" | p01 {r.p01:.3g}, p05 {r.p05:.3g}, median {r.p50:.3g}, p95 {r.p95:.3g}, p99 {r.p99:.3g}" if n>=11 else ''))
for name in ['nurseCharting','respiratoryCharting','physicalExam','lab','vitalAperiodic','treatment']:
    p=table(root,name);print(f'{name} columns:',cols(p) if p else 'table not present')
nc,rc,pe,lab,va,tr=[table(root,n) for n in ['nurseCharting','respiratoryCharting','physicalExam','lab','vitalAperiodic','treatment']]
# A1 high-flow oxygen (and the other oxygen-device words, for O2_NIV and SupplementalO2 consistency)
for lbl in ['O2 Device','Oxygen Delivery Method','Non-invasive Ventilation Mode','Respiratory Device','RETIRED O2 Device','Bipap Delivery Mode']:
    show(f'A1 respiratoryCharting values under "{lbl}" (top 50)',
         f"SELECT respchartvalue,count(*) AS rows FROM {src(rc)} WHERE respchartvaluelabel={q(lbl)} GROUP BY 1 ORDER BY rows DESC LIMIT 50")
show('A1 nurseCharting values under "O2 Admin Device" (top 60)',
     f"""SELECT nursingchartvalue,count(*) AS rows FROM {src(nc)} WHERE nursingchartcelltypevallabel='O2 Admin Device' GROUP BY 1 ORDER BY rows DESC LIMIT 60""")
show('A1 nurseCharting category of the oxygen, SVO2 and arterial-line labels',
     f"""SELECT nursingchartcelltypecat,nursingchartcelltypevallabel,nursingchartcelltypevalname,count(*) AS rows FROM {src(nc)}
         WHERE nursingchartcelltypevallabel IN ('O2 Admin Device','O2 L/%','SVO2','Arterial Line MAP (mmHg)') GROUP BY 1,2,3 ORDER BY rows DESC""")
# A2 arterial line: treatment entries and nurse-charted arterial-line MAP (presence of a line)
dist('A2 nurseCharting "Arterial Line MAP (mmHg)"',src(nc),'nursingchartvalue',"nursingchartcelltypevallabel='Arterial Line MAP (mmHg)'")
show('A2 treatment entries naming an arterial catheter',
     f"""SELECT treatmentstring,count(*) AS rows,count(DISTINCT patientunitstayid) AS stays FROM {src(tr)}
         WHERE regexp_matches(lower(coalesce(treatmentstring,'')),'arterial') GROUP BY 1 ORDER BY rows DESC LIMIT 40""")
ov=con.execute(f"""WITH a AS (SELECT DISTINCT patientunitstayid s FROM {src(nc)} WHERE nursingchartcelltypevallabel='Arterial Line MAP (mmHg)'),
    b AS (SELECT DISTINCT patientunitstayid s FROM {src(tr)} WHERE regexp_matches(lower(coalesce(treatmentstring,'')),'vascular catheter placement\\|arterial'))
    SELECT (SELECT count(*) FROM a) a,(SELECT count(*) FROM b) b,(SELECT count(*) FROM a JOIN b USING(s)) ab""").df().iloc[0]
print(f"A2 stays with arterial-line MAP charting {mask(ov.a)} | with an arterial catheter treatment entry {mask(ov.b)} | both {mask(ov.ab)}")
# A3 dialysis catheter
show('A3 treatment entries naming a hemodialysis catheter or dialysis access',
     f"""SELECT treatmentstring,count(*) AS rows,count(DISTINCT patientunitstayid) AS stays FROM {src(tr)}
         WHERE regexp_matches(lower(coalesce(treatmentstring,'')),'catheter for hemodialysis|dialysis catheter|hemodialysis catheter|dialysis access|catheter for peritoneal')
         GROUP BY 1 ORDER BY rows DESC LIMIT 40""")
# A4 cardiac output, A5 SvO2/ScvO2
dist('A4 vitalAperiodic cardiacoutput (L/min)',src(va),'cardiacoutput','true')
dist('A4 vitalAperiodic cardiacinput (cardiac index, L/min/m2)',src(va),'cardiacinput','true')
dist('A5 nurseCharting "SVO2"',src(nc),'nursingchartvalue',"nursingchartcelltypevallabel='SVO2'")
show('A5 lab names for venous oxygen saturation (any lab name with sat or o2)',
     f"""SELECT labname,count(*) AS rows FROM {src(lab)} WHERE regexp_matches(lower(coalesce(labname,'')),'sat|o2') GROUP BY 1 ORDER BY rows DESC LIMIT 30""")
# A6 urine WBC
dist('A6 lab "WBC\'s in urine" labresult',src(lab),'labresult',"labname='WBC''s in urine'")
show('A6 lab "WBC\'s in urine": units and result text (top 40)',
     f"""SELECT labmeasurenamesystem,labmeasurenameinterface,labresulttext,count(*) AS rows FROM {src(lab)} WHERE labname='WBC''s in urine'
         GROUP BY 1,2,3 ORDER BY rows DESC LIMIT 40""")
# A7 atrial fibrillation: full physical-exam paths (end of path shown)
show('A7 physicalExam paths with rhythm / fibrillation / irregular (last 78 characters, top 60)',
     f"""SELECT right(physicalexampath,78) AS path_end,count(*) AS rows,count(DISTINCT patientunitstayid) AS stays FROM {src(pe)}
         WHERE regexp_matches(lower(coalesce(physicalexampath,'')),'rhythm|fibril|irregular|sinus|flutter') GROUP BY 1 ORDER BY rows DESC LIMIT 60""")
show('A7 treatment entries about atrial fibrillation (top 30)',
     f"""SELECT treatmentstring,count(*) AS rows FROM {src(tr)} WHERE regexp_matches(lower(coalesce(treatmentstring,'')),'atrial fib|fibrillation|flutter')
         GROUP BY 1 ORDER BY rows DESC LIMIT 30""")
'''

MIMIC = r'''# Part B. MIMIC-IV D-dimer and NT-proBNP: units per item (two D-dimer items may use different units).
root=RAW['miiv'];le=table(root,'hosp/labevents');t0=time.time()
d=con.execute(f"""SELECT itemid,coalesce(valueuom,'(none)') AS unit,count(*) AS n,count(TRY_CAST(valuenum AS DOUBLE)) AS numeric_n,
    quantile_cont(TRY_CAST(valuenum AS DOUBLE),0.05) p05,quantile_cont(TRY_CAST(valuenum AS DOUBLE),0.5) p50,quantile_cont(TRY_CAST(valuenum AS DOUBLE),0.95) p95
    FROM {src(le)} WHERE itemid IN ('50915','51196','52551','50963') GROUP BY 1,2 ORDER BY 1,n DESC""").df()
d=d[d.n>=11].copy();d['n']=d.n.map(mask);d['numeric_n']=d.numeric_n.map(mask)
print(f'MIMIC labevents units and value percentiles per item ({time.time()-t0:.0f} s; unit rows with fewer than 11 values not shown):');display(d.round(3))
'''

GAP = r'''# Part C. The eICU stays with onset at or after hour 6 that are not in the index: follow-up relative to onset.
index=pd.read_parquet(DATA_ROOT/'index.parquet',columns=['Dataset','stay_id'])
ds='eicu';parts=[]
for b in pq.ParquetFile(COHORT_ROOT/ds/'outc.parquet').iter_batches(batch_size=500000,columns=['stay_id','time']):
    x=b.to_pandas();t=x.time.dt.total_seconds()/3600 if pd.api.types.is_timedelta64_dtype(x.time) else pd.to_numeric(x.time).astype(float)
    parts.append(pd.DataFrame({'stay_id':x.stay_id,'h':t}).groupby('stay_id').h.max())
follow=pd.concat(parts).groupby(level=0).max().rename('followup_end')
z=pd.read_parquet(COHORT_ROOT/ds/'v10_onset_audit.parquet',columns=['stay_id','OnsetHour']).set_index('stay_id').join(follow)
z=z[z.OnsetHour.ge(6)&~z.index.isin(set(index.loc[index.Dataset.eq(ds),'stay_id']))]
f=np.select([z.followup_end<1,z.followup_end<7],['follow-up < 1 h','follow-up 1-7 h'],'follow-up >= 7 h')
g=np.select([z.OnsetHour<=z.followup_end,z.OnsetHour<=z.followup_end+6],['onset within follow-up','onset 0-6 h after follow-up ends'],'onset > 6 h after follow-up ends')
t=pd.crosstab(pd.Series(f,name='follow-up'),pd.Series(g,name='onset'))
print(f'eICU stays with onset at or after hour 6 not in the index: {mask(len(z))}');display(t.map(mask) if hasattr(t,'map') else t.applymap(mask))
'''

if __name__ == '__main__':
    write([nbf.v4.new_markdown_cell(INTRO), nbf.v4.new_code_cell(SETUP), nbf.v4.new_code_cell(EICU),
           nbf.v4.new_code_cell(MIMIC), nbf.v4.new_code_cell(GAP), nbf.v4.new_code_cell(END)], OUT)
