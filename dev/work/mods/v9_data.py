"""Version 9: bounded raw-table extraction and availability-aware hourly features.
YAIB supplies cohort membership and labels, not the predictor timestamps.
"""
from pathlib import Path
import json, hashlib, re, gc, os, warnings, functools
import numpy as np
import pandas as pd
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

VERSION='v10.4'
from v10_features import engineer_one, ENGINEERED
SPEC=json.loads((Path(__file__).parent/'feature_specs.json').read_text())
# PostoperativeAdmission is not comparably available in either release; it is kept
# as metadata only (always missing), not as a model predictor (v10.2).
BASE=[x for x in SPEC if x!='UrineOutput']+['GCS','Weight','Age','Gender']
SUPPORT=['VasopressorRecorded','InotropeRecorded']
# Invasive artificial airway (endotracheal tube or tracheostomy) as a charted state, and the
# cumulative documented hours with it (ventilator-associated infection exposure), v10.3.
AIRWAY=['Intubated','IntubatedHours']
RENAL=['UrineOutput','UrineOutput_6h','UrineOutput_24h','UrineCoverage_6h','UrineCoverage_24h','Urine_mlkg_h_6h','Oliguria6h',
       'UrineCoverageFraction_6h','Urine_HoursSinceLast']
DERIVED=['SIRS_Temp','SIRS_HR','SIRS_Resp','SIRS_WBC','SIRS_ObservedComponents','SIRS_Count','ShockIndex','GCS_Below15']
DERIVED+=['PF_Ratio','SF_Ratio']
# v10.4 (user: include every feature that could predict sepsis). Admission context is known at
# ICU admission; the admitting diagnosis (eICU admissionDx) from its entry time (MIMIC-IV has none).
ADMISSION=['HospitalHoursBeforeICU','AdmitSource_ED','AdmitSource_OR','AdmitSource_Ward','AdmitSource_OtherHospital',
           'ICUType_Medical','ICUType_Surgical','ICUType_Cardiac','ICUType_Neuro','AdmitDx_Infection','AdmitDx_Operative']
PRIMARY=BASE+SUPPORT+AIRWAY+RENAL+DERIVED+ADMISSION
# Documented exposures (0 = not documented by that hour; no masks), each from its own timestamp.
DEVICE_PATTERNS={
 'CentralLine':r'multi lumen|picc|cordis|introducer|central (?:venous )?(?:line|catheter)|indwelling port|portacath|trauma line|swan|pulmonary artery catheter|pa catheter|tunneled|midline',
 'ArterialLine':r'arterial line|art line|arterial catheter',
 'DialysisCatheter':r'dialysis catheter|hemodialysis catheter|trialysis|quinton',
 'UrinaryCatheter':r'foley|urinary catheter|indwelling catheter|suprapubic|nephrostomy|urethral catheter',
 'Drain':r'chest tube|thoracostomy|pigtail|\bdrain\b|drainage catheter|jackson|\bjp\b|percutaneous drain'}
DEVICE_EXCLUDE=r'remov|discontinu|\bdc\b|pulled|non-invasive|noninvasive'
# Medications that change risk or mask the host response. Antibiotics are NOT predictors: antibiotic
# timing defines the Sepsis-3 suspicion of infection (the label). Hydrocortisone kept separate because
# stress-dose steroids often follow shock (sensitivity analysis can drop it).
MED_FEATURES={
 'Immunosuppressant':r'tacrolimus|cyclosporin|mycophenol|sirolimus|everolimus|azathioprine|rituximab|infliximab|tocilizumab|basiliximab|thymoglobulin|antithymocyte|belatacept|alemtuzumab',
 'Chemotherapy':r'cyclophosphamide|doxorubicin|cisplatin|carboplatin|oxaliplatin|paclitaxel|docetaxel|gemcitabine|fluorouracil|capecitabine|cytarabine|etoposide|vincristine|methotrexate|ifosfamide|bendamustine|azacitidine|decitabine|daunorubicin|idarubicin|irinotecan|pemetrexed',
 'Corticosteroid':r'prednis|methylpred|dexamethasone|fludrocortisone',
 'Hydrocortisone':r'hydrocortisone',
 'BetaBlocker':r'metoprolol|atenolol|carvedilol|labetalol|esmolol|propranolol|bisoprolol|nadolol|sotalol',
 'Antipyretic':r'acetaminophen|paracetamol|ibuprofen|ketorolac',
 'Sedative':r'propofol|midazolam|lorazepam|dexmedetomidine|ketamine|diazepam',
 'Opioid':r'fentanyl|morphine|hydromorphone|oxycodone|remifentanil|methadone',
 'Diuretic':r'furosemide|bumetanide|torsemide|chlorothiazide|metolazone|acetazolamide'}
MED_EXCLUDE=r'cream|ointment|topical|ophth|otic|eye drop|lotion|enema|suppository|rectal foam|nasal spray|inhal'
IMAGING_RE=r'radiolog|x-ray|xray|\bct\b|ct scan|computed tomograph|\bmri\b|ultrasound|echocardiog|imaging'
FLUID_IN_EXCLUDE=r'enteral|tube feed|feeding|oral|\bpo\b|nutrition|tpn|flush'
TRANSFUSION_RE=r'blood|prbc|packed (?:red|cell)|platelet|\bffp\b|plasma|cryo'
INFECTION_DX_RE=r'sepsis|septic|pneumonia|infect|cellulitis|urinary tract|\buti\b|meningitis|encephalitis|endocarditis|abscess|peritonitis|cholangitis|cholecystitis|pyelonephritis|fasciitis|empyema|osteomyelitis|bacteremia'
DEVICES=['Device_'+k for k in DEVICE_PATTERNS]
EXPOSURES=(DEVICES+[d+'_Hours' for d in DEVICES]+['Med_'+k+'_24h' for k in MED_FEATURES]
           +['Imaging_24h','FluidIn_6h','FluidIn_24h','Transfusion_24h'])
