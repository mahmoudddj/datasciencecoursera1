"""Version 9: bounded raw-table extraction and availability-aware hourly features.
YAIB supplies cohort membership and labels, not the predictor timestamps.
"""
from pathlib import Path
import json, hashlib, re, gc, os, warnings
import numpy as np
import pandas as pd
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

VERSION='v10.2'
from v10_features import engineer_one, ENGINEERED
SPEC=json.loads((Path(__file__).parent/'feature_specs.json').read_text())
# PostoperativeAdmission is not comparably available in either release; it is kept
# as metadata only (always missing), not as a model predictor (v10.2).
BASE=[x for x in SPEC if x!='UrineOutput']+['GCS','Weight','Age','Gender']
SUPPORT=['VasopressorRecorded','InotropeRecorded']
RENAL=['UrineOutput','UrineOutput_6h','UrineOutput_24h','UrineCoverage_6h','UrineCoverage_24h','Urine_mlkg_h_6h','Oliguria6h']
DERIVED=['SIRS_Temp','SIRS_HR','SIRS_Resp','SIRS_WBC','SIRS_ObservedComponents','SIRS_Count','ShockIndex']
PRIMARY=BASE+SUPPORT+RENAL+DERIVED
SITES=['urine','respiratory','abdominal','skin','cns','blood','device','other']
PROXIES=['CultureTaken']+['SpecimenSite_'+s for s in SITES]
EXTRA_CONTEXT=['StressDocumented','TraumaDocumented','BurnDocumented','PancreatitisDocumented','PostoperativeDocumented']
PRESSORS={'norepinephrine','epinephrine','phenylephrine','vasopressin','dopamine'}
PRESSOR_RE=r'norepi|noradren|levophed|epinephrine|adrenalin|phenylephrine|neosynephrine|vasopressin|dopamine'
INOTROPE_RE=r'dobutamine|dobutrex|milrinone'
# Urinary collection method is separate from the anatomical specimen site.
SITE_PATTERNS={
 'urine':r'\burin|urogen|bladder|renal pelvis|nephrost',
 'respiratory':r'sputum|respirat|trache|bronch|lung|pulmon|nasophar|pleural|pneumon',
 'abdominal':r'abdom|peritone|biliar|gallbladder|cholang|ascit|stool|fecal|gastro|bowel',
 'cns':r'\bcsf\b|cerebrospinal|mening|ventricular',
 'blood':r'\bblood|bacteremia',
 'skin':r'wound|skin|soft tissue|cellul|ulcer|abscess',
 'device':r'catheter|central line|vascular access|\bpicc\b|device'}
# Conservative documented-term proxies, never adjudicated SIRS causes.
PHENO={
 'postoperative':r'\bpost[- ]?operativ\w*|\bpost[- ]?op\b|\bpostprocedural\b|\bafter surgery\b|\bs/p (?:surgery|operation)\b',
 'trauma':r'\btrauma\b|\btraumatic\b|\bgunshot\b|\bstab wound\b|\bmotor vehicle\b|\btraumatic fracture\b',
 'burn':r'\bburns?\b|\bthermal injury\b|\binhalation injury\b',
 'pancreatitis':r'\bpancreatitis\b',
 'cardiogenic_shock':r'\bcardiogenic shock\b',
 'hemorrhagic_shock':r'\b(?:hemorrhagic|haemorrhagic) shock\b|\bacute (?:posthemorrhagic|blood loss) anemia\b',
 'immunosuppression':r'\bimmunosupp\w*|\bneutropeni\w*|\btransplant recipient\b|\bacquired immunodeficiency\b',
 'malignancy':r'\bmalignant neoplasm\b|\bcarcinoma\b|\bleukemia\b|\blymphoma\b|\bmyeloma\b',
 'stress_documented':r'\bacute stress reaction\b|\bstress cardiomyopathy\b|\btakotsubo\b',
 'dka':r'\bketoacidosis\b',
 'pulmonary_embolism':r'\bpulmonary embol\w*',
 'seizure':r'\bstatus epilepticus\b|\bseizures?\b',
 'transfusion_reaction':r'\btransfusion reaction\b',
 'heat_illness':r'\bheat stroke\b|\bheatstroke\b',
 'drug_reaction':r'\bdrug fever\b|\bneuroleptic malignant syndrome\b|\bserotonin syndrome\b'}
MED_CONTEXT={
 'antimicrobial':r'vancomy|piperacillin|tazobactam|cef[a-z]|meropenem|imipenem|ertapenem|ciprofloxacin|levofloxacin|metronidazole|gentamicin|linezolid|ampicillin|amoxicillin|daptomycin|azithromycin|fluconazole|micafungin',
 'corticosteroid':r'hydrocortisone|predniso|dexamethasone|methylpred',
 'diuretic':r'furosemide|bumetanide|torsemide|chlorothiazide|hydrochlorothiazide|metolazone',
 'beta_agonist':r'albuterol|salbutamol|levalbuterol|terbutaline|formoterol',
 'sedative':r'propofol|midazolam|lorazepam|dexmedetomidine|ketamine',
 'opioid':r'fentanyl|morphine|hydromorphone|oxycodone|remifentanil',
 'antipyretic':r'acetaminophen|paracetamol|ibuprofen',
 'immunosuppressant':r'tacrolimus|cyclosporine|mycophenolate|sirolimus'}

def text_flags(text):
    # Clauses with explicit negation/history-only qualifiers do not establish current context.
    clauses=re.split(r'[;|\n]',str(text or '').lower())
    clauses=[s for s in clauses if not re.search(r'\b(?:no|denies|without|rule out|ruled out|history of|family history)\b',s)]
    return {'Phenotype_'+k:int(any(re.search(p,s) for s in clauses)) for k,p in PHENO.items()}

