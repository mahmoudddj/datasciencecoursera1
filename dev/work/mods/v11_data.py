"""V11 data additions that leave the main raw stage (and its key) untouched.

1. SupplementExtractor: prophylactic-antibiotic events (MIMIC-IV) and antibiotic start times
   (both databases, evaluation metadata only), written to a separate supplementary stage.
2. unlabelled_stays: the self-supervised corpus (stays never labelled by YAIB, protected-hash
   patients excluded) with age/sex from the raw tables; no R label extraction is needed.

Antibiotic rule (user decision, 19 Oct 2026; ASHP/IDSA/SIS/SHEA 2013, CDC 2017, Seymour 2016):
- SURGICAL prophylaxis = prophylaxis agent AND first dose within the perioperative window of a
  surgical timestamp (PACU/OR transfer or ICU admission from the OR) AND the order lasts <= 24 h
  (48 h for cardiac surgery) AND no culture in the Seymour window [-72 h, +24 h] around the dose
  AND no other antibiotic started within 72 h after it.
- MEDICAL prophylaxis = agent/dose pattern typical of PJP, SBP, neutropenia or transplant
  prophylaxis AND no culture in the Seymour window.
- Everything else (empirical, culture-directed) is excluded: it defines the Sepsis-3 label.
- eICU: no prophylaxis features (its label is antibiotic-only).
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import duckdb
import os
from v9_data import RawExtractor,MED_CONTEXT,q,table,csv_scan

def atomic_json_path(path,data):
    path=Path(path);tmp=path.with_suffix('.partial.json');tmp.write_text(json.dumps(data,indent=2,default=str));os.replace(tmp,path)

SURGICAL_AGENTS=r'cefazolin|ancef|cefuroxime|cefoxitin|cefotetan|ampicillin-sulbactam|unasyn|clindamycin|vancomycin|gentamicin|metronidazole|ertapenem|neomycin|erythromycin'
MEDICAL_AGENTS={
 'pjp':r'sulfamethoxazole|trimethoprim|bactrim|dapsone|atovaquone|pentamidine',
 'antifungal':r'fluconazole|posaconazole|micafungin|caspofungin',
 'antiviral':r'acyclovir|valacyclovir|valganciclovir|ganciclovir',
 'sbp_neutropenia':r'norfloxacin|ciprofloxacin|levofloxacin|penicillin v'}
TOPICAL=r'cream|ointment|topical|ophth|otic|eye drop|lotion|enema|suppository|nasal|vaginal|irrig|flush|lock'
CARDIAC_SERVICE=r'csurg|cardiac surg|cardiothoracic|vsurg'
SURGICAL_UNIT=r'pacu|operating|recovery|procedure'

class SupplementExtractor(RawExtractor):
    """Subclass so RawExtractor's source (and therefore RAW_STAGE_KEY) is unchanged."""
    def supplement(self):
        self.antibiotic_starts()
        if self.ds=='miiv':self.prophylaxis()
        self.con.close()
        atomic_json_path(self.out/'supplement_complete.json',{'stays':int(len(self.meta)),'dataset':self.ds})

    def _antibiotics(self):
        """Systemic antibiotic order starts (hour, agent, stop hour, doses/day, route) per stay."""
        if self.ds=='miiv':
            rx=self.csv('hosp/prescriptions')
            if not rx:return None
            eh=self.hour('x.starttime');stop=self.hour('x.stoptime') if 'stoptime' in self.cols(rx) else 'NULL'
            dpd=f"TRY_CAST({self.col(rx,'doses_per_24_hrs')} AS DOUBLE)";dose=f"TRY_CAST({self.col(rx,'dose_val_rx')} AS DOUBLE)"
            route=f"lower(coalesce(CAST({self.col(rx,'route')} AS VARCHAR),''))"
            return self.con.execute(f'''SELECT s.stay_id,{eh} AS "event_hour",{stop} AS "stop_hour",lower(coalesce(x.drug,'')) AS "drug",
              {dpd} AS "doses_per_day",{dose} AS "dose",{route} AS "route"
              FROM {rx} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
              WHERE regexp_matches(lower(coalesce(x.drug,'')),{q(MED_CONTEXT['antimicrobial']+'|'+SURGICAL_AGENTS+'|'+'|'.join(MEDICAL_AGENTS.values()))})
              AND NOT regexp_matches(lower(coalesce(x.drug,''))||' '||{route},{q(TOPICAL)})''').df()
        parts=[]
        md=self.csv('medication')
        if md:
            start='TRY_CAST(x.drugstartoffset AS DOUBLE)/60';stop=f"TRY_CAST({self.col(md,'drugstopoffset')} AS DOUBLE)/60"
            parts.append(self.con.execute(f'''SELECT s.stay_id,{start} AS "event_hour",{stop} AS "stop_hour",lower(coalesce(x.drugname,'')) AS "drug",
              NULL AS "doses_per_day",NULL AS "dose",lower(coalesce(CAST({self.col(md,'routeadmin')} AS VARCHAR),'')) AS "route"
              FROM {md} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
              WHERE lower(coalesce({self.col(md,'drugordercancelled')},''))<>'yes'
              AND regexp_matches(lower(coalesce(x.drugname,'')),{q(MED_CONTEXT['antimicrobial'])})
              AND NOT regexp_matches(lower(coalesce(x.drugname,'')),{q(TOPICAL)})''').df())
        inf=self.csv('infusionDrug')
        if inf:
            parts.append(self.con.execute(f'''SELECT s.stay_id,TRY_CAST(x.infusionoffset AS DOUBLE)/60 AS "event_hour",NULL AS "stop_hour",
              lower(coalesce(x.drugname,'')) AS "drug",NULL AS "doses_per_day",NULL AS "dose",'iv' AS "route"
              FROM {inf} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id
              WHERE regexp_matches(lower(coalesce(x.drugname,'')),{q(MED_CONTEXT['antimicrobial'])})''').df())
        return pd.concat(parts,ignore_index=True) if parts else None

    def antibiotic_starts(self):
        a=self._antibiotics()
        if a is None:a=pd.DataFrame(columns=['stay_id','event_hour'])
        a=a[np.isfinite(a.event_hour.astype(float))&(a.event_hour.astype(float)>=-24)&(a.event_hour.astype(float)<=self.max_hours+24)]
        a[['stay_id','event_hour']].astype({'stay_id':'int64','event_hour':'float64'}).to_parquet(self.out/'antibiotic_starts.parquet',index=False)
        self._abx=a

    def _cultures(self):
        mb=self.csv('hosp/microbiologyevents')
        if not mb:return pd.DataFrame(columns=['stay_id','hour'])
        return self.con.execute(f'''SELECT s.stay_id,{self.hour('x.charttime')} AS "hour" FROM {mb} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
          WHERE x.charttime IS NOT NULL''').df()

    def _surgical_times(self):
        """Hours (relative to ICU intime) of surgical timestamps: PACU/OR/recovery transfers, surgical
        service transfers, and the ICU admission itself when the patient came from the OR/PACU."""
        rows=[]
        tf=self.csv('hosp/transfers')
        if tf and {'careunit','intime','hadm_id'}<=self.cols(tf):
            rows.append(self.con.execute(f'''SELECT s.stay_id,{self.hour('x.intime')} AS "hour",'transfer' AS "kind"
              FROM {tf} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
              WHERE regexp_matches(lower(coalesce(x.careunit,'')),{q(SURGICAL_UNIT)})''').df())
        sv=self.csv('hosp/services')
        if sv and {'curr_service','transfertime','hadm_id'}<=self.cols(sv):
            rows.append(self.con.execute(f'''SELECT s.stay_id,{self.hour('x.transfertime')} AS "hour",'service' AS "kind"
              FROM {sv} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
              WHERE regexp_matches(lower(coalesce(x.curr_service,'')),'surg|ortho|\\bgu\\b|gyn|\\bent\\b|neuro|trauma|cardiac')''').df())
        adm=self.csv('hosp/admissions')
        if adm and 'admission_type' in self.cols(adm):
            rows.append(self.con.execute(f'''SELECT s.stay_id,0.0 AS "hour",'surgical_admission' AS "kind"
              FROM {adm} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
              WHERE lower(coalesce(x.admission_type,'')) LIKE '%surgical%' ''').df())
        t=pd.concat(rows,ignore_index=True) if rows else pd.DataFrame(columns=['stay_id','hour','kind'])
        return t[np.isfinite(t.hour.astype(float))]

    def _cardiac(self):
        sv=self.csv('hosp/services')
        if not sv or 'curr_service' not in self.cols(sv):return set()
        d=self.con.execute(f'''SELECT DISTINCT s.stay_id FROM {sv} x JOIN stays s ON TRY_CAST(x.hadm_id AS BIGINT)=s.hadm_id
          WHERE regexp_matches(lower(coalesce(x.curr_service,'')),{q(CARDIAC_SERVICE)})''').df()
        return set(d.stay_id.astype(int))

    def prophylaxis(self):
        a=getattr(self,'_abx',None)
        if a is None or a.empty:
            pd.DataFrame(columns=['stay_id','event_hour','available_hour','feature','value','unit','kind','end_hour']).to_parquet(self.out/'prophylaxis.parquet',index=False);return
        a=a.copy();a['event_hour']=a.event_hour.astype(float);a['stop_hour']=pd.to_numeric(a.stop_hour,errors='coerce')
        cultures=self._cultures();surg=self._surgical_times();cardiac=self._cardiac()
        cult={sid:g.hour.to_numpy(float) for sid,g in cultures.groupby('stay_id')}
        st={sid:g.hour.to_numpy(float) for sid,g in surg.groupby('stay_id')}
        starts={sid:g.event_hour.to_numpy(float) for sid,g in a.groupby('stay_id')}
        drugs={sid:g.drug.to_numpy() for sid,g in a.groupby('stay_id')}
        out=[]
        for r in a.itertuples(index=False):
            sid=int(r.stay_id);h=float(r.event_hour)
            # Seymour pairing: a culture in [-72 h, +24 h] around the dose makes it label-relevant -> never prophylaxis.
            c=cult.get(sid,np.empty(0))
            if ((c>=h-72)&(c<=h+24)).any():continue
            duration=(r.stop_hour-h) if np.isfinite(r.stop_hour) else np.nan
            others=starts.get(sid,np.empty(0));od=drugs.get(sid,np.empty(0))
            # Escalation = a NON-prophylaxis agent started within 72 h after this dose (a combination
            # prophylaxis partner or a chronic prophylaxis agent is not an escalation).
            proph=pd.Series(od).str.contains(SURGICAL_AGENTS+'|'+'|'.join(MEDICAL_AGENTS.values()),regex=True).to_numpy() if len(od) else np.zeros(0,bool)
            escalation=bool(((others>h)&(others<=h+72)&~proph).any())
            surgical=False
            if pd.Series([r.drug]).str.contains(SURGICAL_AGENTS,regex=True).iloc[0]:
                t=st.get(sid,np.empty(0))
                peri=((t>=h-1)&(t<=h+8)).any()  # dose 0-8 h before the end-of-surgery/transfer timestamp, or within 1 h after
                limit=48. if sid in cardiac else 24.
                short=(np.isfinite(duration) and duration<=limit) or (r.doses_per_day is not None and np.isfinite(r.doses_per_day) and r.doses_per_day<=1 and not np.isfinite(duration))
                surgical=bool(peri and short and not escalation)
            medical=False
            if not surgical:
                drug=str(r.drug);dpd=float(r.doses_per_day) if r.doses_per_day is not None and np.isfinite(r.doses_per_day) else np.nan;dose=float(r.dose) if r.dose is not None and np.isfinite(r.dose) else np.nan
                if pd.Series([drug]).str.contains(MEDICAL_AGENTS['pjp'],regex=True).iloc[0]:
                    medical=('pentamidine' in drug or 'dapsone' in drug or 'atovaquone' in drug or (np.isfinite(dpd) and dpd<=1))
                elif pd.Series([drug]).str.contains(MEDICAL_AGENTS['antifungal'],regex=True).iloc[0]:
                    medical=('fluconazole' not in drug) or (np.isfinite(dpd) and dpd<=1 and (not np.isfinite(dose) or dose<=400))
                elif pd.Series([drug]).str.contains(MEDICAL_AGENTS['antiviral'],regex=True).iloc[0]:
                    medical=np.isfinite(dpd) and dpd<=2
                elif pd.Series([drug]).str.contains(MEDICAL_AGENTS['sbp_neutropenia'],regex=True).iloc[0]:
                    medical=np.isfinite(dpd) and dpd<=1
                medical=bool(medical and not escalation)
            if surgical:out.append((sid,h,h,'Prophylaxis_Surgical',1.,'','exposure',np.nan))
            if medical:out.append((sid,h,h,'Prophylaxis_Medical',1.,'','exposure',np.nan))
        d=pd.DataFrame(out,columns=['stay_id','event_hour','available_hour','feature','value','unit','kind','end_hour'])
        d=d.astype({'stay_id':'int64','event_hour':'float64','available_hour':'float64','value':'float64','end_hour':'float64'})
        d.to_parquet(self.out/'prophylaxis.parquet',index=False)
        pd.DataFrame({'feature':['Prophylaxis_Surgical','Prophylaxis_Medical'],
            'n':[int(d.feature.eq('Prophylaxis_Surgical').sum()),int(d.feature.eq('Prophylaxis_Medical').sum())],
            'antibiotic_orders_considered':len(a)}).to_csv(self.out/'prophylaxis_counts.csv',index=False)