# Carry-forward windows (hours) for latest_known (v10.3, user decision): vitals and labs 24 h;
# GCS and its components until the next measurement; weight never expires.
NO_EXPIRY=['GCS','GCS_Eyes','GCS_Verbal','GCS_Motor','Weight']
# An ETT verbal entry is exported as this marker: it RESETS the verbal component to unknown.
VERBAL_ETT=-1.
# Each record documents urine since the previous record; longer gaps are not distributed.
URINE_MAX_INTERVAL=12.
URINE_MIN_COVERED_HOURS=4.
# Chronic comorbidities (TREWScore list in the user's module). Flags are 1 from the hour their
# documentation is available, else 0 ("not documented", not clinical absence).
# ICD patterns (codes without dots) follow the Quan 2005 Elixhauser/Charlson coding where one exists.
COMORBIDITY_ICD={
 'chronic_heart_failure':(r'^(I099|I110|I130|I132|I255|I420|I42[5-9]|I43|I50|P290)',
    r'^(39891|40201|40211|40291|4040[13]|4041[13]|4049[13]|425[4-9]|428)'),
 'chronic_liver_disease_cirrhosis':(r'^(B18|I85|I864|I982|K70|K711|K71[3-57]|K72[19]|K73|K74|K760|K76[2-9]|Z944)',
    r'^(0702[23]|0703[23]|07044|07054|0706|0709|456[0-2]|571|572[2-8]|573[3489]|V427)'),
 'diabetes':(r'^(E0[89]|E1[0-3])',r'^250'),
 'metastatic_carcinoma':(r'^(C7[7-9]|C80)',r'^(19[6-9])'),
 'hematological_malignancy':(r'^(C8[1-9]|C9[0-6]|D4[56])',r'^(20[0-8]|2384|2387[2-5])'),
 'immunocompromised':(r'^(B2[0-4]|D8[0-4]|D70|D730|Z9081|Z94[0-689]|T86|Z7952|Z796|Z9221|Z5111)',
    r'^(042|279|2880|V42[0-46-9]|99680|9968[1-9]|V5865|V5811|V8741)'),
 # Chronic dialysis/ESRD and chronic respiratory failure or home oxygen/respirator dependence.
 'chronic_organ_insufficiency':(r'^(N185|N186|Z992|Z49|Z9115|J961|J962|Z9981|Z991)',
    r'^(5855|5856|V4511|V56|51883|51884|V461|V462)')}
COMORBIDITY_TEXT={
 'chronic_heart_failure':r'congestive heart failure|\bchf\b|heart failure|cardiomyopathy',
 'chronic_liver_disease_cirrhosis':r'cirrhosis|chronic liver|chronic hepatitis|portal hypertension|varices',
 'diabetes':r'diabet(?!es insipidus)',
 'metastatic_carcinoma':r'metasta',
 'hematological_malignancy':r'leukemia|lymphoma|myeloma|myelodysplas|hematologic malignancy|hodgkin',
 'immunocompromised':r'immunosupp|immunocompromis|immunodeficien|neutropeni|\bhiv\b|\baids\b|transplant|chemotherapy|chronic steroid|steroid use',
 'chronic_organ_insufficiency':r'hemodialysis|peritoneal dialysis|end[- ]stage renal|\besrd\b|chronic respiratory failure|home oxygen|home o2|copd - severe|severe copd'}
COMORBID=['Comorbidity_'+k for k in COMORBIDITY_ICD]
# MIMIC-IV O2 delivery device (itemid 226732): invasive airway vs documented other/no device.
AIRWAY_YES=r'endotracheal|tracheostomy|trach mask|t-piece'
AIRWAY_NO=r'none|nasal cannula|face tent|non-rebreather|venti mask|aerosol|high flow|bipap|cpap|oxymizer|mask|vapotherm|room air'
# MIMIC-IV procedure items resolved by label from d_items: start/placement vs removal.
PROCEDURE_AIRWAY_YES=r'^intubation$|^invasive ventilation$|tracheostomy'
PROCEDURE_AIRWAY_NO=r'extubation'
# eICU treatment entries (entered at treatmentoffset).
EICU_TREATMENT_YES=r'mechanical ventilation|endotracheal|intubation|tracheostomy'
EICU_TREATMENT_NO=r'non-invasive|noninvasive|extubat'
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