def specimen_site(text):
    text=str(text or '').lower()
    return next((s for s,p in SITE_PATTERNS.items() if re.search(p,text)),'other')

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(8*1024**2),b''):h.update(b)
    return h.hexdigest()

def signature(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,default=str).encode()).hexdigest()
def q(s):return "'" + str(s).replace("'","''") + "'"
def ident(s):return '"' + str(s).replace('"','""') + '"'

# eICU/MIMIC releases are RFC-style comma-separated CSVs.  Do not let DuckDB's
# sniffer decide that quote is empty: free-text eICU fields legitimately contain
# commas inside double quotes (e.g. note.csv.gz).
CSV_DIALECT = "header=true,all_varchar=true,delim=',',quote='\"',escape='\"',strict_mode=true"
def csv_scan(path, union_by_name=False):
    opts = CSV_DIALECT + (",union_by_name=true" if union_by_name else "")
    return f"read_csv({q(path)},{opts})"

def table(root,stem,required=False):
    p=Path(root)/Path(stem).parent; base=Path(stem).name.lower()
    found=next((f for f in p.iterdir() if f.is_file() and f.name.lower() in {base+'.csv',base+'.csv.gz'}),None) if p.is_dir() else None
    if required and found is None:raise FileNotFoundError(f'Missing raw table: {root}/{stem}.csv(.gz)')
    return found

def fingerprint(root):
    # Small header/tail content fingerprints plus size/mtime; does not repeatedly hash 15 GB tables.
    result={}
    for f in sorted(Path(root).rglob('*')):
        if not f.is_file() or not (f.name.endswith('.csv') or f.name.endswith('.csv.gz')):continue
        st=f.stat(); h=hashlib.sha256()
        with f.open('rb') as b:
            h.update(b.read(65536))
            if st.st_size>65536:b.seek(max(0,st.st_size-65536));h.update(b.read(65536))
        result[str(f.relative_to(root))]={'size':st.st_size,'mtime_ns':st.st_mtime_ns,'edges_sha256':h.hexdigest()}
    return result

def hour_values(s):
    if pd.api.types.is_timedelta64_dtype(s):return s.dt.total_seconds()/3600
    return pd.to_numeric(s,errors='raise').astype(float)

def cohort_index(folder,smoke_n,seed):
    parts=[]
    for b in pq.ParquetFile(Path(folder)/'outc.parquet').iter_batches(batch_size=200000,columns=['stay_id','time','label']):
        d=b.to_pandas(); d['hour']=hour_values(d.time);d['positive']=d.hour.where(d.label.eq(1))
        assert d.label.isin([0,1]).all(), 'Unexpected YAIB label'
        parts.append(d.groupby('stay_id',as_index=False).agg(first_hour=('hour','min'),followup_end=('hour','max'),first_positive=('positive','min')))
    z=pd.concat(parts).groupby('stay_id',as_index=False).agg(first_hour=('first_hour','min'),followup_end=('followup_end','max'),first_positive=('first_positive','min'))
    # YAIB applies a +/-6-hour outcome window; the first positive is onset minus 6.
    from v10_protocol import resolve_onsets
    z=resolve_onsets(folder,z)
    if smoke_n and len(z)>smoke_n:
        from sklearn.model_selection import train_test_split
        z,_=train_test_split(z,train_size=smoke_n,random_state=seed,stratify=z.Outcome)
    return z.sort_values('stay_id').reset_index(drop=True)

