"""Nonclinical engineering fixtures only; never used for study training/results."""
from pathlib import Path
import tempfile,json,contextlib,io
import numpy as np
import pandas as pd
import torch
import duckdb
from v9_data import aki_stage,latest_known,urine_features,text_flags,specimen_site,RawExtractor,normalize_events,build_sequence,PRIMARY,csv_scan,comorbidity_flags
from v9_models import organ_mapping,ObserverBank,ExperimentModel,perturb_guidance

def run_selftests():
    torch.set_num_threads(min(torch.get_num_threads(),2));checks={}
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks[name]='pass'
    e=pd.DataFrame({'event_hour':[1.,2.,3.],'available_hour':[1.,6.,3.],'value':[10.,100.,20.]})
    v,a=latest_known(e,np.arange(1.,8.),24)
    check('late_entry_not_backdated',v[1]==10 and v[2]==20)
    check('late_old_value_not_overwrite_newer',v[5]==20)
    measured=pd.DataFrame({'event_hour':[0.,2.],'available_hour':[0.,2.],'value':[80.,85.]})
    _,a=latest_known(measured,np.arange(5.));check('time_since_last_measurement',np.array_equal(a,[0,1,0,1,2]))
    urine=pd.DataFrame({'event_hour':np.arange(1.,7.),'available_hour':np.arange(1.,7.),'value':[50.]*6})
    u=urine_features(urine,np.arange(1.,7.),np.repeat(70.,6))
    check('urine_raw_reaches_rolling_volume',u['UrineOutput_6h'][-1]==300)
    # v10.3 relaxed rule: volume over the hours it documents (first record has no known interval), >= 4 of 6 hours.
    check('urine_rate_needs_4_documented_hours',np.isnan(u['Urine_mlkg_h_6h'][3]) and np.isclose(u['Urine_mlkg_h_6h'][4],200/(4*70)))
    check('urine_coverage_fraction_and_recency',np.isclose(u['UrineCoverageFraction_6h'][5],5/6) and u['Urine_HoursSinceLast'][5]==0)
    two=pd.DataFrame({'event_hour':np.arange(2.,11.,2),'available_hour':np.arange(2.,11.,2),'value':[100.]*5})
    u2=urine_features(two,np.array([10.,11.]),np.array([70.,70.]))
    check('two_hourly_urine_counts_as_covered',np.isclose(u2['Urine_mlkg_h_6h'][0],300/(6*70)) and u2['UrineCoverage_6h'][0]==3
          and u2['Urine_HoursSinceLast'][1]==1)
    gap=pd.DataFrame({'event_hour':[2.,8.],'available_hour':[2.,8.],'value':[10.,120.]})
    u3=urine_features(gap,np.array([10.]),np.array([50.]))
    check('urine_interval_straddling_window_prorated',np.isclose(u3['UrineCoverageFraction_6h'][0],4/6) and np.isclose(u3['Urine_mlkg_h_6h'][0],80/(4*50)))
    late=pd.DataFrame({'event_hour':[1.,2.,3.,4.,5.],'available_hour':[1.,2.,3.,4.,9.],'value':[50.]*5})
    check('urine_rate_uses_only_available_records',np.isnan(urine_features(late,np.array([5.]),np.array([70.]))['Urine_mlkg_h_6h'][0]))
    zero=urine.copy();zero['value']=0.;missing=urine.iloc[:0]
    check('missing_urine_not_observed_zero',np.isnan(urine_features(missing,np.array([6.]),np.array([70.]))['UrineOutput'][0]) and urine_features(zero,np.array([6.]),np.array([70.]))['UrineOutput'][0]==0)
    check('AKI_not_trauma',text_flags('Acute kidney injury')['Phenotype_trauma']==0)
    check('nontraumatic_not_trauma',text_flags('Nontraumatic subarachnoid hemorrhage')['Phenotype_trauma']==0)
    check('negation_not_postoperative',text_flags('No surgical procedure performed')['Phenotype_postoperative']==0)
    check('true_trauma_retained',text_flags('Traumatic brain injury')['Phenotype_trauma']==1)
    check('urinary_site_over_collection_device',specimen_site('Urine, Catheter')=='urine')
    check('pneumonia_source',specimen_site('pneumonia')=='respiratory')
    check('comorbidity_icd9_icd10',comorbidity_flags('4280',9)=={'chronic_heart_failure'} and comorbidity_flags('E119',10)=={'diabetes'}
          and comorbidity_flags('C787',10)=={'metastatic_carcinoma'} and comorbidity_flags('C9100',10)=={'hematological_malignancy'})
    check('comorbidity_text_and_negation',comorbidity_flags(text='renal failure - hemodialysis')=={'chronic_organ_insufficiency'}
          and not comorbidity_flags(text='endocrine|pituitary|diabetes insipidus') and not comorbidity_flags(text='No Health Problems'))
    check('broader_comorbidities',comorbidity_flags('J449',10)=={'chronic_pulmonary_disease'} and comorbidity_flags('A419',10)=={'prior_sepsis'}
          and comorbidity_flags(text='dementia')=={'dementia'} and comorbidity_flags('C349',10)=={'solid_tumor'})
    check('acute_codes_not_comorbidity',not comorbidity_flags('I10',10) and not comorbidity_flags('N179',10) and not comorbidity_flags('K720',10))
    mapping,_=organ_mapping(['GCS','UrineOutput','VasopressorRecorded','Phosphate','pH'])
    check('organ_mapping',mapping=={'GCS':'neurologic','UrineOutput':'renal','VasopressorRecorded':'cardiovascular','Phosphate':'metabolic','pH':'respiratory'})

    # Execute BOTH SQL adapters on minimal schema-shaped fixtures.
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        selected=pd.DataFrame({'stay_id':[1],'first_hour':[0.],'followup_end':[24.],'first_positive':[np.nan],'OnsetHour':[np.nan],'Outcome':[0]})
        root=td/'eicu';root.mkdir()

        # Regression for the real eICU note.csv failure: 8 CSV fields, with commas
        # inside three quoted free-text fields.  Strict parsing must preserve the
        # row rather than using ignore_errors/null_padding.
        note_fixture=root/'note.csv'
        note_fixture.write_text(
            'c1,patientunitstayid,c3,c4,c5,c6,c7,c8\n'
            '4327685,260961,1710,1710,Brief Progress,'
            '"notes/Progress Notes/Interventions/Intermediate/Best-practice therapies (e.g. DVT, beta blocker, etc.)",'
            '"Best-practice therapies (e.g. DVT, beta blocker, etc.)",'
            '"Best-practice therapies (e.g. DVT, beta blocker, etc.)"\n'
        )
        con=duckdb.connect()
        parsed=con.execute(f'SELECT * FROM {csv_scan(note_fixture)}').df()
        grouped=con.execute(
            f'SELECT TRY_CAST(patientunitstayid AS BIGINT) id,COUNT(*) n '
            f'FROM {csv_scan(note_fixture)} GROUP BY 1 ORDER BY 1'
        ).df()
        con.close()
        check('quoted_eicu_note_row_has_8_columns',parsed.shape==(1,8))
        check('quoted_eicu_note_commas_preserved','DVT, beta blocker' in parsed.loc[0,'c6'])
        check('quoted_eicu_note_partition_id_preserved',
              grouped.to_dict('records')==[{'id':260961,'n':1}])

        pd.DataFrame({'patientunitstayid':[1],'uniquepid':['p1'],'hospitalid':[1],'unitadmitsource':['Emergency Department'],'apacheadmissiondx':['Acute kidney injury'],'admissionweight':['80']}).to_csv(root/'patient.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1],'observationoffset':[60],'noninvasivesystolic':['95'],'noninvasivediastolic':['55']}).to_csv(root/'vitalAperiodic.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1],'pasthistoryoffset':[0],'pasthistoryenteredoffset':[240],
            'pasthistorypath':['notes/Progress Notes/Past History/Organ Systems/Cardiovascular (R)/Congestive Heart Failure/CHF'],'pasthistoryvaluetext':['CHF']}).to_csv(root/'pastHistory.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1],'diagnosisoffset':[30],'diagnosisstring':['endocrine|glucose metabolism|diabetes mellitus'],'icd9code':['250.00, E11.9']}).to_csv(root/'diagnosis.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1],'treatmentoffset':[120],'treatmentstring':['pulmonary|ventilation and oxygenation|mechanical ventilation']}).to_csv(root/'treatment.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1,1],'infusionoffset':[60,120],'drugname':['Norepinephrine (mcg/min)']*2,'drugrate':['4','0'],'infusionrate':['4','0'],'patientweight':['70','70']}).to_csv(root/'infusionDrug.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1],'intakeoutputoffset':[60],'intakeoutputentryoffset':[180],'cellpath':['flowsheet|I&O|Output (ml)|Urine'],'celllabel':['Foley urine'],'cellvaluenumeric':[50]}).to_csv(root/'intakeOutput.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1],'labresultoffset':[60],'labresultrevisedoffset':[180],'labname':['creatinine'],'labresult':['2'],'labmeasurenamesystem':['mg/dL']}).to_csv(root/'lab.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1],'observationoffset':[60],'heartrate':['80']}).to_csv(root/'vitalPeriodic.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1]*4,'nursingchartoffset':[60,60,60,60],'nursingchartentryoffset':[180,90,90,120],
            'nursingchartcelltypevallabel':['Glasgow coma score','Glasgow coma score','Pupils','Temperature'],
            'nursingchartcelltypevalname':['GCS Total','Eyes','Eyes','Temperature (F)'],'nursingchartvalue':['12','3','4','101']}).to_csv(root/'nurseCharting.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1],'respchartoffset':[60],'respchartentryoffset':[120],'respchartvaluelabel':['FiO2'],'respchartvalue':['40%']}).to_csv(root/'respiratoryCharting.csv',index=False)
        ex=RawExtractor('eicu',root,selected,td/'eicu_stage',12);paths=ex.extract()
        support=pd.read_parquet(td/'eicu_stage/support.parquet')
        check('zero_rate_not_active',support.sort_values('event_hour').value.tolist()==[1.,0.])
        raw=pd.read_parquet(td/'eicu_stage/urine.parquet');check('eicu_entry_time_used',raw.available_hour.iloc[0]==3)
        all_ev=normalize_events(pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True))
        seq=build_sequence(all_ev,{**selected.iloc[0].to_dict(),'Age':60.,'Gender':1.},12,6)
        check('delayed_GCS_not_visible_early',seq.GCS.iloc[:2].isna().all() and seq.GCS.iloc[2]==12)
        check('strict_urine_availability',np.isnan(seq.UrineOutput.iloc[0]) and seq.UrineOutput_6h.iloc[2]==50)
        check('one_urine_record_no_rate',seq.Oliguria6h.isna().all())
        check('eicu_nurse_temperature_fahrenheit_converted',np.isclose(seq.Temp.iloc[1],(101-32)*5/9) and np.isnan(seq.Temp.iloc[0]))
        check('eicu_cuff_blood_pressure',seq.SBP.iloc[0]==95 and seq.DBP.iloc[0]==55)
        check('eicu_admission_weight_known_at_admission',pd.read_parquet(td/'eicu_stage/admission_weight.parquet').value.tolist()==[80.])
        check('eicu_gcs_component_needs_gcs_label',(all_ev.feature=='GCS_Eyes').sum()==1 and seq.GCS_Below15.iloc[1]==1 and np.isnan(seq.GCS_Below15.iloc[0]))
        check('eicu_comorbidity_from_entry_time',seq.Comorbidity_chronic_heart_failure.tolist()==[0.,0.,0.]+[1.]*9
              and seq.Comorbidity_diabetes.eq(1).all() and seq.Comorbidity_metastatic_carcinoma.eq(0).all())
        check('eicu_ventilation_treatment_is_airway',np.isnan(seq.Intubated.iloc[0]) and seq.Intubated.iloc[1]==1 and seq.IntubatedHours.iloc[3]==3)
        root=td/'miiv';(root/'icu').mkdir(parents=True);(root/'hosp').mkdir()
        pd.DataFrame({'stay_id':[1],'hadm_id':[10],'subject_id':[100],'intime':['2100-01-01 00:00:00'],'outtime':['2100-01-02 00:00:00']}).to_csv(root/'icu/icustays.csv',index=False)
        ce=[(220045,'01:00','03:00',100.,'100','bpm'),(223900,'00:30','00:30',5.,'Oriented',''),(220739,'01:00','01:00',3.,'To Speech',''),
            (223901,'01:00','01:00',6.,'Obeys Commands',''),(223900,'02:00','02:00',1.,'No Response-ETT',''),
            (226732,'02:00','02:00',np.nan,'Endotracheal tube',''),(226732,'08:00','08:00',np.nan,'Nasal cannula','')]
        pd.DataFrame([{'stay_id':1,'itemid':i,'charttime':'2100-01-01 '+c+':00','storetime':'2100-01-01 '+st+':00','valuenum':v,'value':t,'valueuom':u}
            for i,c,st,v,t,u in ce]).to_csv(root/'icu/chartevents.csv',index=False)
        # Earlier admission (discharged before this ICU stay), the current one, and a LATER one.
        pd.DataFrame({'subject_id':[100]*3,'hadm_id':[9,10,11],'admittime':['2099-11-20','2099-12-31','2100-02-01'],
            'dischtime':['2099-12-01 00:00:00','2100-01-05 00:00:00','2100-02-10 00:00:00'],'admission_location':['EMERGENCY ROOM']*3}).to_csv(root/'hosp/admissions.csv',index=False)
        pd.DataFrame({'subject_id':[100]*3,'hadm_id':[9,10,11],'seq_num':[1,1,1],'icd_code':['4280','E119','1977'],'icd_version':[9,10,9]}).to_csv(root/'hosp/diagnoses_icd.csv',index=False)
        pd.DataFrame({'hadm_id':[10],'itemid':[50912],'charttime':['2100-01-01 01:00:00'],'storetime':['2100-01-01 04:00:00'],'valuenum':[2.],'valueuom':['mg/dL']}).to_csv(root/'hosp/labevents.csv',index=False)
        pd.DataFrame({'stay_id':[1,1],'itemid':[227488,227489],'charttime':['2100-01-01 01:00:00']*2,'storetime':['2100-01-01 02:00:00']*2,'value':[100.,150.],'valueuom':['mL']*2}).to_csv(root/'icu/outputevents.csv',index=False)
        pd.DataFrame({'stay_id':[1],'itemid':[221906],'starttime':['2100-01-01 01:00:00'],'storetime':['2100-01-01 02:00:00'],'rate':[0.],'statusdescription':['FinishedRunning']}).to_csv(root/'icu/inputevents.csv',index=False)
        ex=RawExtractor('miiv',root,selected,td/'miiv_stage',12);paths=ex.extract()
        raw=pd.read_parquet(td/'miiv_stage/chartevents.parquet');check('mimic_store_time_used',raw.available_hour.iloc[0]==3)
        raw=pd.read_parquet(td/'miiv_stage/urine.parquet');check('irrigant_subtracted',raw.value.sum()==50.)
        mv=build_sequence(normalize_events(pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)),{**selected.iloc[0].to_dict(),'Age':60.,'Gender':1.},12,6)
        check('gcs_from_components_then_ett_resets_verbal',mv.GCS.iloc[0]==14 and mv.GCS.iloc[1:].isna().all())
        check('gcs_below15_from_partial_components_no_expiry',mv.GCS_Below15.eq(1).all())
        check('mimic_airway_from_device_and_ett',mv.Intubated.tolist()==[0.]+[1.]*6+[0.]*5 and mv.IntubatedHours.tolist()==[0.,1,2,3,4,5,6,6,6,6,6,6])
        check('mimic_comorbidity_only_from_earlier_admissions',mv.Comorbidity_chronic_heart_failure.eq(1).all()
              and mv.Comorbidity_diabetes.eq(0).all() and mv.Comorbidity_metastatic_carcinoma.eq(0).all())

    # MIMIC item dictionaries: label-resolved items, alarm-limit exclusion, ng/L troponin, airway procedures.
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);root=td/'miiv';(root/'icu').mkdir(parents=True);(root/'hosp').mkdir()
        sel=pd.DataFrame({'stay_id':[1],'first_hour':[0.],'followup_end':[24.],'first_positive':[np.nan],'OnsetHour':[np.nan],'Outcome':[0]})
        pd.DataFrame({'stay_id':[1],'hadm_id':[10],'subject_id':[100],'intime':['2100-01-01 00:00:00'],'outtime':['2100-01-02 00:00:00']}).to_csv(root/'icu/icustays.csv',index=False)
        pd.DataFrame({'itemid':[225792,225794,224385,227194,228640,228641,228642],'label':['Invasive Ventilation','Non-invasive Ventilation','Intubation','Extubation','EtCO2','EtCO2 Alarm - High','EtCO2 Clinical indication'],
            'linksto':['procedureevents']*4+['chartevents']*3}).to_csv(root/'icu/d_items.csv',index=False)
        pd.DataFrame({'itemid':[51002,52642,51003],'label':['Troponin I','Troponin I','Troponin T']}).to_csv(root/'hosp/d_labitems.csv',index=False)
        pd.DataFrame({'stay_id':[1]*3,'itemid':[224385,225794,227194],'starttime':['2100-01-01 02:00:00','2100-01-01 03:00:00','2100-01-01 06:00:00'],
            'storetime':['2100-01-01 02:30:00','2100-01-01 03:00:00','2100-01-01 07:00:00']}).to_csv(root/'icu/procedureevents.csv',index=False)
        pd.DataFrame({'stay_id':[1,1],'itemid':[228640,228641],'charttime':['2100-01-01 01:00:00']*2,'storetime':['2100-01-01 01:00:00']*2,'valuenum':[35.,60.],'value':['35','60'],'valueuom':['mmHg']*2}).to_csv(root/'icu/chartevents.csv',index=False)
        pd.DataFrame({'hadm_id':[10,10],'itemid':[52642,51003],'charttime':['2100-01-01 01:00:00']*2,'storetime':['2100-01-01 02:00:00']*2,'valuenum':[250.,.05],'valueuom':['ng/L','ng/mL']}).to_csv(root/'hosp/labevents.csv',index=False)
        pd.DataFrame({'stay_id':[1],'itemid':[226559],'charttime':['2100-01-01 01:00:00'],'storetime':['2100-01-01 01:00:00'],'value':[50.],'valueuom':['mL']}).to_csv(root/'icu/outputevents.csv',index=False)
        paths=RawExtractor('miiv',root,sel,td/'st',12).extract()
        d=pd.read_csv(td/'st/item_dictionary.csv')
        check('label_resolved_items_without_alarm_limits',set(d.key[d.feature.eq('TroponinI')])=={51002,52642} and set(d.key[d.feature.eq('EtCO2')])=={228640})
        mv=build_sequence(normalize_events(pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)),{**sel.iloc[0].to_dict(),'Age':60.,'Gender':1.},12,6)
        check('troponin_ng_per_litre_converted',mv.TroponinI.iloc[1]==.25 and mv.TroponinT.iloc[1]==.05 and mv.EtCO2.iloc[0]==35)
        check('airway_procedures_causal_and_noninvasive_excluded',mv.Intubated.iloc[:7].tolist()[2:]==[1.,1,1,1,0] and np.isnan(mv.Intubated.iloc[1])
              and mv.IntubatedHours.iloc[7]==4)

    # v10.4 exposures, admission context and admitting diagnosis on schema-shaped fixtures (both databases).
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);sel=pd.DataFrame({'stay_id':[1],'first_hour':[0.],'followup_end':[24.],'first_positive':[np.nan],'OnsetHour':[np.nan],'Outcome':[0]})
        root=td/'miiv';(root/'icu').mkdir(parents=True);(root/'hosp').mkdir()
        T=lambda h:str(pd.Timestamp('2100-01-01')+pd.Timedelta(hours=h))
        pd.DataFrame({'stay_id':[1],'hadm_id':[10],'subject_id':[100],'intime':[T(0)],'outtime':[T(30)],'first_careunit':['Medical Intensive Care Unit (MICU)']}).to_csv(root/'icu/icustays.csv',index=False)
        pd.DataFrame({'subject_id':[100],'hadm_id':[10],'admittime':[T(-30)],'dischtime':[T(60)],'admission_location':['EMERGENCY ROOM']}).to_csv(root/'hosp/admissions.csv',index=False)
        pd.DataFrame({'subject_id':[100,100],'hadm_id':[10,10],'careunit':['Emergency Department','Medicine'],'intime':[T(-30),T(-20)]}).to_csv(root/'hosp/transfers.csv',index=False)
        pd.DataFrame({'itemid':[225752,224263,225202,227194,225158,226361],'label':['Arterial Line','Multi Lumen','Foley Catheter Removed','Extubation','NaCl 0.9%','Pre-Admission Intake'],
            'linksto':['procedureevents']*4+['inputevents']*2}).to_csv(root/'icu/d_items.csv',index=False)
        pd.DataFrame({'stay_id':[1]*3,'itemid':[225752,224263,225202],'starttime':[T(2),T(5),T(3)],'storetime':[T(3),T(5),T(3)]}).to_csv(root/'icu/procedureevents.csv',index=False)
        pd.DataFrame({'hadm_id':[10]*4,'drug':['Tacrolimus','Metoprolol Tartrate','Hydrocortisone Cream 1%','Vancomycin'],'starttime':[T(1),T(4),T(2),T(1)]}).to_csv(root/'hosp/prescriptions.csv',index=False)
        pd.DataFrame({'stay_id':[1,1],'itemid':[225158,225158],'starttime':[T(1),T(6)],'endtime':[T(2),T(9)],'storetime':[T(2),T(9)],'amount':[500.,1000.],
            'amountuom':['ml','ml'],'ordercategoryname':['03-IV Fluid Bolus','02-Fluids (Crystalloids)'],'statusdescription':['FinishedRunning']*2,'rate':[0.,0.]}).to_csv(root/'icu/inputevents.csv',index=False)
        pd.DataFrame({'hadm_id':[10,10],'ordertime':[T(3),T(4)],'order_type':['Radiology','Medications']}).to_csv(root/'hosp/poe.csv',index=False)
        pd.DataFrame({'stay_id':[1],'itemid':[226559],'charttime':[T(1)],'storetime':[T(1)],'value':[50.],'valueuom':['mL']}).to_csv(root/'icu/outputevents.csv',index=False)
        pd.DataFrame({'stay_id':[1],'itemid':[220045],'charttime':[T(1)],'storetime':[T(1)],'valuenum':[90.],'value':['90'],'valueuom':['bpm']}).to_csv(root/'icu/chartevents.csv',index=False)
        paths=RawExtractor('miiv',root,sel,td/'ms',12).extract()
        meta=pd.read_parquet(td/'ms/metadata.parquet').iloc[0].to_dict()
        mv=build_sequence(normalize_events(pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)),{**meta,'Age':60.,'Gender':1.},12,6)
        check('mimic_admission_context',mv.HospitalHoursBeforeICU.eq(30).all() and mv.AdmitSource_Ward.eq(1).all() and mv.AdmitSource_ED.eq(0).all()
              and mv.ICUType_Medical.eq(1).all() and mv.ICUType_Surgical.eq(0).all() and mv.AdmitDx_Infection.isna().all())
        check('mimic_devices_from_store_time_removals_ignored',mv.Device_ArterialLine.tolist()[:4]==[0,0,1,1] and mv.Device_ArterialLine_Hours.iloc[3]==2
              and mv.Device_CentralLine.iloc[4]==1 and mv.Device_UrinaryCatheter.eq(0).all())
        check('mimic_medications_24h_no_topical_no_antibiotic_feature',mv.Med_Immunosuppressant_24h.tolist()==[1.]*12 and mv.Med_BetaBlocker_24h.tolist()[2:4]==[0.,1.]
              and mv.Med_Hydrocortisone_24h.eq(0).all() and not any('ntibiot' in c and c!='PriorAntibiotics_90d' and not c.startswith('PriorAntibiotics_90d') for c in mv.columns))
        check('mimic_fluids_known_at_end_and_imaging',mv.FluidIn_6h.tolist()[:3]==[0.,500.,500.] and mv.FluidIn_24h.iloc[8]==1500 and mv.FluidIn_6h.iloc[8]==1000
              and mv.Imaging_24h.iloc[2]==1 and mv.Imaging_24h.iloc[1]==0)
        root=td/'eicu';root.mkdir()
        pd.DataFrame({'patientunitstayid':[1],'uniquepid':['p1'],'hospitalid':[1],'unitadmitsource':['Operating Room'],'unittype':['CTICU'],
            'hospitaladmitoffset':[-600],'apacheadmissiondx':['x']}).to_csv(root/'patient.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1]*3,'treatmentoffset':[60,120,180],'treatmentstring':['cardiovascular|vascular access|central venous catheter',
            'renal|urinary catheter|foley catheter','pulmonary|radiologic procedures|chest x-ray']}).to_csv(root/'treatment.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1,1],'drugname':['PROPOFOL 10 MG/ML','ACETAMINOPHEN 325 MG'],'drugstartoffset':[60,60],'drugorderoffset':[30,240],
            'drugordercancelled':['No','No']}).to_csv(root/'medication.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1]*4,'intakeoutputoffset':[60,60,120,120],'intakeoutputentryoffset':[60,60,180,120],
            'cellpath':['flowsheet|I&O|Intake (ml)|Crystalloids|NS','flowsheet|I&O|Intake (ml)|Enteral|Tube feeding','flowsheet|I&O|Intake (ml)|Blood Products|PRBC','flowsheet|I&O|Output (ml)|Urine'],
            'celllabel':['NS','tube feeding','PRBC','Urine'],'cellvaluenumeric':[250,100,300,40]}).to_csv(root/'intakeOutput.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1,1],'admitdxenteredoffset':[90,90],'admitdxpath':['admission diagnosis|Operative|Diagnosis|Cardiovascular|Valve replacement',
            'admission diagnosis|Was the patient admitted from the O.R. or went to the O.R. within 4 hours of admission?|Yes']}).to_csv(root/'admissionDx.csv',index=False)
        paths=RawExtractor('eicu',root,sel,td/'es',12).extract()
        meta=pd.read_parquet(td/'es/metadata.parquet').iloc[0].to_dict()
        es=build_sequence(normalize_events(pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)),{**meta,'Age':60.,'Gender':1.},12,6)
        check('eicu_admission_context',es.HospitalHoursBeforeICU.eq(10).all() and es.AdmitSource_OR.eq(1).all() and es.ICUType_Cardiac.eq(1).all())
        check('eicu_admitting_diagnosis_from_entry_time',np.isnan(es.AdmitDx_Operative.iloc[0]) and es.AdmitDx_Operative.iloc[1]==1 and es.AdmitDx_Infection.iloc[1]==0)
        check('eicu_devices_imaging_from_treatments',es.Device_CentralLine.iloc[0]==1 and es.Device_UrinaryCatheter.tolist()[:2]==[0.,1.] and es.Imaging_24h.iloc[2]==1)
        check('eicu_medication_available_at_order_entry',es.Med_Sedative_24h.iloc[0]==1 and es.Med_Antipyretic_24h.tolist()[2:4]==[0.,1.])
        check('eicu_fluids_exclude_enteral_and_split_transfusion',es.FluidIn_6h.iloc[0]==250 and es.Transfusion_24h.tolist()[1:3]==[0.,300.])

    # v10.5: text states, vasopressor dose, procedures, nutrition, stool, prior contact, lab changes, AKI (both databases).
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);sel=pd.DataFrame({'stay_id':[1],'first_hour':[0.],'followup_end':[24.],'first_positive':[np.nan],'OnsetHour':[np.nan],'Outcome':[0]})
        root=td/'miiv';(root/'icu').mkdir(parents=True);(root/'hosp').mkdir()
        T=lambda h:str(pd.Timestamp('2100-01-01')+pd.Timedelta(hours=h))
        pd.DataFrame({'stay_id':[1,2],'hadm_id':[10,10],'subject_id':[100,100],'intime':[T(0),T(-40)],'outtime':[T(30),T(-30)]}).to_csv(root/'icu/icustays.csv',index=False)
        pd.DataFrame({'subject_id':[100]*3,'hadm_id':[8,9,10],'admittime':[T(-24*400),T(-24*30),T(-48)],'dischtime':[T(-24*390),T(-24*20),T(60)],
            'admission_location':['EMERGENCY ROOM','EMERGENCY ROOM','TRANSFER FROM SKILLED NURSING FACILITY']}).to_csv(root/'hosp/admissions.csv',index=False)
        pd.DataFrame({'subject_id':[100,100,100],'hadm_id':[9,None,10],'charttime':[T(-24*25),T(-60),T(-10)],'org_name':['E. COLI','STAPH AUREUS','KLEBSIELLA'],'spec_type_desc':['URINE','BLOOD CULTURE','SPUTUM']}).to_csv(root/'hosp/microbiologyevents.csv',index=False)
        pd.DataFrame({'itemid':[221906,222315,225802,225194,226579,228332,220048,226588,223951,224056],'label':['Norepinephrine','Vasopressin','Dialysis - CRRT','Peptamen 1.5 (Full)','Stool','Delirium assessment','Heart Rhythm','Chest Tube #1','Capillary Refill R','Skin Color'],
            'linksto':['inputevents','inputevents','procedureevents','inputevents','outputevents','chartevents','chartevents','outputevents','chartevents','chartevents']}).to_csv(root/'icu/d_items.csv',index=False)
        pd.DataFrame({'subject_id':[100,100],'hadm_id':[9,10],'starttime':[T(-24*25),T(1)],'drug':['Vancomycin','Ceftriaxone']}).to_csv(root/'hosp/prescriptions.csv',index=False)
        ce=[(226732,1,1,np.nan,'High flow nasal cannula'),(226732,4,4,np.nan,'Bipap mask '),(226732,6,6,np.nan,'Nasal cannula'),(228332,2,2,np.nan,'Positive'),
            (220048,1,1,np.nan,'SR (Sinus Rhythm)'),(220048,3,3,np.nan,'AF (Atrial Fibrillation)'),(228096,2,2,np.nan,'-2 Light sedation'),(226730,0,0,170.,'170'),(226512,0,0,80.,'80'),(223791,2,2,np.nan,'7 Severe'),(223951,1,1,np.nan,'Abnormal >3 sec'),(223951,4,4,np.nan,'Normal <3 secs'),(224056,2,2,np.nan,'Mottled')]
        pd.DataFrame([{'stay_id':1,'itemid':i,'charttime':T(c),'storetime':T(st),'valuenum':v,'value':t,'valueuom':'kg' if i==226512 else ''} for i,c,st,v,t in ce]).to_csv(root/'icu/chartevents.csv',index=False)
        pd.DataFrame({'stay_id':[1]*4,'itemid':[221906,221906,222315,225194],'starttime':[T(2),T(5),T(3),T(1)],'endtime':[T(5),T(9),T(9),T(3)],'storetime':[T(2),T(5),T(3),T(1)],
            'rate':[.2,0.,2.4,30.],'rateuom':['mcg/kg/min','mcg/kg/min','units/hour','mL/hour'],'amount':[1,1,1,60.],'amountuom':['mg','mg','units','ml'],
            'ordercategoryname':['01-Drips','01-Drips','01-Drips','10-Enteral Nutrition'],'statusdescription':['Changed','FinishedRunning','FinishedRunning','FinishedRunning']}).to_csv(root/'icu/inputevents.csv',index=False)
        pd.DataFrame({'stay_id':[1],'itemid':[225802],'starttime':[T(4)],'storetime':[T(4)]}).to_csv(root/'icu/procedureevents.csv',index=False)
        pd.DataFrame({'stay_id':[1,1,1],'itemid':[226559,226579,226588],'charttime':[T(1),T(2),T(3)],'storetime':[T(1),T(2),T(3)],'value':[50.,200.,120.],'valueuom':['mL']*3}).to_csv(root/'icu/outputevents.csv',index=False)
        pd.DataFrame({'hadm_id':[10]*6,'itemid':[50912]*4+[51487,51486],'charttime':[T(-20),T(1),T(4),T(7),T(2),T(2)],'storetime':[T(-19),T(2),T(5),T(8),T(3),T(3)],
            'valuenum':[1.,1.2,1.6,2.1,np.nan,np.nan],'value':['1.0','1.2','1.6','2.1','POS','NEG'],'valueuom':['mg/dL']*4+['','']}).to_csv(root/'hosp/labevents.csv',index=False)
        paths=RawExtractor('miiv',root,sel,td/'ms',12).extract()
        meta=pd.read_parquet(td/'ms/metadata.parquet').iloc[0].to_dict()
        mv=build_sequence(normalize_events(pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)),{**meta,'Age':60.,'Gender':1.},12,6)
        check('mimic_o2_support_states',mv.O2_HighFlow.tolist()[:6]==[1.,1,1,0,0,0] and mv.O2_NIV.tolist()[3:6]==[1.,1,0.] and mv.SupplementalO2.iloc[0]==1)
        check('mimic_delirium_af_rass',mv.Delirium.iloc[1]==1 and np.isnan(mv.Delirium.iloc[0]) and mv.Rhythm_AF.tolist()[:3]==[0.,0.,1.] and mv.RASS.iloc[1]==-2)
        check('mimic_vasopressor_ne_equivalent',np.isclose(mv.VasopressorDose_NEeq.iloc[1],.2) and np.isclose(mv.VasopressorDose_NEeq.iloc[2],.2+2.4/60*2.5)
              and np.isclose(mv.VasopressorDose_NEeq.iloc[4],2.4/60*2.5) and mv.VasopressorDose_NEeq.iloc[0]==0)
        check('mimic_rrt_enteral_stool',mv.Procedure_RRT_24h.tolist()[2:5]==[0.,1.,1.] and mv.Nutrition_Enteral_24h.iloc[0]==1 and mv.StoolRecords_24h.iloc[1]==1)
        check('mimic_prior_contact',mv.PriorAdmissions_1y.eq(1).all() and np.isclose(mv.DaysSinceLastDischarge.iloc[0],20) and mv.PriorICUStays_SameAdmission.eq(1).all()
              and mv.AdmitFrom_NursingFacility.eq(1).all() and mv.PriorPositiveCulture_1y.eq(1).all())
        check('mimic_pain_dipstick_drains',mv.PainScore.iloc[1]==7 and mv.UrineNitrite.iloc[2]==1 and mv.UrineLeukEsterase.iloc[2]==0
              and np.isnan(mv.UrineNitrite.iloc[1]) and mv.DrainOutput_24h.iloc[2]==120 and mv.StoolRecords_24h.iloc[2]==1)
        check('mimic_perfusion_signs_prior_antibiotics',mv.CapRefill_Abnormal.tolist()[:4]==[1.,1,1,0] and mv.Skin_Abnormal.iloc[1]==1
              and mv.PriorAntibiotics_90d.eq(1).all())
        check('mimic_height_bmi_iculos',mv.Height.eq(170).all() and np.isclose(mv.BMI.iloc[0],80/1.7**2) and mv.ICULOS.tolist()==list(range(1,13)))
        check('lab_changes_and_aki',np.isnan(mv.Creatinine_DeltaPrev.iloc[0]) and np.isclose(mv.Creatinine_DeltaPrev.iloc[1],.2) and np.isclose(mv.Creatinine_DeltaBaseline.iloc[4],.6)
              and mv.AKI_Stage.tolist()[:8]==[0.,0.,0.,3.,3.,3.,3.,3.] and mv.LabResults_24h.iloc[7]==5)
        cr=pd.DataFrame({'event_hour':[0.,10.,20.],'available_hour':[1.,11.,21.],'value':[1.,1.6,3.1]})
        st=aki_stage(cr,np.array([2.,12.,22.]),np.array([np.nan,.3,np.nan]),np.zeros(3))
        check('aki_creatinine_and_urine_criteria',st.tolist()==[0.,1.,3.])
        root=td/'eicu';root.mkdir()
        pd.DataFrame({'patientunitstayid':[1],'uniquepid':['p1'],'hospitalid':[1],'unitadmitsource':['Floor'],'unittype':['MICU'],'hospitaladmitoffset':[-60],
            'apacheadmissiondx':['x'],'admissionweight':['100'],'admissionheight':['180'],'unitvisitnumber':['2']}).to_csv(root/'patient.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1]*3,'infusionoffset':[60,120,300],'drugname':['Norepinephrine (mcg/min)','Vasopressin (units/min)','Norepinephrine (mcg/min)'],
            'drugrate':['10','0.04','0'],'infusionrate':['10','0.04','0']}).to_csv(root/'infusionDrug.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1]*3,'treatmentoffset':[60,120,180],'treatmentstring':['pulmonary|ventilation and oxygenation|non-invasive ventilation',
            'renal|dialysis|C V V H','pulmonary|bronchoscopy']}).to_csv(root/'treatment.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1]*2,'nursingchartoffset':[60,60],'nursingchartentryoffset':[60,60],'nursingchartcelltypevallabel':['Delirium Scale/Score','Sedation Scale/Score/Goal'],
            'nursingchartcelltypevalname':['Delirium Score','Sedation Score'],'nursingchartvalue':['Yes','-1']}).to_csv(root/'nurseCharting.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1]*3,'intakeoutputoffset':[60,60,120],'intakeoutputentryoffset':[60,60,120],
            'cellpath':['flowsheet|I&O|Intake (ml)|Enteral|Jevity','flowsheet|I&O|Output (ml)|Urine','flowsheet|I&O|Output (ml)|Stool'],'celllabel':['Jevity','Urine','Stool'],
            'cellvaluenumeric':[50,40,100]}).to_csv(root/'intakeOutput.csv',index=False)
        paths=RawExtractor('eicu',root,sel,td/'es',12).extract()
        meta=pd.read_parquet(td/'es/metadata.parquet').iloc[0].to_dict()
        es=build_sequence(normalize_events(pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)),{**meta,'Age':60.,'Gender':1.},12,6)
        check('eicu_delirium_rass_niv_rrt_bronch',es.Delirium.iloc[0]==1 and es.RASS.iloc[0]==-1 and es.O2_NIV.iloc[0]==1 and es.Procedure_RRT_24h.tolist()[:2]==[0.,1.]
              and es.Procedure_Bronchoscopy_24h.iloc[2]==1)
        check('eicu_vasopressor_dose_per_kg',np.isclose(es.VasopressorDose_NEeq.iloc[0],.1) and np.isclose(es.VasopressorDose_NEeq.iloc[1],.1+.04*2.5)
              and np.isclose(es.VasopressorDose_NEeq.iloc[4],.04*2.5))
        check('eicu_nutrition_stool_height_prior_icu',es.Nutrition_Enteral_24h.iloc[0]==1 and es.StoolRecords_24h.iloc[1]==1 and es.Height.eq(180).all()
              and es.PriorICUStays_SameAdmission.eq(1).all() and es.PriorAdmissions_1y.isna().all())

    meta={'followup_end':24.,'OnsetHour':10.,'Age':60.,'Gender':1.}
    seq=build_sequence(all_ev,meta,12,6)
    # Post-onset hours are kept for trajectory (utility) scoring but can never be trained on or scored as incident risk;
    # and keeping them must not change any pre-onset row (feature causality).
    post=seq[seq.Hour>=10];pre=seq[seq.Hour<=9];trunc=build_sequence(all_ev,{**meta},9,6)
    check('post_onset_rows_present_ineligible',seq.Hour.max()==12 and len(post)==3 and post.Eligible.eq(0).all() and post.SepsisLabel.eq(0).all())
    check('pre_onset_rows_unchanged_by_post_onset_rows',pre.reset_index(drop=True).equals(trunc.reset_index(drop=True)))
    check('six_hour_target',seq.loc[seq.Hour.eq(3),'SepsisLabel'].item()==0 and seq.loc[seq.Hour.eq(4),'SepsisLabel'].item()==1)
    seq2=build_sequence(all_ev,{**meta,'OnsetHour':np.nan,'followup_end':10.},12,6)
    check('negative_followup_censoring',seq2.loc[seq2.Hour.eq(4),'Eligible'].item()==1 and seq2.loc[seq2.Hour.eq(5),'Eligible'].item()==0)

    features=['HR','Creatinine','GCS','HR_observed','Creatinine_observed','GCS_observed']
    torch.manual_seed(1);bank=ObserverBank(features)
    x=torch.zeros(2,12,len(features));x[:,:,3:]=0
    z=bank(x);check('all_missing_observers_exactly_abstain',torch.equal(z['active'],torch.zeros_like(z['active'])) and torch.equal(z['logit'],torch.zeros_like(z['logit'])))
    x=torch.randn(2,12,len(features));x[:,:,3:]=1
    x2=x.clone();x2[:,7:,:3]=torch.randn_like(x2[:,7:,:3])*100
    mask=torch.ones(2,12);hours=torch.arange(1,13).float().expand(2,-1)
    for arm in ['osta','observer_features','output_fusion','gated_attention','cnn']:
        with contextlib.redirect_stdout(io.StringIO()):model=ExperimentModel(features,arm,bank.names,small=True,dropout=0.)
        for mode in ['eval','train']:
            getattr(model,mode)()
            with torch.no_grad():a=model(x,mask,hours,bank(x));b=model(x2,mask,hours,bank(x2))
            check(f'{arm}_{mode}_future_invariance',float((a[:,:7]-b[:,:7]).abs().max())<1e-5)
        if arm=='gated_attention':
            no=perturb_guidance(bank(x),'missing_all');model(x,mask,hours,no)
            check('missing_guidance_zero_attention_bias',model.last_bias.abs().max().item()==0)
            model(x,mask,hours,bank(x));check('active_guidance_exercised',model.last_bias.abs().max().item()>0)
        model.train();model.zero_grad();logits=model(x,mask,hours,bank(x));loss=nn_loss(logits);loss.backward()
        check(f'{arm}_backward_finite',all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None))
    print('Version 9 engineering checks:',len(checks),'PASS')
    return checks

def nn_loss(logits):return torch.nn.functional.binary_cross_entropy_with_logits(logits,torch.zeros_like(logits))

if __name__=='__main__':
    result=run_selftests();Path('v9_selftest_results.json').write_text(json.dumps(result,indent=2))