@functools.lru_cache(maxsize=None)
def comorbidity_flags(code=None,version=None,text=None):
    """Set of comorbidity names matched by one ICD code (version 9/10; inferred from the
    first character when not given) and/or one free-text documentation string."""
    hits=set()
    code=None if isinstance(code,float) and np.isnan(code) else code
    text=None if isinstance(text,float) and np.isnan(text) else text
    for c in re.split(r'[,;]',str(code or '')):
        c=c.strip().upper().replace('.','')
        if not c:continue
        v=int(version) if version not in (None,'') and str(version).strip() not in ('','nan') else (9 if c[0].isdigit() or c[0]=='V' else 10)
        hits|={k for k,(p10,p9) in COMORBIDITY_ICD.items() if re.search(p10 if v==10 else p9,c)}
    if text:
        t=str(text).lower()
        if not re.search(r'\b(?:no|denies|without|rule out|ruled out|family history)\b|no health problems',t):
            hits|={k for k,p in COMORBIDITY_TEXT.items() if re.search(p,t)}
    return frozenset(hits)

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
        self.standard();self.urine();self.support();self.airway();self.admission_weight();self.comorbidity()
        self.exposures();self.admission_diagnosis()
        self.microbiology();self.context();self.admission_context();self.treatment_context()
        self.meta.to_parquet(self.out/'metadata.parquet',index=False)
        pd.DataFrame(self.audit).to_csv(self.out/'extraction_counts.csv',index=False)
        self.con.close();return self.files

    def miiv_dictionary(self,source):
        """MIMIC-IV item dictionary (itemid, label) for one event table; empty if absent."""
        d=self.csv('hosp/d_labitems' if source=='labevents' else 'icu/d_items')
        if d is None:return pd.DataFrame(columns=['itemid','label','fluid'])
        where=f"WHERE lower(coalesce({self.col(d,'linksto')},''))={q(source)}" if source!='labevents' and 'linksto' in self.cols(d) else ''
        fluid=f'CAST({self.col(d,"fluid")} AS VARCHAR)' if source=='labevents' else "''"
        return self.con.execute(f'SELECT CAST(x.itemid AS VARCHAR) AS "itemid",CAST(x."label" AS VARCHAR) AS "label",{fluid} AS "fluid" FROM {d} x {where}').df()

    def standard(self):
        # Build exact dictionary-based mappings from the pinned ricu version, plus the v10.3
        # additions (eICU nurse-charted and cuff vitals, Hct, EtCO2, SaO2, Troponin I, airway).
        # A mapping is (key, feature, unit override, required eICU nurse-charting label).
        audit=[]
        for stem in (['hosp/labevents','icu/chartevents'] if self.ds=='miiv' else ['lab','vitalPeriodic','vitalAperiodic','nurseCharting','respiratoryCharting']):
            raw=self.csv(stem)
            if raw is None:continue
            source=Path(stem).name.lower(); mappings=[]
            labels=self.miiv_dictionary(source) if self.ds=='miiv' else None
            for feat,spec in SPEC.items():
                if feat=='UrineOutput':continue
                for item in spec['sources'][self.ds]:
                    if item.get('table','').lower()!=source:continue
                    unit=str(item.get('unit','')).lower()
                    if self.ds=='miiv':
                        ids=[str(i) for i in np.atleast_1d(item.get('ids',[])).tolist()]
                        if 'label_regex' in item and len(labels):
                            lab=labels.label.fillna('').str.lower()
                            hit=lab.str.contains(item['label_regex'],regex=True)
                            if 'exclude_regex' in item:hit&=~lab.str.contains(item['exclude_regex'],regex=True)
                            if 'fluid_regex' in item:hit&=labels.fluid.fillna('').str.lower().str.contains(item['fluid_regex'],regex=True)
                            ids+=labels.itemid[hit].tolist()
                        for itemid in ids:mappings.append((itemid,feat,unit,''))
                    elif 'ids' in item:
                        for name in np.atleast_1d(item['ids']).tolist():mappings.append((str(name).lower(),feat,unit,''))
                    elif 'val_var' in item:mappings.append((item['val_var'].lower(),feat,unit,''))
            if self.ds=='miiv' and source=='chartevents':
                # 224639 daily weight; 226531 admission weight charted in pounds.
                mappings.extend([('223900','GCS_Verbal','',''),('223901','GCS_Motor','',''),('220739','GCS_Eyes','',''),
                    ('226512','Weight','',''),('224639','Weight','',''),('226531','Weight','lbs',''),
                    ('223900','Intubated','',''),('226732','Intubated','','')])
            if self.ds=='eicu' and source=='nursecharting':
                g='glasgow coma score'
                mappings.extend([('gcs total','GCS','',''),('eyes','GCS_Eyes','',g),('motor','GCS_Motor','',g),('verbal','GCS_Verbal','',g),
                    ('admission weight','Weight','',''),('weight','Weight','','')])
            if not mappings:continue
            mapping=pd.DataFrame(sorted(set(mappings)),columns=['key','feature','unit','label'])
            if self.ds=='miiv':
                audit.append(mapping.drop(columns='label').assign(source=source).merge(labels.rename(columns={'itemid':'key','label':'item_label'}),on='key',how='left'))
            self.con.register('mapping',mapping)
            if self.ds=='miiv':
                eh=self.hour('x.charttime'); ah=f'greatest({eh},{self.hour("x.storetime")})'
                # A missing storetime must not acquire an optimistic availability time via greatest(NULL,event).
                ah=f'CASE WHEN x.storetime IS NOT NULL THEN {ah} END'
                join='TRY_CAST(x.stay_id AS BIGINT)=s.stay_id' if source=='chartevents' else 'TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id'
                unit=f"CASE WHEN m.unit<>'' THEN m.unit ELSE coalesce({self.col(raw,'valueuom')},'') END"
                value='TRY_CAST(x.valuenum AS DOUBLE)'
                if source=='chartevents':
                    text="lower(coalesce(x.value,''))"
                    # Intubated verbal GCS is not imputed: an ETT entry is exported as a reset marker
                    # (the verbal component becomes unknown). The same entry documents an artificial
                    # airway; a scored (non-ETT) verbal response or another O2 device documents none.
                    value=f'''CASE WHEN m.feature='GCS_Verbal' AND {text} LIKE '%ett%' THEN {VERBAL_ETT}
                      WHEN m.feature='Intubated' AND x.itemid='223900' THEN CASE WHEN {text} LIKE '%ett%' THEN 1.0
                           WHEN TRY_CAST(x.valuenum AS DOUBLE) IS NOT NULL THEN 0.0 END
                      WHEN m.feature='Intubated' THEN CASE WHEN regexp_matches({text},{q(AIRWAY_YES)}) THEN 1.0
                           WHEN regexp_matches({text},{q(AIRWAY_NO)}) THEN 0.0 END
                      ELSE {value} END'''
                sql=f'''SELECT s.stay_id,{eh} event_hour,{ah} available_hour,m.feature,{value} AS "value",
                  {unit} unit,'state' kind,CAST(NULL AS DOUBLE) end_hour
                  FROM {raw} x JOIN stays s ON {join} JOIN mapping m ON x.itemid=m.key
                  WHERE {eh} >= -24'''
            elif source in ['vitalperiodic','vitalaperiodic']:
                # Monitor observation offset is the available timing proxy; no separate receipt field exists.
                fields=[]
                for key,feat,_,_ in sorted(set(mappings)):
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
                unit=f"CASE WHEN m.unit<>'' THEN m.unit ELSE coalesce({unit},'') END"
                eh=f'TRY_CAST(x.{t} AS DOUBLE)/60'; ah=f'CASE WHEN TRY_CAST(x.{entry} AS DOUBLE) IS NOT NULL THEN greatest({eh},TRY_CAST(x.{entry} AS DOUBLE)/60) END'
                value=f"TRY_CAST(replace(x.{val},'%','') AS DOUBLE)"
                # 'Eyes'/'Motor'/'Verbal' are GCS components only under the Glasgow coma score label.
                label=(f"AND (m.label='' OR lower(coalesce({self.col(raw,'nursingchartcelltypevallabel')},''))=m.label)"
                       if source=='nursecharting' else '')
                sql=f'''SELECT s.stay_id,{eh} event_hour,{ah} available_hour,m.feature,{value} AS "value",
                  {unit} unit,'state' kind,CAST(NULL AS DOUBLE) end_hour
                  FROM {raw} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
                  JOIN mapping m ON lower(x.{key})=m.key {label}'''
            self.export(source,sql)
        # Dictionary audit (item IDs and labels only, no patient data) to verify the mapped items.
        if audit:pd.concat(audit,ignore_index=True).to_csv(self.out/'item_dictionary.csv',index=False)

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

    def airway(self):
        """Invasive artificial airway (ETT or tracheostomy) documentation outside chartevents:
        MIMIC-IV procedure items (resolved by label), eICU respiratory care airway type and
        treatment entries. 1 = airway documented, 0 = removal/non-invasive support documented."""
        if self.ds=='miiv':
            raw=self.csv('icu/procedureevents')
            if raw is None:return
            items=self.miiv_dictionary('procedureevents');lab=items.label.fillna('').str.lower()
            yes=items.itemid[lab.str.contains(PROCEDURE_AIRWAY_YES,regex=True)&~lab.str.contains('non-invasive|noninvasive',regex=True)].tolist()
            no=items.itemid[lab.str.contains(PROCEDURE_AIRWAY_NO,regex=True)].tolist()
            if not yes+no:return
            items[items.itemid.isin(yes+no)].assign(feature='Intubated',value=lambda x:x.itemid.isin(yes).astype(float)).to_csv(self.out/'airway_items.csv',index=False)
            eh=self.hour('x.starttime');ah=f'CASE WHEN x.storetime IS NOT NULL THEN greatest({eh},{self.hour("x.storetime")}) END'
            # Start/placement time only: a recorded end time may have been entered later.
            sql=f'''SELECT s.stay_id,{eh} event_hour,{ah} available_hour,'Intubated' feature,
              CASE WHEN x.itemid IN ({','.join(map(q,yes)) or "''"}) THEN 1.0 ELSE 0.0 END AS "value",
              '' unit,'state' kind,CAST(NULL AS DOUBLE) end_hour
              FROM {raw} x JOIN stays s ON TRY_CAST(x.stay_id AS BIGINT)=s.stay_id
              WHERE x.itemid IN ({','.join(map(q,yes+no))})'''
            self.export('airway_procedures',sql);return
        parts=[]
        rc=self.csv('respiratoryCare')
        if rc and {'airwaytype','respcarestatusoffset'}<=self.cols(rc):
            parts.append(f'''SELECT s.stay_id,TRY_CAST(x.respcarestatusoffset AS DOUBLE)/60 event_hour,
              TRY_CAST(x.respcarestatusoffset AS DOUBLE)/60 available_hour,'Intubated' feature,1.0 AS "value",
              '' unit,'state' kind,CAST(NULL AS DOUBLE) end_hour
              FROM {rc} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
              WHERE regexp_matches(lower(coalesce(x.airwaytype,'')),'ett|trach|tube|crico')''')
        tr=self.csv('treatment')
        if tr and {'treatmentstring','treatmentoffset'}<=self.cols(tr):
            text="lower(coalesce(x.treatmentstring,''))"
            parts.append(f'''SELECT s.stay_id,TRY_CAST(x.treatmentoffset AS DOUBLE)/60 event_hour,
              TRY_CAST(x.treatmentoffset AS DOUBLE)/60 available_hour,'Intubated' feature,
              CASE WHEN regexp_matches({text},{q(EICU_TREATMENT_NO)}) THEN 0.0 ELSE 1.0 END AS "value",
              '' unit,'state' kind,CAST(NULL AS DOUBLE) end_hour
              FROM {tr} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
              WHERE regexp_matches({text},{q(EICU_TREATMENT_YES+'|'+EICU_TREATMENT_NO)})''')
        if parts:self.export('airway',' UNION ALL '.join(parts))

    def admission_weight(self):
        # eICU admission weight from the unit admission record (no offset): known at unit admission.
        if self.ds!='eicu':return
        raw=self.csv('patient',True)
        if 'admissionweight' not in self.cols(raw):return
        self.export('admission_weight',f'''SELECT s.stay_id,0.0 event_hour,0.0 available_hour,'Weight' feature,
          TRY_CAST(x.admissionweight AS DOUBLE) AS "value",'kg' unit,'state' kind,CAST(NULL AS DOUBLE) end_hour
          FROM {raw} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id''')

    def comorbidity(self):
        """Causal chronic-comorbidity flags, each from the hour its documentation is available.
        MIMIC-IV: ICD codes of EARLIER hospital admissions of the same person (discharged before
        this ICU admission: known at hour -1). Codes of the current admission have no timestamp
        and are never used. eICU: past history (entry offset) and diagnosis entries (entry offset)."""
        queries=[]
        if self.ds=='miiv':
            dx=self.csv('hosp/diagnoses_icd');adm=self.csv('hosp/admissions')
            if dx and adm and {'subject_id','hadm_id','dischtime'}<=self.cols(adm):
                queries.append(f'''SELECT s.stay_id,-1.0 available_hour,x.icd_code AS "code",x.icd_version AS "version",NULL AS "text"
                  FROM {dx} x JOIN {adm} a ON x.hadm_id=a.hadm_id JOIN stays s ON CAST(a.subject_id AS VARCHAR)=s.person
                  WHERE TRY_CAST(a.hadm_id AS BIGINT)<>s.hadm_id AND TRY_CAST(a.dischtime AS TIMESTAMP)<=s.intime''')
        else:
            ph=self.csv('pastHistory')
            if ph:
                entry='coalesce(TRY_CAST(x.pasthistoryenteredoffset AS DOUBLE),TRY_CAST(x.pasthistoryoffset AS DOUBLE))' if 'pasthistoryenteredoffset' in self.cols(ph) else 'TRY_CAST(x.pasthistoryoffset AS DOUBLE)'
                queries.append(f'''SELECT s.stay_id,{entry}/60 available_hour,NULL AS "code",NULL AS "version",
                  concat_ws(' ',x.pasthistorypath,x.pasthistoryvaluetext) AS "text"
                  FROM {ph} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id''')
            dg=self.csv('diagnosis')
            if dg:
                queries.append(f'''SELECT s.stay_id,TRY_CAST(x.diagnosisoffset AS DOUBLE)/60 available_hour,{self.col(dg,'icd9code')} AS "code",NULL AS "version",
                  x.diagnosisstring AS "text" FROM {dg} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id''')
        first={}
        for sql in queries:
            for rb in self.con.execute(f'SELECT * FROM ({sql}) z WHERE available_hour<={self.max_hours}').fetch_record_batch(50000):
                for r in rb.to_pandas().itertuples(index=False):
                    if pd.isna(r.available_hour):continue
                    for k in comorbidity_flags(r.code,r.version,r.text):
                        key=(int(r.stay_id),k);first[key]=min(first.get(key,np.inf),max(float(r.available_hour),-168.))
        rows=[{'stay_id':sid,'event_hour':h,'available_hour':h,'feature':'Comorbidity_'+k,'value':1.,'unit':'','kind':'state','end_hour':np.nan}
              for (sid,k),h in first.items()]
        d=pd.DataFrame(rows,columns=['stay_id','event_hour','available_hour','feature','value','unit','kind','end_hour'])
        schema=pa.schema([('stay_id',pa.int64()),('event_hour',pa.float64()),('available_hour',pa.float64()),('feature',pa.string()),
            ('value',pa.float64()),('unit',pa.string()),('kind',pa.string()),('end_hour',pa.float64())])
        pq.write_table(pa.Table.from_pandas(d,schema=schema,preserve_index=False),self.out/'comorbidity.parquet')
        self.files.append(self.out/'comorbidity.parquet')
        if len(d):self.audit.extend([{'dataset':self.ds,'table':'comorbidity','feature':f,'n':int(n)} for f,n in d.feature.value_counts().items()])

    def classify_export(self,name,base,classes,exclude):
        """Export exposure events from `base` (stay_id,event_hour,available_hour,text,value) whose
        text matches a class pattern (one row per matching class) and not the exclusion pattern."""
        self.con.register('classes',pd.DataFrame(list(classes.items()),columns=['feature','pattern']))
        self.export(name,f'''SELECT b.stay_id,b.event_hour,b.available_hour,c.feature,CAST(b.value AS DOUBLE) AS "value",
          '' unit,'exposure' kind,CAST(NULL AS DOUBLE) end_hour FROM ({base}) b
          JOIN classes c ON regexp_matches(lower(coalesce(b."text",'')),c.pattern)
          WHERE NOT regexp_matches(lower(coalesce(b."text",'')),{q(exclude)})''')

    def exposures(self):
        """v10.4: invasive devices, medications, imaging orders, IV fluids and transfusions, each from
        the time it was recorded (MIMIC: storetime-bounded; eICU: entry/order offsets)."""
        dev={'Device_'+k:p for k,p in DEVICE_PATTERNS.items()};med={'Med_'+k:p for k,p in MED_FEATURES.items()}
        if self.ds=='miiv':
            pe=self.csv('icu/procedureevents');di=self.csv('icu/d_items')
            if pe and di:
                eh=self.hour('x.starttime');ah=f'CASE WHEN x.storetime IS NOT NULL THEN greatest({eh},{self.hour("x.storetime")}) END'
                self.classify_export('devices',f'''SELECT s.stay_id,{eh} event_hour,{ah} available_hour,d."label" AS "text",1.0 AS "value"
                  FROM {pe} x JOIN stays s ON TRY_CAST(x.stay_id AS BIGINT)=s.stay_id JOIN {di} d ON x.itemid=d.itemid''',dev,DEVICE_EXCLUDE)
            rx=self.csv('hosp/prescriptions')
            if rx:
                # Prescription start time (orders are entered at or before their start).
                eh=self.hour('x.starttime')
                self.classify_export('medications',f'''SELECT s.stay_id,{eh} event_hour,{eh} available_hour,x.drug AS "text",1.0 AS "value"
                  FROM {rx} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id''',med,MED_EXCLUDE)
            ie=self.csv('icu/inputevents')
            if ie and di:
                eh=self.hour('x.starttime');ah=f'CASE WHEN x.storetime IS NOT NULL THEN greatest({eh},{self.hour("x.storetime")}) END'
                base=f'''FROM {ie} x JOIN stays s ON TRY_CAST(x.stay_id AS BIGINT)=s.stay_id JOIN {di} d ON x.itemid=d.itemid
                  WHERE lower(coalesce(x.statusdescription,''))<>'rewritten' '''
                self.classify_export('infusion_medications',f'''SELECT s.stay_id,{eh} event_hour,{ah} available_hour,d."label" AS "text",1.0 AS "value" {base}''',med,MED_EXCLUDE)
                # A volume is known once the administration ends: event at the end time.
                end=self.hour('x.endtime');aend=f'CASE WHEN x.storetime IS NOT NULL THEN greatest({end},{self.hour("x.storetime")}) END'
                cat="lower(coalesce(x.ordercategoryname,''))"
                self.export('fluids',f'''SELECT s.stay_id,{end} event_hour,{aend} available_hour,
                  CASE WHEN {cat} LIKE '%blood product%' THEN 'Transfusion' ELSE 'FluidIn' END feature,
                  TRY_CAST(x.amount AS DOUBLE) AS "value",'mL' unit,'volume' kind,CAST(NULL AS DOUBLE) end_hour {base}
                  AND regexp_matches({cat},'crystalloid|colloid|fluid bolus|blood product')
                  AND lower(coalesce(x.amountuom,''))='ml' AND TRY_CAST(x.amount AS DOUBLE)>0''')
            poe=self.csv('hosp/poe')
            if poe and 'ordertime' in self.cols(poe):
                eh=self.hour('x.ordertime')
                self.export('imaging',f'''SELECT s.stay_id,{eh} event_hour,{eh} available_hour,'Imaging' feature,1.0 AS "value",
                  '' unit,'exposure' kind,CAST(NULL AS DOUBLE) end_hour FROM {poe} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
                  WHERE lower(coalesce(x.order_type,''))='radiology' ''')
            return
        tr=self.csv('treatment')
        if tr and {'treatmentstring','treatmentoffset'}<=self.cols(tr):
            base=f'''SELECT s.stay_id,TRY_CAST(x.treatmentoffset AS DOUBLE)/60 event_hour,TRY_CAST(x.treatmentoffset AS DOUBLE)/60 available_hour,
              x.treatmentstring AS "text",1.0 AS "value" FROM {tr} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id'''
            self.classify_export('devices',base,dev,DEVICE_EXCLUDE)
            self.classify_export('imaging',base,{'Imaging':IMAGING_RE},'$^')
        md=self.csv('medication')
        if md:
            order=f"TRY_CAST({self.col(md,'drugorderoffset')} AS DOUBLE)/60";start='TRY_CAST(x.drugstartoffset AS DOUBLE)/60'
            self.classify_export('medications',f'''SELECT s.stay_id,{start} event_hour,greatest({start},coalesce({order},{start})) available_hour,
              x.drugname AS "text",1.0 AS "value" FROM {md} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
              WHERE lower(coalesce({self.col(md,'drugordercancelled')},''))<>'yes' ''',med,MED_EXCLUDE)
        inf=self.csv('infusionDrug')
        if inf:
            self.classify_export('infusion_medications',f'''SELECT s.stay_id,TRY_CAST(x.infusionoffset AS DOUBLE)/60 event_hour,
              TRY_CAST(x.infusionoffset AS DOUBLE)/60 available_hour,x.drugname AS "text",1.0 AS "value"
              FROM {inf} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id''',med,MED_EXCLUDE)
        io=self.csv('intakeOutput')
        if io:
            eh='TRY_CAST(x.intakeoutputoffset AS DOUBLE)/60'
            ah=f'CASE WHEN x.intakeoutputentryoffset IS NOT NULL THEN greatest({eh},TRY_CAST(x.intakeoutputentryoffset AS DOUBLE)/60) END'
            text="lower(coalesce(x.cellpath,'')||' '||coalesce(x.celllabel,''))"
            # Charted intake volumes (never the cumulative intaketotal/nettotal columns).
            self.export('fluids',f'''SELECT s.stay_id,{eh} event_hour,{ah} available_hour,
              CASE WHEN regexp_matches({text},{q(TRANSFUSION_RE)}) THEN 'Transfusion' ELSE 'FluidIn' END feature,
              TRY_CAST(x.cellvaluenumeric AS DOUBLE) AS "value",'mL' unit,'volume' kind,CAST(NULL AS DOUBLE) end_hour
              FROM {io} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
              WHERE lower(coalesce(x.cellpath,'')) LIKE '%intake (ml)%' AND NOT regexp_matches({text},{q(FLUID_IN_EXCLUDE+'|total|cumul')})
              AND TRY_CAST(x.cellvaluenumeric AS DOUBLE)>0''')

    def admission_diagnosis(self):
        # eICU admitting diagnosis from its entry offset; MIMIC-IV has no timestamped equivalent.
        if self.ds!='eicu':return
        ad=self.csv('admissionDx')
        if not ad or not {'admitdxpath','admitdxenteredoffset'}<=self.cols(ad):return
        path="lower(coalesce(x.admitdxpath,''))";t='TRY_CAST(x.admitdxenteredoffset AS DOUBLE)/60'
        self.export('admission_diagnosis',f'''SELECT s.stay_id,{t} event_hour,{t} available_hour,f.feature,f.value AS "value",
          '' unit,'state' kind,CAST(NULL AS DOUBLE) end_hour FROM {ad} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id,
          LATERAL (VALUES
            ('AdmitDx_Infection',CASE WHEN {path} LIKE '%|diagnosis|%' THEN CASE WHEN regexp_matches({path},{q(INFECTION_DX_RE)}) THEN 1.0 ELSE 0.0 END END),
            ('AdmitDx_Operative',CASE WHEN {path} LIKE '%|non-operative|%' THEN 0.0 WHEN {path} LIKE '%|operative|%' THEN 1.0
               WHEN {path} LIKE '%o.r.%' AND {path} LIKE '%|yes' THEN 1.0 WHEN {path} LIKE '%o.r.%' AND {path} LIKE '%|no' THEN 0.0 END)) f(feature,value)''')

    def admission_context(self):
        """Known at ICU admission: hours in hospital before the ICU, where the patient came from,
        and the ICU type. MIMIC: transfers (unit before the ICU) and admissions; eICU: patient."""
        m=self.meta;out=pd.DataFrame({'stay_id':m.stay_id})
        def text(series):return series.astype('string').fillna('')
        def has(series,pattern):return text(series).str.lower().str.contains(pattern,regex=True)
        if self.ds=='miiv':
            icu=self.csv('icu/icustays',True);adm=self.csv('hosp/admissions');tf=self.csv('hosp/transfers')
            unit=self.con.execute(f'SELECT CAST(x.stay_id AS BIGINT) stay_id,{self.col(icu,"first_careunit")} AS "unit" FROM {icu} x JOIN stays s ON TRY_CAST(x.stay_id AS BIGINT)=s.stay_id').df()
            out=out.merge(unit,on='stay_id',how='left')
            if adm and {'admittime','admission_location'}<=self.cols(adm):
                a=self.con.execute(f'''SELECT s.stay_id,epoch(s.intime-TRY_CAST(x.admittime AS TIMESTAMP))/3600.0 AS "before",x.admission_location AS "loc"
                  FROM {adm} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id''').df()
                out=out.merge(a,on='stay_id',how='left')
            else:out['before']=np.nan;out['loc']=None
            prev=pd.DataFrame(columns=['stay_id','prev'])
            if tf and {'careunit','intime','hadm_id'}<=self.cols(tf):
                prev=self.con.execute(f'''SELECT stay_id,"prev" FROM (SELECT s.stay_id,x.careunit AS "prev",row_number() OVER (PARTITION BY s.stay_id
                  ORDER BY TRY_CAST(x.intime AS TIMESTAMP) DESC) AS "r" FROM {tf} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
                  WHERE TRY_CAST(x.intime AS TIMESTAMP)<s.intime AND x.careunit IS NOT NULL) WHERE "r"=1''').df()
            out=out.merge(prev,on='stay_id',how='left')
            src=text(out.prev).where(text(out.prev).ne('')&~has(out.prev,'unknown'),text(out['loc']))
            known=src.ne('')
            out['AdmitSource_ED']=has(src,'emergency');out['AdmitSource_OR']=has(src,'pacu|operating|procedure|surgery transfer')
            out['AdmitSource_OtherHospital']=has(src,'transfer from hospital|other hospital')
            out['AdmitSource_Ward']=known&~(out.AdmitSource_ED|out.AdmitSource_OR|out.AdmitSource_OtherHospital|has(src,'intensive|icu|unknown|information not'))
        else:
            raw=self.csv('patient',True)
            p=self.con.execute(f'''SELECT s.stay_id,{self.col(raw,'unittype')} AS "unit",{self.col(raw,'unitadmitsource')} AS "src",
              -TRY_CAST({self.col(raw,'hospitaladmitoffset')} AS DOUBLE)/60 AS "before"
              FROM {raw} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id''').df()
            out=out.merge(p,on='stay_id',how='left');src=out.src;known=text(src)!=''
            out['AdmitSource_ED']=has(src,'emergency|chest pain');out['AdmitSource_OR']=has(src,'operating|recovery|pacu')
            out['AdmitSource_OtherHospital']=has(src,'other hospital');out['AdmitSource_Ward']=has(src,'floor|step-down|sdu|acute care|observation')
        for c in ['AdmitSource_ED','AdmitSource_OR','AdmitSource_OtherHospital','AdmitSource_Ward']:
            out[c]=out[c].astype(float).where(known)
        u=out.unit;ku=text(u)!=''
        out['ICUType_Neuro']=has(u,'neuro');out['ICUType_Cardiac']=has(u,'cardiac|coronary|ccu|cticu|csicu|cvicu')
        out['ICUType_Surgical']=has(u,'surg|sicu')&~has(u,'cardiac')
        out['ICUType_Medical']=has(u,'medical|micu|med-surg')
        for c in ['ICUType_Neuro','ICUType_Cardiac','ICUType_Surgical','ICUType_Medical']:out[c]=out[c].astype(float).where(ku)
        out['HospitalHoursBeforeICU']=out.before.clip(lower=0)
        keep=['stay_id','HospitalHoursBeforeICU']+[c for c in ADMISSION if c.startswith(('AdmitSource_','ICUType_'))]
        self.meta=self.meta.drop(columns=[c for c in keep if c!='stay_id' and c in self.meta]).merge(out[keep],on='stay_id',how='left',validate='one_to_one')

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
    for name,factor,units in [('Calcium',4.,['mmol/l']),('CalciumIonized',.25,['mg/dl']),('Magnesium',1/1.215,['meq/l']),('CRP',10.,['mg/dl']),
                              ('Weight',.45359237,['lbs','lb']),('TroponinT',.001,['ng/l']),('TroponinI',.001,['ng/l'])]:
        d.loc[f.eq(name)&u.isin(units),'value']*=factor
    # Reject known incompatible units instead of accepting by numeric appearance.
    allowed={
      'Albumin':{'g/dl'},'Bilirubin_total':{'mg/dl'},'Bilirubin_direct':{'mg/dl'},'Creatinine':{'mg/dl'},
      'BUN':{'mg/dl'},'Glucose':{'mg/dl'},'Lactate':{'mmol/l'},'Magnesium':{'mg/dl','meq/l'},'Hct':{'%'},
      'TroponinT':{'ng/ml','ng/l'},'TroponinI':{'ng/ml','ng/l'},'EtCO2':{'mmhg'},'SaO2':{'%'},
      'Calcium':{'mg/dl','mmol/l'},'CalciumIonized':{'mmol/l','mg/dl'},'CRP':{'mg/l','mg/dl'},'Phosphate':{'mg/dl'},'Weight':{'kg','lbs','lb'},
      'UrineOutput':{'ml'},'FiO2':{'%','fraction',''},'Temp':{'c','°c','degc','f','°f','degf'}}
    for name,units in allowed.items():
        bad=f.eq(name)&~u.isin(units|{''});d.loc[bad,'value']=np.nan
    for name,s in SPEC.items():
        if name=='UrineOutput':continue
        ix=f.eq(name);lo=s.get('min');hi=s.get('max')
        if isinstance(lo,(float,int)):d.loc[ix&d.value.lt(lo),'value']=np.nan
        if isinstance(hi,(float,int)):d.loc[ix&d.value.gt(hi),'value']=np.nan
    bounds={'Weight':(20,500),'GCS':(3,15),'GCS_Eyes':(1,4),'GCS_Verbal':(1,5),'GCS_Motor':(1,6),'Intubated':(0,1)}
    ett=f.eq('GCS_Verbal')&d.value.eq(VERBAL_ETT)  # reset marker, not a score
    for name,(lo,hi) in bounds.items():d.loc[f.eq(name)&~d.value.between(lo,hi)&~ett,'value']=np.nan
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

    Weight-normalised rate (v10.3, relaxed from 6/6 hourly records): each urine record
    documents the output since the previous record known by t (gaps over 12 h, and the first
    record, have no known interval). The documented volume falling in (t-6,t] is divided by
    the hours it covers and by weight, when at least 4 of the 6 hours are covered. The covered
    fraction and the hours since the last record are separate features.
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
        known=(a<=t)&(e<=t);pos=known&(v>=0)
        if not pos.any():continue
        times,inv=np.unique(e[pos],return_inverse=True);out['Urine_HoursSinceLast'][i]=t-times[-1]
        vol=np.bincount(inv,weights=v[pos]);start=t-6.
        prev,cur=times[:-1],times[1:]
        use=(cur>start)&(cur-prev<=URINE_MAX_INTERVAL);span=cur-np.maximum(prev,start)
        covered=float(span[use].sum());volume=float((vol[1:]*span/np.where(use,cur-prev,1.))[use].sum())
        irrigant=v[known&(v<0)&(e>start)].sum()
        out['UrineCoverageFraction_6h'][i]=min(covered/6.,1.)
        net=volume+irrigant
        if covered>=URINE_MIN_COVERED_HOURS and net>=0 and np.isfinite(weight[i]) and weight[i]>0:
            out['Urine_mlkg_h_6h'][i]=net/(covered*weight[i])
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