class RawExtractor:
    def __init__(self,ds,root,selected,output,max_hours=120,memory='1GB',temp=None):
        self.ds=ds;self.root=Path(root);self.out=Path(output);self.out.mkdir(parents=True,exist_ok=True)
        self.max_hours=max_hours;self.con=duckdb.connect()
        self.con.execute(f'SET memory_limit={q(memory)}');self.con.execute('SET threads=1')
        self.con.execute('SET preserve_insertion_order=false')
        if temp:Path(temp).mkdir(parents=True,exist_ok=True);self.con.execute(f'SET temp_directory={q(temp)}')
        self.con.register('chosen',selected[['stay_id']]);self.audit=[];self.files=[]
        if ds=='miiv':
            raw=self.csv('icu/icustays',True)
            self.meta=self.con.execute(f'''SELECT CAST(x.stay_id AS BIGINT) stay_id,CAST(x.hadm_id AS BIGINT) hadm_id,
              CAST(x.subject_id AS VARCHAR) person,CAST(x.intime AS TIMESTAMP) intime,CAST(x.outtime AS TIMESTAMP) outtime,
              'BIDMC' hospital FROM {raw} x JOIN chosen s ON TRY_CAST(x.stay_id AS BIGINT)=s.stay_id''').df()
        else:
            raw=self.csv('patient',True)
            self.meta=self.con.execute(f'''SELECT CAST(x.patientunitstayid AS BIGINT) stay_id, CAST(x.uniquepid AS VARCHAR) person,
              CAST(x.hospitalid AS VARCHAR) hospital, x.unitadmitsource admission_source
              FROM {raw} x JOIN chosen s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id''').df()
        self.meta=self.meta.merge(selected,on='stay_id',validate='one_to_one')
        if len(self.meta)!=len(selected):raise ValueError('Raw source and YAIB stay IDs do not match.')
        if self.meta.person.isna().any():raise ValueError('Missing patient linkage: cannot make safe patient-grouped splits.')
        self.con.register('stays',self.meta)

    def csv(self,stem,required=False):
        p=table(self.root,stem,required)
        if p is None:return None
        # Avoid numeric inference losing leading zeros in ICD codes and identifiers.
        return csv_scan(p,union_by_name=True)

    def cols(self,rel):return {r[0].lower() for r in self.con.execute(f'DESCRIBE SELECT * FROM {rel}').fetchall()}
    def col(self,rel,name,alias='x',default='NULL'):
        return f'{alias}.{ident(name)}' if name.lower() in self.cols(rel) else default

    def hour(self,c):return f"epoch(TRY_CAST({c} AS TIMESTAMP)-s.intime)/3600.0"

    def export(self,name,sql):
        path=self.out/(name+'.parquet');tmp=path.with_suffix('.partial.parquet')
        # Unknown entry time is excluded, not silently backdated to measurement time.
        bounded=f'''SELECT * FROM ({sql}) e WHERE available_hour IS NOT NULL AND event_hour IS NOT NULL
           AND available_hour>=event_hour AND available_hour BETWEEN -168 AND {self.max_hours}
           AND event_hour BETWEEN -168 AND {self.max_hours} AND value IS NOT NULL'''
        self.con.execute(f'COPY ({bounded}) TO {q(tmp)} (FORMAT PARQUET,COMPRESSION ZSTD)');os.replace(tmp,path)
        rows=self.con.execute(f'SELECT feature,COUNT(*) n FROM read_parquet({q(path)}) GROUP BY feature').df()
        self.audit.extend([{'dataset':self.ds,'table':name,**r} for r in rows.to_dict('records')]);self.files.append(path)

    def extract(self):
        self.standard();self.urine();self.support();self.microbiology();self.context();self.treatment_context()
        self.meta.to_parquet(self.out/'metadata.parquet',index=False)
        pd.DataFrame(self.audit).to_csv(self.out/'extraction_counts.csv',index=False)
        self.con.close();return self.files

    def standard(self):
        # Build exact dictionary-based mappings from the pinned ricu version.
        for stem in (['hosp/labevents','icu/chartevents'] if self.ds=='miiv' else ['lab','vitalPeriodic','vitalAperiodic','nurseCharting','respiratoryCharting']):
            raw=self.csv(stem)
            if raw is None:continue
            source=Path(stem).name.lower(); mappings=[]
            for feat,spec in SPEC.items():
                if feat=='UrineOutput':continue
                for item in spec['sources'][self.ds]:
                    if item.get('table','').lower()!=source:continue
                    if self.ds=='miiv':
                        for itemid in np.atleast_1d(item.get('ids',[])).tolist():mappings.append((str(itemid),feat))
                    elif 'ids' in item:
                        for name in np.atleast_1d(item['ids']).tolist():mappings.append((str(name).lower(),feat))
                    elif 'val_var' in item:mappings.append((item['val_var'].lower(),feat))
            if self.ds=='miiv' and source=='chartevents':mappings.extend([('223900','GCS_Verbal'),('223901','GCS_Motor'),('220739','GCS_Eyes'),('226512','Weight')])
            if self.ds=='eicu' and source=='nursecharting':mappings=[('gcs total','GCS'),('admission weight','Weight'),('weight','Weight')]
            if not mappings:continue
            self.con.register('mapping',pd.DataFrame(sorted(set(mappings)),columns=['key','feature']))
            if self.ds=='miiv':
                eh=self.hour('x.charttime'); ah=f'greatest({eh},{self.hour("x.storetime")})'
                # A missing storetime must not acquire an optimistic availability time via greatest(NULL,event).
                ah=f'CASE WHEN x.storetime IS NOT NULL THEN {ah} END'
                join='TRY_CAST(x.stay_id AS BIGINT)=s.stay_id' if source=='chartevents' else 'TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id'
                unit=self.col(raw,'valueuom'); value='TRY_CAST(x.valuenum AS DOUBLE)'
                sql=f'''SELECT s.stay_id,{eh} event_hour,{ah} available_hour,m.feature,{value} AS "value",
                  coalesce({unit},'') unit,'state' kind,CAST(NULL AS DOUBLE) end_hour
                  FROM {raw} x JOIN stays s ON {join} JOIN mapping m ON x.itemid=m.key
                  WHERE {eh} >= -24'''
                # Do not infer normal GCS for an intubated patient; ETT verbal scores stay unknown.
                if source=='chartevents':sql+=' AND NOT (m.feature=\'GCS_Verbal\' AND lower(coalesce(x.value,\'\')) LIKE \'%ett%\')'
            elif source in ['vitalperiodic','vitalaperiodic']:
                # Monitor observation offset is the available timing proxy; no separate receipt field exists.
                fields=[]
                for key,feat in sorted(set(mappings)):
                    if key in self.cols(raw):fields.append(f'({q(feat)},TRY_CAST(x.{ident(key)} AS DOUBLE))')
                if not fields:continue
                sql=f'''SELECT s.stay_id,TRY_CAST(x.observationoffset AS DOUBLE)/60 event_hour,
                  TRY_CAST(x.observationoffset AS DOUBLE)/60 available_hour,m.feature,m.value,'' unit,
                  'state' kind,CAST(NULL AS DOUBLE) end_hour FROM {raw} x JOIN stays s
                  ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id,
                  LATERAL (VALUES {','.join(fields)}) m(feature,value)'''
            else:
                cfg={'lab':('labname','labresult','labresultoffset','labresultrevisedoffset','labmeasurenamesystem'),
                     'nursecharting':('nursingchartcelltypevalname','nursingchartvalue','nursingchartoffset','nursingchartentryoffset',None),
                     'respiratorycharting':('respchartvaluelabel','respchartvalue','respchartoffset','respchartentryoffset',None)}[source]
                key,val,t,entry,u=cfg; unit=self.col(raw,u) if u else "''"
                eh=f'TRY_CAST(x.{t} AS DOUBLE)/60'; ah=f'CASE WHEN TRY_CAST(x.{entry} AS DOUBLE) IS NOT NULL THEN greatest({eh},TRY_CAST(x.{entry} AS DOUBLE)/60) END'
                value=f"TRY_CAST(replace(x.{val},'%','') AS DOUBLE)"
                sql=f'''SELECT s.stay_id,{eh} event_hour,{ah} available_hour,m.feature,{value} AS "value",
                  coalesce({unit},'') unit,'state' kind,CAST(NULL AS DOUBLE) end_hour
                  FROM {raw} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
                  JOIN mapping m ON lower(x.{key})=m.key'''
            self.export(source,sql)

    def urine(self):
        if self.ds=='miiv':
            raw=self.csv('icu/outputevents',True);eh=self.hour('x.charttime')
            ah=f'CASE WHEN x.storetime IS NOT NULL THEN greatest({eh},{self.hour("x.storetime")}) END'
            ids=[226559,226560,226561,226584,226563,226564,226565,226567,226557,226558,227488,227489]
            val='TRY_CAST(x.value AS DOUBLE)*CASE WHEN TRY_CAST(x.itemid AS BIGINT)=227488 THEN -1 ELSE 1 END'
            sql=f'''SELECT s.stay_id,{eh} event_hour,{ah} available_hour,'UrineOutput' feature,{val} AS "value",
              coalesce(x.valueuom,'') unit,'volume' kind,CAST(NULL AS DOUBLE) end_hour
              FROM {raw} x JOIN stays s ON TRY_CAST(x.stay_id AS BIGINT)=s.stay_id
              WHERE TRY_CAST(x.itemid AS BIGINT) IN ({','.join(map(str,ids))})'''
        else:
            raw=self.csv('intakeOutput',True);eh='TRY_CAST(x.intakeoutputoffset AS DOUBLE)/60'
            ah=f'CASE WHEN x.intakeoutputentryoffset IS NOT NULL THEN greatest({eh},TRY_CAST(x.intakeoutputentryoffset AS DOUBLE)/60) END'
            # Never sum outputtotal or nettotal; they contain repeated cumulative values.
            sql=f'''SELECT s.stay_id,{eh} event_hour,{ah} available_hour,'UrineOutput' feature,
              TRY_CAST(x.cellvaluenumeric AS DOUBLE) AS "value",'mL' unit,'volume' kind,CAST(NULL AS DOUBLE) end_hour
              FROM {raw} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
              WHERE lower(coalesce(x.cellpath,'')) LIKE '%output (ml)%'
              AND regexp_matches(lower(coalesce(x.celllabel,'')),'urine|foley|urinary catheter|urethral catheter|straight cath|condom cath|texas cath|nephrost')
              AND NOT regexp_matches(lower(coalesce(x.celllabel,'')),'total|cumul|irrig|dialys|drain')'''
        self.export('urine',sql)

    def support(self):
        if self.ds=='miiv':
            raw=self.csv('icu/inputevents')
            if not raw:return
            eh=self.hour('x.starttime'); ah=f'CASE WHEN x.storetime IS NOT NULL THEN greatest({eh},{self.hour("x.storetime")}) END'
            self.con.register('drugmap',pd.DataFrame([('221906','VasopressorRecorded'),('221289','VasopressorRecorded'),('221749','VasopressorRecorded'),('222315','VasopressorRecorded'),('221662','VasopressorRecorded'),('221653','InotropeRecorded'),('221986','InotropeRecorded')],columns=['id','feature']))
            # Use recorded positive/zero rates; does not reconstruct current infusion from future stop times.
            sql=f'''SELECT s.stay_id,{eh} event_hour,{ah} available_hour,m.feature,
              CASE WHEN TRY_CAST(x.rate AS DOUBLE)>0 THEN 1.0 WHEN TRY_CAST(x.rate AS DOUBLE)=0 THEN 0.0 END AS "value",
              '' unit,'support' kind,CAST(NULL AS DOUBLE) end_hour
              FROM {raw} x JOIN stays s ON TRY_CAST(x.stay_id AS BIGINT)=s.stay_id JOIN drugmap m ON x.itemid=m.id
              WHERE lower(coalesce(x.statusdescription,''))<>'rewritten' '''
        else:
            raw=self.csv('infusionDrug')
            if not raw:return
            rate='coalesce(TRY_CAST(x.drugrate AS DOUBLE),TRY_CAST(x.infusionrate AS DOUBLE))'
            sql=f'''SELECT s.stay_id,TRY_CAST(x.infusionoffset AS DOUBLE)/60 event_hour,
              TRY_CAST(x.infusionoffset AS DOUBLE)/60 available_hour,
              CASE WHEN regexp_matches(lower(x.drugname),{q(PRESSOR_RE)}) THEN 'VasopressorRecorded' ELSE 'InotropeRecorded' END feature,
              CASE WHEN {rate}>0 THEN 1.0 WHEN {rate}=0 THEN 0.0 END AS "value",
              '' unit,'support' kind,CAST(NULL AS DOUBLE) end_hour
              FROM {raw} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
              WHERE regexp_matches(lower(x.drugname),{q(PRESSOR_RE+'|'+INOTROPE_RE)})'''
            # This weight becomes available only when the infusion record is entered.
            if 'patientweight' in self.cols(raw):
                self.export('infusion_weight',f'''SELECT s.stay_id,TRY_CAST(x.infusionoffset AS DOUBLE)/60 event_hour,
                  TRY_CAST(x.infusionoffset AS DOUBLE)/60 available_hour,'Weight' feature,TRY_CAST(x.patientweight AS DOUBLE) AS "value",
                  'kg' unit,'state' kind,CAST(NULL AS DOUBLE) end_hour FROM {raw} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id''')
        self.export('support',sql)

    def microbiology(self):
        # Retrospective specimen-site context, never a confirmed infection-source label.
        stem='hosp/microbiologyevents' if self.ds=='miiv' else 'microLab';raw=self.csv(stem)
        if not raw:return
        if self.ds=='miiv':
            sql=f'''SELECT DISTINCT s.stay_id,{self.hour('x.charttime')} event_hour,x.spec_type_desc AS "text"
              FROM {raw} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id WHERE {self.hour('x.charttime')} BETWEEN 0 AND {self.max_hours}'''
        else:sql=f'''SELECT DISTINCT s.stay_id,TRY_CAST(x.culturetakenoffset AS DOUBLE)/60 event_hour,x.culturesite AS "text"
              FROM {raw} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id WHERE TRY_CAST(x.culturetakenoffset AS DOUBLE)/60 BETWEEN 0 AND {self.max_hours}'''
        d=self.con.execute(sql).df();d['site']=d.text.map(specimen_site)
        d.to_parquet(self.out/'specimen_context.parquet',index=False)

    def context(self):
        queries=[]
        if self.ds=='miiv':
            dx=self.csv('hosp/diagnoses_icd');dd=self.csv('hosp/d_icd_diagnoses')
            if dx and dd:queries.append(f'''SELECT s.stay_id,d.long_title AS "text" FROM {dx} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id JOIN {dd} d ON x.icd_code=d.icd_code AND x.icd_version=d.icd_version''')
            adm=self.csv('hosp/admissions')
            if adm:
                a=self.con.execute(f'''SELECT s.stay_id,x.admission_location admission_source FROM {adm} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id''').df()
                # Hospital entry source is not necessarily the source of a later ICU admission.
                self.meta=self.meta.merge(a,on='stay_id',how='left')
                self.meta['PostoperativeAdmission']=np.nan
        else:
            raw=self.csv('patient');queries.append(f'''SELECT s.stay_id,x.apacheadmissiondx AS "text" FROM {raw} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id''')
            for stem,col in [('diagnosis','diagnosisstring'),('pastHistory','pasthistoryvaluetext')]:
                r=self.csv(stem)
                if r:queries.append(f'SELECT s.stay_id,x.{col} AS "text" FROM {r} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id')
            # Retained as metadata because cross-source matching is not implemented.
            self.meta['PostoperativeAdmission']=np.nan
        flags_by_stay={};writer=None
        if queries:
            evidence_path=self.out/'phenotype_evidence.parquet'
            evidence_schema=pa.schema([('stay_id',pa.int64()),('phenotype',pa.string()),('matched_text',pa.string())])
            writer=pq.ParquetWriter(evidence_path,evidence_schema,compression='zstd')
            try:
                reader=self.con.execute(' UNION ALL '.join(queries)).fetch_record_batch(20000)
                for rb in reader:
                    hits=[]
                    for r in rb.to_pandas().dropna(subset=['text']).itertuples(index=False):
                        flags=text_flags(r.text);prev=flags_by_stay.setdefault(r.stay_id,{k:0 for k in flags})
                        for f,v in flags.items():
                            if v:prev[f]=1;hits.append({'stay_id':int(r.stay_id),'phenotype':f,'matched_text':r.text})
                    if hits:writer.write_table(pa.Table.from_pylist(hits,schema=evidence_schema))
            finally:writer.close()
        rows=[{'stay_id':sid,**flags} for sid,flags in flags_by_stay.items()]
        pd.DataFrame(rows,columns=['stay_id']+['Phenotype_'+k for k in PHENO]).to_parquet(self.out/'phenotypes.parquet',index=False)

        # Keep clinician-documented suspicion separate from the specimen collection site.
        if self.ds=='eicu':
            r=self.csv('carePlanInfectiousDisease')
            if r:
                c=self.con.execute(f'''SELECT s.stay_id,TRY_CAST(x.cplinfectdiseaseoffset AS DOUBLE)/60 documented_hour,
                   x.infectdiseasesite AS "text" FROM {r} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
                   WHERE TRY_CAST(x.cplinfectdiseaseoffset AS DOUBLE)/60 BETWEEN 0 AND {self.max_hours}''').df()
                c['site']=c.text.map(specimen_site);c.to_parquet(self.out/'clinician_source_context.parquet',index=False)

    def treatment_context(self):
        # Order proxies for confounder/error analyses. Orders do not prove administration.
        raw=self.csv('hosp/prescriptions' if self.ds=='miiv' else 'medication')
        if not raw:return
        if self.ds=='miiv':
            sql=f'''SELECT s.stay_id,x.drug AS "text" FROM {raw} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
              WHERE {self.hour('x.starttime')} BETWEEN -24 AND {self.max_hours}'''
        else:
            sql=f'''SELECT s.stay_id,x.drugname AS "text" FROM {raw} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
              WHERE TRY_CAST(x.drugstartoffset AS DOUBLE)/60 BETWEEN -24 AND {self.max_hours}
              AND lower(coalesce(x.drugordercancelled,''))<>'yes' '''
        by_stay={}
        for rb in self.con.execute(sql).fetch_record_batch(20000):
            for r in rb.to_pandas().dropna(subset=['text']).itertuples(index=False):
                text=str(r.text).lower();flags=by_stay.setdefault(r.stay_id,{k:0 for k in MED_CONTEXT})
                for k,p in MED_CONTEXT.items():
                    if re.search(p,text):flags[k]=1
        rows=[{'stay_id':sid,**{'TreatmentContext_'+k:v for k,v in f.items()}} for sid,f in by_stay.items()]
        pd.DataFrame(rows,columns=['stay_id']+['TreatmentContext_'+k for k in MED_CONTEXT]).to_parquet(self.out/'treatment_context.parquet',index=False)