def unlabelled_stays(ds,root,exclude_stay_ids,protected,max_stays=None,seed=42,max_hours=120,min_hours=6):
    """Stays for self-supervised pretraining: every ICU stay in the raw release that is NOT in the labelled
    cohort and whose patient is NOT in the protected final holdout. Returns (selected, static): `selected`
    has the columns build_shards/RawExtractor expect (OnsetHour NaN; followup_end = stay length capped);
    `static` has Age and Gender from the raw tables. No labels of any kind are read."""
    con=duckdb.connect();con.execute("SET memory_limit='2GB'");con.execute('SET threads=2')
    try:
        if ds=='miiv':
            icu=csv_scan(table(root,'icu/icustays',True),True);pat=csv_scan(table(root,'hosp/patients',True),True)
            d=con.execute(f'''SELECT CAST(x.stay_id AS BIGINT) AS "stay_id",CAST(x.subject_id AS VARCHAR) AS "person",
              epoch(TRY_CAST(x.outtime AS TIMESTAMP)-TRY_CAST(x.intime AS TIMESTAMP))/3600.0 AS "los",
              TRY_CAST(p.anchor_age AS DOUBLE) AS "Age",lower(coalesce(p.gender,'')) AS "sex"
              FROM {icu} x LEFT JOIN {pat} p ON x.subject_id=p.subject_id''').df()
        else:
            pt=csv_scan(table(root,'patient',True),True)
            d=con.execute(f'''SELECT CAST(x.patientunitstayid AS BIGINT) AS "stay_id",CAST(x.uniquepid AS VARCHAR) AS "person",
              TRY_CAST(x.unitdischargeoffset AS DOUBLE)/60 AS "los",
              CASE WHEN lower(CAST(x.age AS VARCHAR)) LIKE '%>%' THEN 90.0 ELSE TRY_CAST(x.age AS DOUBLE) END AS "Age",
              lower(coalesce(x.gender,'')) AS "sex" FROM {pt} x''').df()
    finally:con.close()
    d=d[~d.stay_id.isin(set(int(i) for i in exclude_stay_ids))&d.person.notna()&(d.los>=min_hours)]
    d=d[~d.person.map(lambda p:protected(ds+'|'+str(p)))]
    if max_stays is not None and len(d)>max_stays:d=d.sample(max_stays,random_state=seed)
    d=d.sort_values('stay_id').reset_index(drop=True)
    d['Gender']=d.sex.map({'male':1.,'m':1.,'female':0.,'f':0.}).astype(float)
    selected=pd.DataFrame({'stay_id':d.stay_id.astype('int64'),'first_hour':0.,'followup_end':np.minimum(d.los,float(max_hours)),
        'first_positive':np.nan,'OnsetHour':np.nan,'Outcome':0})
    static=d[['stay_id','Age','Gender']].copy()
    return selected,static