def first_known(events,hours):
    """Per cutoff: event time of the earliest record already available by then (NaN if none)."""
    out=np.full(len(hours),np.nan)
    if events.empty:return out
    z=events.sort_values('available_hour');a=z.available_hour.to_numpy(float)
    first=np.minimum.accumulate(z.event_hour.to_numpy(float))
    idx=np.searchsorted(a,hours,side='right')-1;ok=idx>=0;out[ok]=first[idx[ok]];return out

def window_total(events,hours,window,count=False):
    """Sum (or count) of records available by each cutoff with event time in (t-window, t]; 0 if none."""
    e=events.event_hour.to_numpy(float);a=events.available_hour.to_numpy(float);v=events.value.to_numpy(float)
    out=np.zeros(len(hours))
    for i,t in enumerate(hours):
        m=(a<=t)&(e>t-window)&(e<=t)
        if m.any():out[i]=m.sum() if count else v[m].sum()
    return out

def build_sequence(events,meta,max_hours=120,horizon=6):
    end=min(max_hours,int(np.floor(meta['followup_end'])))
    hours=np.arange(1,end+1,dtype=float)
    d=pd.DataFrame({'Hour':hours});ages={}
    by={f:g for f,g in events.groupby('feature',sort=False)} if len(events) else {}
    def ev(f):return by.get(f,events.iloc[:0])
    for feat in BASE+SUPPORT+['GCS_Eyes','GCS_Verbal','GCS_Motor','Intubated']:
        if feat in ['Age','Gender','PostoperativeAdmission']:continue
        z=ev(feat)
        if feat in SUPPORT:
            d[feat],ages[feat]=support_features(z,hours);continue
        if feat=='Intubated' and len(z):
            # Several devices can be charted at one time: any invasive airway at that time counts.
            z=z.groupby('event_hour',as_index=False).agg(value=('value','max'),available_hour=('available_hour','max'))
        # v10.3: vitals and labs carried 24 h; GCS (and components) until the next measurement;
        # weight never expires (charted once; otherwise weight-normalised urine vanished after day 1).
        ttl=float(max_hours+168) if feat in NO_EXPIRY else 24.
        d[feat],ages[feat]=latest_known(z,hours,ttl)
    # Intubated verbal scores are not imputed: an ETT entry resets the verbal component to unknown.
    ett=d.GCS_Verbal.eq(VERBAL_ETT).to_numpy()
    d.loc[ett,'GCS_Verbal']=np.nan;ages['GCS_Verbal']=np.where(ett,np.nan,ages['GCS_Verbal'])
    # Total GCS: the charted total or the sum of three known components, whichever is more recent.
    components=d[['GCS_Eyes','GCS_Verbal','GCS_Motor']]
    complete=components.notna().all(axis=1).to_numpy()
    ca=np.stack([ages[k] for k in ['GCS_Eyes','GCS_Verbal','GCS_Motor']])
    component_age=np.max(np.where(np.isfinite(ca),ca,-np.inf),axis=0);component_age[~np.isfinite(component_age)]=np.nan
    use=complete&(d.GCS.isna().to_numpy()|(component_age<np.nan_to_num(ages['GCS'],nan=np.inf)))
    d.loc[use,'GCS']=components.sum(axis=1)[use];ages['GCS']=np.where(use,component_age,ages['GCS'])
    # GCS < 15 is decidable from partial components (eyes < 4, verbal < 5 or motor < 6) without
    # imputing the missing ones; a normal result needs a known total of 15.
    partial=(d.GCS_Eyes<4)|(d.GCS_Verbal<5)|(d.GCS_Motor<6)
    d['GCS_Below15']=np.where(d.GCS.notna(),(d.GCS<15).astype(float),np.where(partial,1.,np.nan))
    d=d.drop(columns=['GCS_Eyes','GCS_Verbal','GCS_Motor'])
    # Cumulative documented airway hours (unknown hours are not counted); unknown before any airway record.
    tube=d.Intubated.to_numpy()
    d['IntubatedHours']=np.where(np.cumsum(np.isfinite(tube))>0,np.cumsum(tube==1).astype(float),np.nan)
    for feat in COMORBID:
        # 1 from the hour its documentation is available, else 0 (not documented).
        known=ev(feat).available_hour
        d[feat]=(hours>=known.min()).astype(float) if len(known) else 0.
    d['Age']=meta.get('Age',np.nan);d['Gender']=meta.get('Gender',np.nan);d=d.copy()
    for feat,v in urine_features(ev('UrineOutput'),hours,d.Weight.to_numpy()).items():d[feat]=v
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
    new={};fio2=d.FiO2.where(d.FiO2>=21)/100
    new['PF_Ratio']=d.PaO2/fio2;new['SF_Ratio']=d.O2Sat/fio2
    # Admission context known at ICU admission; eICU admitting diagnosis from its entry time.
    for f in ADMISSION:
        if f.startswith('AdmitDx_'):
            z=ev(f)
            if len(z):z=z.groupby('event_hour',as_index=False).agg(value=('value','max'),available_hour=('available_hour','max'))
            new[f],_=latest_known(z,hours,float(max_hours+168))
        else:
            v=meta.get(f,np.nan);new[f]=np.repeat(float(v) if v is not None and pd.notna(v) else np.nan,len(hours))
    # Documented exposures, each from the hour its record is available (0 = not documented).
    for dev in DEVICES:
        first=first_known(ev(dev),hours)
        new[dev]=np.isfinite(first).astype(float);new[dev+'_Hours']=hours-first
    for k in MED_FEATURES:new['Med_'+k+'_24h']=(window_total(ev('Med_'+k),hours,24,True)>0).astype(float)
    new['Imaging_24h']=window_total(ev('Imaging'),hours,24,True)
    new['FluidIn_6h']=window_total(ev('FluidIn'),hours,6);new['FluidIn_24h']=window_total(ev('FluidIn'),hours,24)
    new['Transfusion_24h']=window_total(ev('Transfusion'),hours,24)
    d=pd.concat([d,pd.DataFrame(new,index=d.index)],axis=1)
    extras={feat+'_age':age for feat,age in ages.items() if feat in BASE+SUPPORT+['Intubated']}
    # Explicit masks survive imputation and reach every model and observer.
    extras.update({feat+'_observed':d[feat].notna().astype(float) for feat in PRIMARY})
    d=pd.concat([d,pd.DataFrame(extras,index=d.index)],axis=1)
    onset=meta['OnsetHour'];follow=meta['followup_end']
    at_risk=np.ones(len(d),bool) if pd.isna(onset) else hours<onset
    known_future=(hours+horizon<=follow) if pd.isna(onset) else ((hours+horizon<=follow)|(hours+horizon>=onset))
    d['Eligible']=(at_risk&known_future).astype(int)
    d['SepsisLabel']=((onset>hours)&(onset<=hours+horizon)).astype(int) if pd.notna(onset) else 0
    # Post-onset hours stay in the sequence (Eligible=0, so they never enter a loss or an incident-risk
    # metric); the PhysioNet utility score needs predictions up to 3 h after onset. Features are causal
    # (prefix checks), so pre-onset rows are unchanged by the extra rows.
    return engineer_one(d.reset_index(drop=True))

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
            for f in COMORBID+EXPOSURES:  # flagged/nonzero hours (never missing; 0 means not documented)
                a,b=batch_counts.get(f,(0,0));batch_counts[f]=(a+int(seq[f].gt(0).sum()),b+len(seq))
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