def normalize_events(d):
    d=d.copy();d['value']=pd.to_numeric(d.value,errors='coerce')
    u=d.unit.fillna('').str.lower().str.replace(' ','',regex=False)
    # Explicit conversions; unit discrepancies are retained in an audit by the caller.
    f=d.feature
    d.loc[f.eq('Temp')&u.isin(['f','°f','degf']),'value']=(d.value-32)*5/9
    d.loc[f.eq('FiO2')&d.value.between(.2,1),'value']*=100
    # eICU reports ionized calcium in mg/dL (~4-5); the channel is mmol/L (same 4x factor as total Calcium).
    for name,factor,units in [('Calcium',4.,['mmol/l']),('CalciumIonized',.25,['mg/dl']),('Magnesium',1/1.215,['meq/l']),('CRP',10.,['mg/dl'])]:
        d.loc[f.eq(name)&u.isin(units),'value']*=factor
    # Reject known incompatible units instead of accepting by numeric appearance.
    allowed={
      'Albumin':{'g/dl'},'Bilirubin_total':{'mg/dl'},'Bilirubin_direct':{'mg/dl'},'Creatinine':{'mg/dl'},
      'BUN':{'mg/dl'},'Glucose':{'mg/dl'},'Lactate':{'mmol/l'},'Magnesium':{'mg/dl','meq/l'},
      'Calcium':{'mg/dl','mmol/l'},'CalciumIonized':{'mmol/l','mg/dl'},'CRP':{'mg/l','mg/dl'},'Phosphate':{'mg/dl'},'Weight':{'kg'},
      'UrineOutput':{'ml'},'FiO2':{'%','fraction',''},'Temp':{'c','°c','degc','f','°f','degf'}}
    for name,units in allowed.items():
        bad=f.eq(name)&~u.isin(units|{''});d.loc[bad,'value']=np.nan
    for name,s in SPEC.items():
        if name=='UrineOutput':continue
        ix=f.eq(name);lo=s.get('min');hi=s.get('max')
        if isinstance(lo,(float,int)):d.loc[ix&d.value.lt(lo),'value']=np.nan
        if isinstance(hi,(float,int)):d.loc[ix&d.value.gt(hi),'value']=np.nan
    bounds={'Weight':(20,500),'GCS':(3,15),'GCS_Eyes':(1,4),'GCS_Verbal':(1,5),'GCS_Motor':(1,6)}
    for name,(lo,hi) in bounds.items():d.loc[f.eq(name)&~d.value.between(lo,hi),'value']=np.nan
    return d.dropna(subset=['value','event_hour','available_hour'])

