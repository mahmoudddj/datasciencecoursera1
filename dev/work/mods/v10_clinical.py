"""Full restricted hourly target trajectories for frozen legacy inference."""
from pathlib import Path
import json,os
import pandas as pd
import numpy as np
import duckdb
from v9_data import RawExtractor,cohort_index,build_sequence,normalize_events,table,csv_scan,q,signature
from v9_train import atomic_json
from v10_protocol import protected_group


def stay_context(ds,raw_root,stay_ids):
    """ICU discharge follow-up and PhysioNet-style HospAdmTime (hours from hospital admission
    to ICU admission, negative), both known at ICU admission. Never derived from outcomes."""
    con=duckdb.connect();con.execute("SET memory_limit='1GB'");con.execute('SET threads=1')
    con.register('chosen',pd.DataFrame({'stay_id':list(stay_ids)}))
    try:
        if ds=='miiv':
            icu=csv_scan(table(raw_root,'icu/icustays',True));adm=table(raw_root,'hosp/admissions')
            hadm=(f"LEFT JOIN {csv_scan(adm)} a ON TRY_CAST(a.hadm_id AS BIGINT)=TRY_CAST(x.hadm_id AS BIGINT)" if adm else '')
            hat=("epoch(TRY_CAST(a.admittime AS TIMESTAMP)-TRY_CAST(x.intime AS TIMESTAMP))/3600." if adm else 'CAST(NULL AS DOUBLE)')
            z=con.execute(f"""SELECT CAST(x.stay_id AS BIGINT) stay_id,CAST(x.subject_id AS VARCHAR) person,
                epoch(TRY_CAST(x.outtime AS TIMESTAMP)-TRY_CAST(x.intime AS TIMESTAMP))/3600. followup,{hat} HospAdmTime
                FROM {icu} x {hadm} JOIN chosen c ON TRY_CAST(x.stay_id AS BIGINT)=c.stay_id""").df()
        else:
            p=table(raw_root,'patient',True)
            z=con.execute(f"""SELECT CAST(patientunitstayid AS BIGINT) stay_id,CAST(uniquepid AS VARCHAR) person,
                TRY_CAST(unitdischargeoffset AS DOUBLE)/60. followup,TRY_CAST(hospitaladmitoffset AS DOUBLE)/60. HospAdmTime
                FROM {csv_scan(p)} x JOIN chosen c ON TRY_CAST(x.patientunitstayid AS BIGINT)=c.stay_id""").df()
    finally:con.close()
    if z.stay_id.duplicated().any():raise ValueError('Duplicate stay context rows')
    return z

