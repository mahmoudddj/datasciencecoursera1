"""Nonclinical engineering fixtures only; never used for study training/results."""
from pathlib import Path
import tempfile,json,contextlib,io
import numpy as np
import pandas as pd
import torch
import duckdb
from v9_data import latest_known,urine_features,text_flags,specimen_site,RawExtractor,normalize_events,build_sequence,PRIMARY,csv_scan
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
    check('urine_rate_requires_complete_window',np.isnan(u['Urine_mlkg_h_6h'][4]) and np.isclose(u['Urine_mlkg_h_6h'][5],300/420))
    zero=urine.copy();zero['value']=0.;missing=urine.iloc[:0]
    check('missing_urine_not_observed_zero',np.isnan(urine_features(missing,np.array([6.]),np.array([70.]))['UrineOutput'][0]) and urine_features(zero,np.array([6.]),np.array([70.]))['UrineOutput'][0]==0)
    check('AKI_not_trauma',text_flags('Acute kidney injury')['Phenotype_trauma']==0)
    check('nontraumatic_not_trauma',text_flags('Nontraumatic subarachnoid hemorrhage')['Phenotype_trauma']==0)
    check('negation_not_postoperative',text_flags('No surgical procedure performed')['Phenotype_postoperative']==0)
    check('true_trauma_retained',text_flags('Traumatic brain injury')['Phenotype_trauma']==1)
    check('urinary_site_over_collection_device',specimen_site('Urine, Catheter')=='urine')
    check('pneumonia_source',specimen_site('pneumonia')=='respiratory')
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

        pd.DataFrame({'patientunitstayid':[1],'uniquepid':['p1'],'hospitalid':[1],'unitadmitsource':['Emergency Department'],'apacheadmissiondx':['Acute kidney injury']}).to_csv(root/'patient.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1,1],'infusionoffset':[60,120],'drugname':['Norepinephrine (mcg/min)']*2,'drugrate':['4','0'],'infusionrate':['4','0'],'patientweight':['70','70']}).to_csv(root/'infusionDrug.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1],'intakeoutputoffset':[60],'intakeoutputentryoffset':[180],'cellpath':['flowsheet|I&O|Output (ml)|Urine'],'celllabel':['Foley urine'],'cellvaluenumeric':[50]}).to_csv(root/'intakeOutput.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1],'labresultoffset':[60],'labresultrevisedoffset':[180],'labname':['creatinine'],'labresult':['2'],'labmeasurenamesystem':['mg/dL']}).to_csv(root/'lab.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1],'observationoffset':[60],'heartrate':['80']}).to_csv(root/'vitalPeriodic.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1],'nursingchartoffset':[60],'nursingchartentryoffset':[180],'nursingchartcelltypevalname':['GCS Total'],'nursingchartvalue':['12']}).to_csv(root/'nurseCharting.csv',index=False)
        pd.DataFrame({'patientunitstayid':[1],'respchartoffset':[60],'respchartentryoffset':[120],'respchartvaluelabel':['FiO2'],'respchartvalue':['40%']}).to_csv(root/'respiratoryCharting.csv',index=False)
        ex=RawExtractor('eicu',root,selected,td/'eicu_stage',12);paths=ex.extract()
        support=pd.read_parquet(td/'eicu_stage/support.parquet')
        check('zero_rate_not_active',support.sort_values('event_hour').value.tolist()==[1.,0.])
        raw=pd.read_parquet(td/'eicu_stage/urine.parquet');check('eicu_entry_time_used',raw.available_hour.iloc[0]==3)
        all_ev=normalize_events(pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True))
        seq=build_sequence(all_ev,{**selected.iloc[0].to_dict(),'Age':60.,'Gender':1.},12,6)
        check('delayed_GCS_not_visible_early',seq.GCS.iloc[:2].isna().all() and seq.GCS.iloc[2]==12)
        check('strict_urine_availability',np.isnan(seq.UrineOutput.iloc[0]) and seq.UrineOutput_6h.iloc[2]==50)
        check('unknown_weight_no_oliguria',seq.Oliguria6h.isna().all())
        root=td/'miiv';(root/'icu').mkdir(parents=True);(root/'hosp').mkdir()
        pd.DataFrame({'stay_id':[1],'hadm_id':[10],'subject_id':[100],'intime':['2100-01-01 00:00:00'],'outtime':['2100-01-02 00:00:00']}).to_csv(root/'icu/icustays.csv',index=False)
        pd.DataFrame({'stay_id':[1],'itemid':[220045],'charttime':['2100-01-01 01:00:00'],'storetime':['2100-01-01 03:00:00'],'valuenum':[100.],'value':['100'],'valueuom':['bpm']}).to_csv(root/'icu/chartevents.csv',index=False)
        pd.DataFrame({'hadm_id':[10],'itemid':[50912],'charttime':['2100-01-01 01:00:00'],'storetime':['2100-01-01 04:00:00'],'valuenum':[2.],'valueuom':['mg/dL']}).to_csv(root/'hosp/labevents.csv',index=False)
        pd.DataFrame({'stay_id':[1,1],'itemid':[227488,227489],'charttime':['2100-01-01 01:00:00']*2,'storetime':['2100-01-01 02:00:00']*2,'value':[100.,150.],'valueuom':['mL']*2}).to_csv(root/'icu/outputevents.csv',index=False)
        pd.DataFrame({'stay_id':[1],'itemid':[221906],'starttime':['2100-01-01 01:00:00'],'storetime':['2100-01-01 02:00:00'],'rate':[0.],'statusdescription':['FinishedRunning']}).to_csv(root/'icu/inputevents.csv',index=False)
        ex=RawExtractor('miiv',root,selected,td/'miiv_stage',12);paths=ex.extract()
        raw=pd.read_parquet(td/'miiv_stage/chartevents.parquet');check('mimic_store_time_used',raw.available_hour.iloc[0]==3)
        raw=pd.read_parquet(td/'miiv_stage/urine.parquet');check('irrigant_subtracted',raw.value.sum()==50.)

    meta={'followup_end':24.,'OnsetHour':10.,'Age':60.,'Gender':1.}
    seq=build_sequence(all_ev,meta,12,6)
    check('post_onset_rows_excluded',seq.Hour.max()==9)
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