def latest_known(events,hours,ttl=24.):
    """Latest observation known by each cutoff, with stale values becoming unknown.
    An old observation entered late cannot overwrite a newer known observation.
    """
    vals=np.full(len(hours),np.nan);ages=np.full(len(hours),np.nan)
    if events.empty:return vals,ages
    z=events.sort_values(['event_hour','available_hour']).reset_index(drop=True)
    z['rank']=np.arange(len(z));av=z.sort_values(['available_hour','rank'])
    ranks=np.maximum.accumulate(av['rank'].to_numpy())
    idx=np.searchsorted(av.available_hour.to_numpy(),hours,side='right')-1;ok=idx>=0
    if ok.any():
        picked=z.iloc[ranks[idx[ok]]];age=hours[ok]-picked.event_hour.to_numpy()
        values=picked.value.to_numpy().astype(float);values[(age<0)|(age>ttl)]=np.nan
        vals[ok]=values;ages[ok]=age
    return vals,ages

def urine_features(events,hours,weight):
    """Rolling urine volume/coverage known at each cutoff; numpy version of v9 loop.
    Window (t-w,t] by measurement time AND available by t. Irrigant input is negative
    and is netted before interpretation; a negative net is unknown, never zero.
    """
    out={f:np.full(len(hours),np.nan) for f in RENAL}
    e=events.event_hour.to_numpy(float);a=events.available_hour.to_numpy(float);v=events.value.to_numpy(float)
    ce=np.ceil(e)
    for i,t in enumerate(hours):
        for window in [1,6,24]:
            m=(a<=t)&(e>t-window)&(e<=t)
            val=v[m].sum() if m.any() else np.nan
            if np.isfinite(val) and val<0:val=np.nan
            out['UrineOutput' if window==1 else f'UrineOutput_{window}h'][i]=val
            if window>1:out[f'UrineCoverage_{window}h'][i]=len(np.unique(ce[m]))
        cov=out['UrineCoverage_6h'][i]
        if t>=6 and cov==6 and np.isfinite(weight[i]) and weight[i]>0 and np.isfinite(out['UrineOutput_6h'][i]):
            out['Urine_mlkg_h_6h'][i]=out['UrineOutput_6h'][i]/(6*weight[i])
            out['Oliguria6h'][i]=float(out['Urine_mlkg_h_6h'][i]<.5)
    return out