def legacy_target(ds,raw_root,cohort_folder,out,max_hours=120,mode='smoke',release_final=False,reuse_stage=None):
    if release_final and mode!='full':raise ValueError('Final labels/metrics cannot be released in smoke')
    out=Path(out);out.mkdir(parents=True,exist_ok=True);stage=out/'raw_stage'
    if (out/'complete.json').exists():return pd.read_parquet(out/'index.parquet')
    selected=cohort_index(cohort_folder,None,42)
    # Follow-up uses actual source ICU discharge rather than YAIB's onset+6 stop.
    z=stay_context(ds,raw_root,selected.stay_id)
    selected=selected.merge(z,on='stay_id',validate='one_to_one')
    reserve=(ds+'|'+selected.person).map(protected_group)
    selected=selected[reserve if release_final else ~reserve].copy()
    selected['followup_end']=selected.followup;selected=selected.drop(columns=['followup','person'])
    # Clipped earliest positive cannot be mapped back by the official scorer. Preserve
    # exclusions explicitly instead of shifting labels and reporting false lead times.
    excluded=selected[selected.OnsetHour.notna()&selected.OnsetHour.lt(7)]
    excluded.to_parquet(out/'excluded_clipped_onsets.parquet',index=False)
    selected=selected[~selected.stay_id.isin(excluded.stay_id)]
    if selected.empty:raise ValueError('No target stays after protected split and onset checks')
    # Reuse a compatible raw-table stage (same raw_stage_key, a superset of these stays)
    # instead of rescanning the raw tables.
    if reuse_stage and (Path(reuse_stage)/'raw_complete.json').is_file() and set(selected.stay_id)<=set(pd.read_parquet(Path(reuse_stage)/'metadata.parquet').stay_id):
        stage=Path(reuse_stage);reused=True
    else:
        reused=False
        if not (stage/'raw_complete.json').is_file():
            RawExtractor(ds,raw_root,selected,stage,max_hours).extract();atomic_json(stage/'raw_complete.json',{'stays':len(selected)})
    paths=[p for p in stage.glob('*.parquet') if p.stem not in ['metadata','phenotypes','phenotype_evidence','specimen_context','clinician_source_context','treatment_context']]
    meta=pd.read_parquet(stage/'metadata.parquet')[['stay_id','person','hospital']]
    meta=meta.merge(selected,on='stay_id',validate='one_to_one')
    static=pd.read_parquet(Path(cohort_folder)/'sta.parquet')
    static=static[['stay_id']+[c for c in ['age','sex'] if c in static]].drop_duplicates('stay_id').rename(columns={'age':'Age'})
    if 'sex' in static:
        static['Gender']=static.sex.astype(str).str.lower().map({'male':1.,'m':1.,'1':1.,'1.0':1.,'true':1.,'female':0.,'f':0.,'0':0.,'0.0':0.,'false':0.})
        static=static.drop(columns='sex')
    meta=meta.merge(static,on='stay_id',how='left',validate='one_to_one')
    con=duckdb.connect();con.execute("SET memory_limit='1GB'");con.execute('SET threads=1')
    index=[];shard=out/'shards';shard.mkdir(exist_ok=True)
    rel='read_parquet(['+','.join(q(p) for p in paths)+'],union_by_name=true)'
    for start in range(0,len(meta),16):
        chunk=meta.iloc[start:start+16];p=shard/f'{start//16:06d}.parquet';done=shard/f'{start//16:06d}.done.json'
        contract=[int(x) for x in chunk.stay_id]
        if done.is_file() and json.loads(done.read_text())['stays']==contract:
            index.extend(json.loads(done.read_text())['index']);continue
        con.register('ids',chunk[['stay_id']])
        events=normalize_events(con.execute(f'SELECT e.* FROM {rel} e JOIN ids USING(stay_id)').df());parts=[];offset=0;rows=[]
        for r in chunk.to_dict('records'):
            # Temporarily omit onset only to request full feature histories. True onset
            # remains metadata and determines StepLabel; never substitute incident y.
            d=build_sequence(events[events.stay_id.eq(r['stay_id'])],{**r,'OnsetHour':np.nan},max_hours,6)
            if d.empty:continue
            d=d.drop(columns=['Eligible','SepsisLabel'])
            # PhysioNet step label: 1 from (onset - 6 h) onward; applied once only.
            d['StepLabel']=((d.Hour>=r['OnsetHour']-6)&pd.notna(r['OnsetHour'])).astype(int)
            d['HospAdmTime']=float(r['HospAdmTime']) if pd.notna(r.get('HospAdmTime')) else np.nan
            pid=ds+'|'+str(r['stay_id']);d.insert(0,'Patient_ID',pid);parts.append(d)
            rows.append({'Patient_ID':pid,'Group_ID':ds+'|'+str(r['person']),'Hospital_ID':str(r['hospital']),'Dataset':ds,
                         'OnsetHour':None if pd.isna(r['OnsetHour']) else float(r['OnsetHour']),'file':str(p),'offset':offset,'length':len(d)})
            offset+=len(d)
        if parts:
            tmp=p.with_suffix('.partial.parquet');pd.concat(parts,ignore_index=True).to_parquet(tmp,index=False);os.replace(tmp,p)
        tmp=done.with_suffix('.partial');tmp.write_text(json.dumps({'stays':contract,'index':rows}));os.replace(tmp,done)
        index.extend(rows)
    con.close();ix=pd.DataFrame(index);ix['OnsetHour']=ix.OnsetHour.astype(float);ix.to_parquet(out/'index.parquet',index=False)
    atomic_json(out/'complete.json',{'scope':'YAIB-selected ICU stays, full hourly source followup capped at '+str(max_hours),'stays':len(ix),
        'excluded_clipped':len(excluded),'mode':mode,'release_final':release_final,'reused_raw_stage':str(stage) if reused else None})
    return ix
