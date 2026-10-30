"""Stage-2 supplementary raw stage (protocol 10c.2 items 9, 10, 17): antibiotic COURSES (start, stop, agent, route),
culture times, hospital outcomes and the MIMIC-IV anchor-year group, for every selected stay, written to its own folder
with its own completion marker so that the main raw stage, the v11 supplement and their keys are untouched.
Reuses SupplementExtractor._antibiotics (same agent patterns, same topical exclusions)."""
from pathlib import Path
import numpy as np
import pandas as pd
from v9_data import q,table,csv_scan
from v11_data import SupplementExtractor,atomic_json_path

SEPSIS_ICD=r'^(A4[01]|R652|038|99591|99592|78552)'

class CourseExtractor(SupplementExtractor):
    def courses(self):
        a=self._antibiotics()
        if a is None or len(a)==0:a=pd.DataFrame(columns=['stay_id','event_hour','stop_hour','drug','route'])
        a=a.copy();a['start']=pd.to_numeric(a.event_hour,errors='coerce');a['stop']=pd.to_numeric(a.get('stop_hour'),errors='coerce')
        a=a[np.isfinite(a.start)&(a.start>=-168)&(a.start<=self.max_hours+24)]
        out=a[['stay_id','start','stop','drug','route']].astype({'stay_id':'int64','start':'float64','stop':'float64'}).sort_values(['stay_id','start'])
        out.to_parquet(self.out/'courses.parquet',index=False);return out
    def cultures(self):
        if self.ds=='miiv':
            c=self._cultures();c=c.rename(columns={'hour':'culture_hour'})
        else:
            ml=self.csv('microLab')
            if ml and 'culturetakenoffset' in self.cols(ml):
                c=self.con.execute(f'''SELECT s.stay_id,TRY_CAST(x.culturetakenoffset AS DOUBLE)/60 AS "culture_hour" FROM {ml} x JOIN stays s ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id''').df()
            else:c=pd.DataFrame(columns=['stay_id','culture_hour'])
        c=c[np.isfinite(pd.to_numeric(c.culture_hour,errors='coerce'))].astype({'stay_id':'int64','culture_hour':'float64'})
        c.to_parquet(self.out/'cultures.parquet',index=False);return c
    def outcomes(self):
        if self.ds=='miiv':
            icu=self.csv('icu/icustays',True);adm=self.csv('hosp/admissions',True);pat=self.csv('hosp/patients')
            # Column lookups tolerate schema differences (self.col returns NULL for a missing column).
            d=self.con.execute(f'''SELECT s.stay_id,TRY_CAST({self.col(adm,'hospital_expire_flag','a')} AS DOUBLE) AS "hospital_death",
                 epoch(TRY_CAST({self.col(adm,'deathtime','a')} AS TIMESTAMP)-s.intime)/3600.0 AS "death_hour",
                 epoch(TRY_CAST({self.col(icu,'outtime','x')} AS TIMESTAMP)-s.intime)/3600.0 AS "icu_los_h",
                 epoch(TRY_CAST({self.col(adm,'dischtime','a')} AS TIMESTAMP)-s.intime)/3600.0 AS "hospital_los_h"
                 FROM stays s JOIN {icu} x ON TRY_CAST(x.stay_id AS BIGINT)=s.stay_id LEFT JOIN {adm} a ON TRY_CAST(a.hadm_id AS BIGINT)=s.hadm_id''').df()
            d['icu_death']=(d.death_hour.notna()&(d.death_hour<=d.icu_los_h+1)).astype(float);d['admitted_for_sepsis_dx']=np.nan
            if pat and 'anchor_year_group' in self.cols(pat):
                y=self.con.execute(f'''SELECT s.stay_id,CAST(p.anchor_year_group AS VARCHAR) AS "anchor_year_group" FROM stays s JOIN {pat} p ON CAST(p.subject_id AS VARCHAR)=s.person''').df()
                d=d.merge(y,on='stay_id',how='left')
            else:d['anchor_year_group']=None
            dx=self.csv('hosp/diagnoses_icd')
            if dx:
                z=self.con.execute(f'''SELECT DISTINCT s.stay_id FROM stays s JOIN {dx} g ON TRY_CAST(g.hadm_id AS BIGINT)=s.hadm_id
                     WHERE regexp_matches(upper(replace(coalesce(g.icd_code,''),'.','')),{q(SEPSIS_ICD)})''').df()
                d['sepsis_documented']=d.stay_id.isin(set(z.stay_id)).astype(float)
            else:d['sepsis_documented']=np.nan
        else:
            pt=self.csv('patient',True)
            d=self.con.execute(f'''SELECT s.stay_id,
                 CASE lower(coalesce(CAST({self.col(pt,'hospitaldischargestatus')} AS VARCHAR),'')) WHEN 'expired' THEN 1.0 WHEN 'alive' THEN 0.0 END AS "hospital_death",
                 CASE lower(coalesce(CAST({self.col(pt,'unitdischargestatus')} AS VARCHAR),'')) WHEN 'expired' THEN 1.0 WHEN 'alive' THEN 0.0 END AS "icu_death",
                 TRY_CAST({self.col(pt,'unitdischargeoffset')} AS DOUBLE)/60 AS "icu_los_h",TRY_CAST({self.col(pt,'hospitaldischargeoffset')} AS DOUBLE)/60 AS "hospital_los_h",
                 CASE WHEN lower(coalesce(CAST({self.col(pt,'apacheadmissiondx')} AS VARCHAR),'')) LIKE '%sepsis%' THEN 1.0 ELSE 0.0 END AS "admitted_for_sepsis_dx",
                 CAST({self.col(pt,'hospitalid')} AS VARCHAR) AS "hospital"
                 FROM stays s JOIN {pt} x ON TRY_CAST(x.patientunitstayid AS BIGINT)=s.stay_id''').df()
            d['death_hour']=np.where(d.icu_death.eq(1),d.icu_los_h,np.where(d.hospital_death.eq(1),d.hospital_los_h,np.nan));d['anchor_year_group']=None
            dg=self.csv('diagnosis')
            if dg:
                z=self.con.execute(f'''SELECT DISTINCT s.stay_id FROM stays s JOIN {dg} g ON TRY_CAST(g.patientunitstayid AS BIGINT)=s.stay_id
                     WHERE lower(coalesce(g.diagnosisstring,'')) LIKE '%sepsis%' OR lower(coalesce(g.diagnosisstring,'')) LIKE '%septic%' ''').df()
                d['sepsis_documented']=d.stay_id.isin(set(z.stay_id)).astype(float)
            else:d['sepsis_documented']=np.nan
        d=d.astype({'stay_id':'int64'});d.to_parquet(self.out/'outcomes.parquet',index=False);return d
    def supplement2(self):
        c=self.courses();k=self.cultures();o=self.outcomes();self.con.close()
        atomic_json_path(self.out/'supplement2_complete.json',{'stays':int(len(self.meta)),'dataset':self.ds,'courses':int(len(c)),'cultures':int(len(k)),'outcomes':int(len(o))})

def first_treatment_hours(courses,cultures):
    """Per stay: the first antibiotic start, the first culture, and the earlier of the two (the first treatment indicator)."""
    a=courses.groupby('stay_id').start.min().rename('first_antibiotic_hour') if len(courses) else pd.Series(dtype=float,name='first_antibiotic_hour')
    c=cultures.groupby('stay_id').culture_hour.min().rename('first_culture_hour') if len(cultures) else pd.Series(dtype=float,name='first_culture_hour')
    d=pd.concat([a,c],axis=1);d['first_treatment_hour']=d.min(axis=1);return d.reset_index().rename(columns={'index':'stay_id'})