def support_features(z,hours):
    """Any positive-rate record known in the preceding hour (max over records), and
    hours since the latest such record; a zero for one drug cannot erase a positive."""
    e=z.event_hour.to_numpy(float);a=z.available_hour.to_numpy(float);v=z.value.to_numpy(float)
    values=np.full(len(hours),np.nan);age=np.full(len(hours),np.nan)
    for i,t in enumerate(hours):
        m=(a<=t)&(e>t-1)&(e<=t)
        if m.any():values[i]=v[m].max();age[i]=t-e[m].max()
    return values,age

def build_sequence(events,meta,max_hours=120,horizon=6):
    end=min(max_hours,int(np.floor(meta['followup_end'])))
    hours=np.arange(1,end+1,dtype=float)
    d=pd.DataFrame({'Hour':hours});ages={}
    for feat in BASE+SUPPORT+['GCS_Eyes','GCS_Verbal','GCS_Motor']:
        if feat in ['Age','Gender','PostoperativeAdmission']:continue
        z=events[events.feature.eq(feat)]
        if feat in SUPPORT:
            d[feat],ages[feat]=support_features(z,hours);continue
        # Body weight changes slowly and is often charted once: no 24 h expiry
        # (v10.2), otherwise weight-normalised urine output vanished after day 1.
        ttl=(6. if feat in ['HR','SBP','DBP','MAP','Temp','Resp','O2Sat','FiO2','GCS','GCS_Eyes','GCS_Verbal','GCS_Motor']
             else float(max_hours+168) if feat=='Weight' else 24.)
        d[feat],ages[feat]=latest_known(z,hours,ttl)
    # Both databases require observed GCS components/total; intubated verbal scores are not imputed normal.
    components=d[['GCS_Eyes','GCS_Verbal','GCS_Motor']]
    complete=components.notna().all(axis=1)
    d.loc[d.GCS.isna()&complete,'GCS']=components.sum(axis=1)
    ca=np.stack([ages[k] for k in ['GCS_Eyes','GCS_Verbal','GCS_Motor']])
    component_age=np.max(np.where(np.isfinite(ca),ca,-np.inf),axis=0);component_age[~np.isfinite(component_age)]=np.nan
    ages['GCS']=np.where(np.isnan(ages['GCS'])&complete.to_numpy(),component_age,ages['GCS'])
    d=d.drop(columns=['GCS_Eyes','GCS_Verbal','GCS_Motor'])
    d['Age']=meta.get('Age',np.nan);d['Gender']=meta.get('Gender',np.nan)
    for feat,v in urine_features(events[events.feature.eq('UrineOutput')],hours,d.Weight.to_numpy()).items():d[feat]=v
    def criterion(cols,predicate):
        obs=d[cols].notna().any(axis=1);return predicate().astype(float).where(obs)
    d['SIRS_Temp']=criterion(['Temp'],lambda:(d.Temp<36)|(d.Temp>38))
    d['SIRS_HR']=criterion(['HR'],lambda:d.HR>90)
    # An OR criterion is positive if any observed term is positive; a negative
    # requires both terms observed. A missing alternative is not assumed normal.
    rpos=(d.Resp>20)|(d.PaCO2<32);wpos=(d.WBC<4)|(d.WBC>12)|(d.Bands>10)
    d['SIRS_Resp']=np.where(rpos,1.,np.where(d[['Resp','PaCO2']].notna().all(axis=1),0.,np.nan))
    d['SIRS_WBC']=np.where(wpos,1.,np.where(d[['WBC','Bands']].notna().all(axis=1),0.,np.nan))
    comps=d[['SIRS_Temp','SIRS_HR','SIRS_Resp','SIRS_WBC']]
    d['SIRS_ObservedComponents']=comps.notna().sum(axis=1)
    d['SIRS_Count']=comps.sum(axis=1,min_count=4) # incomplete count is unknown; individual observed criteria remain usable
    d['ShockIndex']=(d.HR/d.SBP).where(d.SBP>0)
    extras={feat+'_age':age for feat,age in ages.items() if feat in BASE+SUPPORT}
    # Explicit masks survive imputation and reach every model and observer.
    extras.update({feat+'_observed':d[feat].notna().astype(float) for feat in PRIMARY})
    d=pd.concat([d,pd.DataFrame(extras,index=d.index)],axis=1)
    onset=meta['OnsetHour'];follow=meta['followup_end']
    at_risk=np.ones(len(d),bool) if pd.isna(onset) else hours<onset
    known_future=(hours+horizon<=follow) if pd.isna(onset) else ((hours+horizon<=follow)|(hours+horizon>=onset))
    d['Eligible']=(at_risk&known_future).astype(int)
    d['SepsisLabel']=((onset>hours)&(onset<=hours+horizon)).astype(int) if pd.notna(onset) else 0
    # No post-onset histories are needed for this incident-sepsis task.
    return engineer_one(d[at_risk].reset_index(drop=True))

def build_shards(ds,stage,cohort_folder,out,max_hours=120,horizon=6,batch=32):
    stage=Path(stage);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    meta=pd.read_parquet(stage/'metadata.parquet');static=pd.read_parquet(Path(cohort_folder)/'sta.parquet')
    cols=['stay_id']+[c for c in ['age','sex'] if c in static]
    static=static[cols].rename(columns={'age':'Age'}).drop_duplicates('stay_id')
    if 'sex' in static:
        s=static.sex.astype(str).str.lower();static['Gender']=s.map({'male':1.,'m':1.,'1':1.,'1.0':1.,'true':1.,'female':0.,'f':0.,'0':0.,'0.0':0.,'false':0.})
        static=static.drop(columns='sex')
    meta=meta.merge(static,on='stay_id',how='left',validate='one_to_one')
    meta['Dataset']=ds;meta['Patient_ID']=ds+'|'+meta.stay_id.astype(str);meta['Group_ID']=ds+'|'+meta.person.astype(str);meta['Hospital_ID']=meta.hospital.astype(str)
    ph=pd.read_parquet(stage/'phenotypes.parquet')
    if len(ph):meta=meta.merge(ph,on='stay_id',how='left',validate='one_to_one')
    treatment=stage/'treatment_context.parquet'
    if treatment.is_file():
        c=pd.read_parquet(treatment)
        if len(c):meta=meta.merge(c,on='stay_id',how='left',validate='one_to_one')
    clinician=stage/'clinician_source_context.parquet'
    if clinician.is_file():
        c=pd.read_parquet(clinician);c['value']=1
        if len(c):meta=meta.merge(c.pivot_table(index='stay_id',columns='site',values='value',aggfunc='max').add_prefix('ClinicianSuspectedSite_').reset_index(),on='stay_id',how='left',validate='one_to_one')
    context=stage/'specimen_context.parquet'
    if context.is_file():
        c=pd.read_parquet(context);c['value']=1
        if len(c):
            w=c.pivot_table(index='stay_id',columns='site',values='value',aggfunc='max').add_prefix('SpecimenSite_').reset_index()
            meta=meta.merge(w,on='stay_id',how='left',validate='one_to_one')
    for c in ['Phenotype_'+k for k in PHENO]+['SpecimenSite_'+s for s in SITES]:
        if c not in meta:meta[c]=0
        meta[c]=meta[c].fillna(0).astype(int) # means no matching documentation, not clinical absence
    eventpaths=[p for p in stage.glob('*.parquet') if p.stem not in ['metadata','phenotypes','phenotype_evidence','specimen_context','clinician_source_context','treatment_context']]
    con=duckdb.connect();con.execute("SET memory_limit='1GB'");con.execute('SET threads=1')
    index=[];schema=None;counts={};unit_counts=[];parts_dir=out/'parts';parts_dir.mkdir(exist_ok=True)
    reused=0
    for start in range(0,len(meta),batch):
        chunk=meta.iloc[start:start+batch];name=f'{ds}_{start//batch:05d}.parquet';dest=out/name
        # Per-batch resume: a batch is reused only when its exact stay list matches.
        contract={'version':VERSION,'stays':[int(x) for x in chunk.stay_id],'max_hours':max_hours,'horizon':horizon}
        done=parts_dir/(name+'.done.json')
        if done.is_file():
            rec=json.loads(done.read_text())
            if rec.get('contract')==contract and (not rec['index'] or dest.is_file()):
                index.extend(rec['index']);reused+=1
                if rec['schema'] is not None:
                    if schema is None:schema=rec['schema']
                    assert rec['schema']==schema
                for f,(x,y) in rec['counts'].items():a,b=counts.get(f,(0,0));counts[f]=(a+x,b+y)
                if rec['units']:unit_counts.append(pd.DataFrame(rec['units']))
                continue
        con.register('batchids',chunk[['stay_id']])
        if eventpaths:
            rel='read_parquet(['+','.join(q(p) for p in eventpaths)+'],union_by_name=true)'
            events=con.execute(f'SELECT e.* FROM {rel} e JOIN batchids b USING(stay_id)').df()
        else:events=pd.DataFrame(columns=['stay_id','event_hour','available_hour','feature','value','unit','kind','end_hour'])
        uq=None
        if len(events):
            uq=events.groupby(['feature','unit'],dropna=False).size().reset_index(name='n');unit_counts.append(uq)
        events=normalize_events(events);groups={sid:g for sid,g in events.groupby('stay_id')};parts=[];offset=0
        batch_index=[];batch_counts={};batch_schema=None
        for row in chunk.to_dict('records'):
            e=groups.get(row['stay_id'],events.iloc[:0]);seq=build_sequence(e,row,max_hours,horizon)
            if seq.empty or not seq.Eligible.any():continue
            feats=[c for c in seq if c not in ['Hour','Eligible','SepsisLabel']]
            if schema is None:schema=feats
            assert feats==schema;batch_schema=feats
            seq=seq.astype({c:'float32' for c in feats}).copy()
            seq.insert(0,'Patient_ID',row['Patient_ID']);parts.append(seq)
            batch_index.append({**row,'file':str(dest),'offset':offset,'length':len(seq),'eligible_positive':int(seq.SepsisLabel[seq.Eligible.eq(1)].max())})
            offset+=len(seq)
            for f in PRIMARY:
                a,b=batch_counts.get(f,(0,0));batch_counts[f]=(a+int(seq[f].notna().sum()),b+len(seq))
        if parts:
            tmp=dest.with_suffix('.partial.parquet');pd.concat(parts,ignore_index=True).to_parquet(tmp,index=False,compression='zstd');os.replace(tmp,dest)
        rec={'contract':contract,'index':json.loads(pd.DataFrame(batch_index).to_json(orient='records',date_format='iso')) if batch_index else [],
             'schema':batch_schema,'counts':batch_counts,'units':json.loads(uq.to_json(orient='records')) if uq is not None else []}
        tmp=done.with_suffix('.partial');tmp.write_text(json.dumps(rec));os.replace(tmp,done)
        index.extend(rec['index'])
        for f,(x,y) in batch_counts.items():a,b=counts.get(f,(0,0));counts[f]=(a+x,b+y)
        if start%1024==0:print(ds,'hourly features:',min(start+batch,len(meta)),'/',len(meta),flush=True)
        del events,groups,parts;gc.collect()
    if reused:print(ds,'reused completed feature batches:',reused,flush=True)
    con.close()
    ix=pd.DataFrame(index);ix.to_parquet(out/'index.parquet',index=False)
    (out/'schema.json').write_text(json.dumps(schema,indent=2))
    pd.DataFrame([{'dataset':ds,'feature':f,'observed_rows':a,'rows':b,'missing_fraction':1-a/b if b else np.nan} for f,(a,b) in counts.items()]).to_csv(out/'coverage.csv',index=False)
    if unit_counts:pd.concat(unit_counts).groupby(['feature','unit'],dropna=False)['n'].sum().reset_index().to_csv(out/'units.csv',index=False)
    return ix,schema

def raw_stage_key(cohort_key,max_hours):
    """Contract for the raw-table event stage. Depends only on the extraction code and
    mappings, so feature-engineering changes do not force new full raw-table scans, and
    the legacy notebook can reuse the main notebook's stage for the same cohort."""
    import inspect
    code=''.join(inspect.getsource(o) for o in [RawExtractor,csv_scan,table,text_flags,specimen_site])
    return signature({'cohort':cohort_key,'max_hours':max_hours,'dialect':CSV_DIALECT,'spec':SPEC,
        'patterns':[SITE_PATTERNS,PHENO,MED_CONTEXT,PRESSOR_RE,INOTROPE_RE],'code':hashlib.sha256(code.encode()).hexdigest()})[:16]
