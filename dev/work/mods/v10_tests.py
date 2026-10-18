"""Bounded nonclinical checks; real R/ricu execution is explicitly separate."""
from pathlib import Path
import tempfile,json,contextlib,io
import numpy as np
import pandas as pd
import torch
from v10_features import *
from v10_protocol import config,partition,resolve_onsets
from v9_models import ExperimentModel,ObserverBank,perturb_guidance,organ_mapping

def run_checks():
    from v9_selftest import run_selftests
    checks=[{'check':k,'passed':v} for k,v in run_selftests().items()]
    def check(name,ok):
        if not bool(ok):raise AssertionError(name)
        checks.append({'check':name,'passed':True})
    d=pd.DataFrame({'Patient_ID':['a']*8,'Hour':np.arange(1,9),'HR':[70.,73,71,80,85,76,99,94],
       'SBP':[100.]*8,'DBP':[70.]*8,'MAP':[99.]*8,'Resp':[22.]*8,'Temp':[37.]*8})
    e=engineer_one(d)
    check('missing_GCS_keeps_qSOFA_total_unknown',e.qSOFA_Total.isna().all())
    check('missing_SOFA_components_unknown',e.SOFAproxy_Total.isna().all())
    check('unknown_age_not_zero',e.AgeSBP.isna().all())
    check('measured_MAP_preserved',e.MAP.eq(99).all() and e.DerivedMAP.eq(80).all())
    a=elapsed_since_event([0,1,np.nan,1,0],[1,2,4,7,9],'last')
    check('last_event_resets_real_elapsed_hours',np.allclose(a[1:],[0,2,0,2]) and np.isnan(a[0]))
    a=elapsed_since_event([0,1,np.nan,1,0],[1,2,4,7,9],'first')
    check('first_event_not_reset',np.allclose(a[1:],[0,2,5,7]))
    check('true_regression_slope_irregular_hours',np.isclose(trailing_stats([3,7,13],[1,3,6],8)[-1,0],2))
    for n in range(1,len(d)):
        prefix=engineer_one(d.iloc[:n]);mut=d.copy();mut.loc[mut.index>=n,'HR']=1e12
        m=engineer_one(mut).iloc[:n]
        for z in [e.iloc[:n],m]:
            check(f'prefix_values_{n}_{len(checks)}',np.array_equal(prefix[ENGINEERED].to_numpy(),z[ENGINEERED].to_numpy(),equal_nan=True))
            check(f'prefix_masks_{n}_{len(checks)}',prefix[[f+'_observed' for f in ENGINEERED]].equals(z[[f+'_observed' for f in ENGINEERED]]))
    z=engineer_frame(pd.concat([d.assign(Patient_ID='b',HR=200),d]))
    check('patient_keys_preserved',not z.duplicated(['Patient_ID','Hour']).any() and z.groupby('Patient_ID').HR_Slope3h.first()['b']==0)
    for bad in [d.assign(Hour=1),d.iloc[::-1]]:
        try:engineer_one(bad);raise AssertionError('accepted bad hours')
        except ValueError:check('duplicate_or_unsorted_hours_rejected',True)
    f=['HR','Creatinine','GCS','HR_observed','Creatinine_observed','GCS_observed']
    torch.manual_seed(42);bank=ObserverBank(f);x=torch.randn(2,7,len(f));x[:,:,3:]=1
    mask=torch.ones(2,7);hours=torch.arange(1,8).float().expand(2,-1)
    for arm in ['osta','observer_features','output_fusion','gated_attention','ungated_attention','cnn']:
        with contextlib.redirect_stdout(io.StringIO()):m=ExperimentModel(f,arm,bank.names,small=False,dropout=0)
        m.eval();a=m(x,mask,hours,bank(x));b=m(x[:,:4],mask[:,:4],hours[:,:4],bank(x[:,:4]))
        check(arm+'_full_size_prefix',torch.allclose(a[:,:4],b,atol=2e-5,rtol=2e-5))
        pad=torch.cat([x,torch.randn(2,3,len(f))*100],1);pm=torch.cat([mask,torch.zeros(2,3)],1);ph=torch.cat([hours,torch.zeros(2,3)],1)
        check(arm+'_padding',torch.allclose(a,m(pad,pm,ph,bank(pad))[:,:7],atol=2e-5,rtol=2e-5))
        m.train();m.zero_grad();m(x,mask,hours,bank(x)).square().mean().backward()
        check(arm+'_full_size_backward',all(torch.isfinite(p.grad).all() for p in m.parameters() if p.grad is not None))
        m.eval()
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'s.pt';torch.save(m.state_dict(),p)
            with contextlib.redirect_stdout(io.StringIO()):copy=ExperimentModel(f,arm,bank.names,small=False,dropout=0)
            copy.load_state_dict(torch.load(p,weights_only=True));copy.eval()
            check(arm+'_checkpoint_equivalence',torch.equal(m(x,mask,hours,bank(x)),copy(x,mask,hours,bank(x))))
    for c in ['missing_all','missing_half','incorrect','conflicting','stale_6h','delayed_2h']:
        z=perturb_guidance(bank(x),c);check('guidance_'+c,all(torch.isfinite(v).all() for v in z.values()))
    check('full_mode_no_smoke_epoch_or_architecture',config('full')['epochs']==30 and not config('full')['small_model'])
    check('smoke_budget',config()['epochs']==2 and len(config()['seeds'])==1)
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);batch=root/'batches/plan/000';batch.mkdir(parents=True)
        (batch/'ids.json').write_text('[1,2]');(batch/'labels_complete.json').write_text('{}')
        pd.DataFrame({'stay_id':[1],'time':[5.],'sep3_alt':[True]}).to_parquet(batch/'labels.parquet')
        summary=pd.DataFrame({'stay_id':[1,2],'first_hour':[1,1],'followup_end':[20,20],'first_positive':[1,np.nan]})
        q=resolve_onsets(root,summary)
        check('clipped_window_does_not_shift_onset',q.OnsetHour.iloc[0]==5 and q.WindowReconstructionDifference.iloc[0]==2)
    # ---- v10.2: genuine trends on fresh measurements at real measurement times ----
    g=pd.DataFrame({'Hour':[1.,2,3,4,5],'HR':[80.,80,90,90,100],'HR_age':[0.5,1.5,0.25,1.25,0.]})
    t=fresh_measurement_times(g.HR,g.Hour,g.HR_age)
    check('fresh_times_skip_carried_values',np.allclose(t,[.5,np.nan,2.75,np.nan,5.],equal_nan=True))
    st=trailing_stats(g.HR,g.Hour,6,t)
    check('fresh_slope_uses_measurement_times',np.isclose(st[-1,0],np.polyfit([.5,2.75,5],[80,90,100],1)[0]) and st[-1,3]==3)
    check('carried_values_not_double_counted',st[1,3]==1 and np.isnan(st[1,1]))
    g32=g.astype('float32')
    check('fresh_times_float32_roundtrip',np.allclose(fresh_measurement_times(g32.HR,g32.Hour,g32.HR_age),t,equal_nan=True,atol=1e-3))
    ee=engineer_one(g.assign(Patient_ID='z'))
    check('engineer_uses_age_channels',np.isclose(ee.HR_Slope6h.iloc[-1],st[-1,0]))
    vp=pd.DataFrame({'Hour':[1.,2,3,4,5,6],'VasopressorRecorded':[np.nan,0,1,np.nan,1,0]})
    ve=engineer_one(vp)
    check('vasopressor_first_vs_last',np.allclose(ve.Vasopressor_HoursSinceFirst,[np.nan,np.nan,0,1,2,3],equal_nan=True)
          and np.allclose(ve.Vasopressor_HoursSinceLast,[np.nan,np.nan,0,1,0,1],equal_nan=True))
    qq=pd.DataFrame({'Hour':[1.,2,3,4],'Resp':[25.,25,15,15],'SBP':[90.,120,120,90],'GCS':[np.nan,15,15,np.nan]})
    qe=engineer_one(qq)
    # hour1: 2 positives (GCS unknown) -> event; hour2: all known, 1 positive -> 0; hour4: 1 positive, GCS unknown -> unknown
    check('qsofa2_event_unknown_handling',np.allclose(qe.qSOFA2_HoursSinceFirst,[0,1,2,3]) and np.allclose(qe.qSOFA2_HoursSinceLast,[0,1,2,3]))
    from v9_models import organ_mapping as om
    om(list(ENGINEERED)+[f+'_observed' for f in ENGINEERED]);check('every_engineered_feature_mapped',True)
    # ---- adapter-level prefix causality: events available after t cannot alter rows <=t ----
    from v9_data import build_sequence,PRIMARY
    rng=np.random.default_rng(7);rows=[]
    for f,m,sd in [('HR',90,15),('SBP',110,20),('DBP',65,10),('MAP',80,12),('Resp',20,5),('Temp',37.5,.8),('GCS',13,2),
                   ('Creatinine',1.4,.6),('Platelets',150,60),('Bilirubin_total',1.5,1),('BUN',25,8),('WBC',11,4),('Weight',80,5),('UrineOutput',40,25)]:
        for _ in range(30):
            eh=float(rng.uniform(-3,30));rows.append({'feature':f,'value':float(max(.5,rng.normal(m,sd))),'event_hour':eh,'available_hour':eh+float(rng.choice([0,0,.4,3])),'unit':''})
    for _ in range(12):
        eh=float(rng.uniform(0,30));rows.append({'feature':'VasopressorRecorded','value':float(rng.choice([0,1])),'event_hour':eh,'available_hour':eh+.2,'unit':''})
    ev=pd.DataFrame(rows);meta={'followup_end':30.,'OnsetHour':np.nan,'Age':70.,'Gender':0.}
    full=build_sequence(ev,meta,30,6);cols=[c for c in full if c not in ['Eligible','SepsisLabel']]
    for cut in [3.,8.,15.,22.]:
        pre=build_sequence(ev[ev.available_hour<=cut],meta,30,6)
        a=full.loc[full.Hour<=cut,cols].reset_index(drop=True);b=pre.loc[pre.Hour<=cut,cols].reset_index(drop=True)
        check(f'adapter_prefix_values_and_masks_t{int(cut)}',np.array_equal(a.to_numpy(float),b.to_numpy(float),equal_nan=True))
    check('postoperative_not_a_predictor','PostoperativeAdmission' not in full)
    check('weight_known_beyond_24h',full.Weight.notna().iloc[-1] or full.Weight_age.iloc[-1]<=54)
    # ---- shard-level resume: an interrupted build reuses completed batches exactly ----
    import duckdb,shutil
    from v9_data import build_shards
    with tempfile.TemporaryDirectory() as td:
        td=Path(td);stage=td/'stage';stage.mkdir();cohort=td/'cohort';cohort.mkdir()
        ids=list(range(1,7))
        pd.DataFrame({'stay_id':ids,'person':[f'p{i}' for i in ids],'hospital':'h','first_hour':0.,'followup_end':30.,
                      'first_positive':np.nan,'OnsetHour':[np.nan,20.,np.nan,15.,np.nan,np.nan],'Outcome':0}).to_parquet(stage/'metadata.parquet')
        pd.DataFrame({'stay_id':ids,'age':60.,'sex':'Female'}).to_parquet(cohort/'sta.parquet')
        pd.DataFrame(columns=['stay_id']).to_parquet(stage/'phenotypes.parquet')
        evs=pd.concat([ev.assign(stay_id=i,kind='state',end_hour=np.nan) for i in ids],ignore_index=True)
        evs.to_parquet(stage/'events.parquet')
        ix1,s1=build_shards('miiv',stage,cohort,td/'a',30,6,batch=2)
        first=sorted((td/'a/parts').glob('*.done.json'))[0];shutil.copytree(td/'a',td/'b')
        for p in sorted((td/'b/parts').glob('*.done.json'))[1:]:p.unlink()
        ix2,s2=build_shards('miiv',stage,cohort,td/'b',30,6,batch=2)
        check('shard_resume_identical_index',ix1.drop(columns='file').equals(ix2.drop(columns='file')) and s1==s2)
        check('shard_resume_identical_values',pd.read_parquet(sorted((td/'a').glob('miiv_*.parquet'))[-1]).equals(pd.read_parquet(sorted((td/'b').glob('miiv_*.parquet'))[-1])))
    # ---- release preflight: demo/partial copies stop before any import ----
    from v10_preflight import check_release,ricu_status
    def raises(f):
        try:f();return False
        except ValueError:return True
    check('mimic_demo_140_stays_refused',raises(lambda:check_release({'miiv':140,'eicu':200859},{})))
    check('eicu_demo_refused',raises(lambda:check_release({'miiv':73181,'eicu':2520},{})))
    check('partial_copy_refused',raises(lambda:check_release({'miiv':5000,'eicu':200859},{})))
    check('full_releases_accepted',len(check_release({'miiv':94458,'eicu':200859},{}))==2)
    check('demo_allowed_only_in_smoke',not raises(lambda:check_release({'miiv':140,'eicu':200859},{},True,'smoke')) and raises(lambda:check_release({'miiv':140,'eicu':200859},{},True,'full')))
    with tempfile.TemporaryDirectory() as td:
        r=Path(td);(r/'chartevents').mkdir();(r/'patients.fst').write_text('x');(r/'chartevents/1.fst').write_text('x');(r/'chartevents/2.fst').write_text('x')
        st=ricu_status('miiv',r,r/'proj')
        check('ricu_import_status_counts_tables',st['fst_files']==3 and st['tables_with_fst']==2)
    # ---- per-file audit: demo files mixed into a full folder are refused (sizes only) ----
    from v10_preflight import check_files,FULL_MIN_BYTES
    def fake_release(root,ds,small=()):
        for stem,mn in FULL_MIN_BYTES[ds].items():
            f=Path(root)/(stem+'.csv.gz');f.parent.mkdir(parents=True,exist_ok=True)
            with open(f,'wb') as h:h.truncate(5000 if stem in small else mn+1)   # sparse: no disk use
    with tempfile.TemporaryDirectory() as td:
        full=Path(td)/'full';mixed=Path(td)/'mixed';demo=Path(td)/'demo'
        fake_release(full,'miiv');fake_release(mixed,'miiv',('icu/icustays','icu/chartevents','hosp/patients','hosp/admissions'))
        fake_release(demo,'miiv',tuple(FULL_MIN_BYTES['miiv']))
        check('full_release_files_accepted',all(r['status']=='ok' for r in check_files({'miiv':full})))
        try:check_files({'miiv':mixed},True,'smoke');ok=False
        except ValueError as e:ok='MIXED' in str(e) and 'icustays' in str(e) and 'chartevents' in str(e)
        check('mixed_demo_full_folder_refused_even_with_demo_allowed',ok)
        check('pure_demo_files_allowed_only_in_smoke',not raises(lambda:check_files({'miiv':demo},True,'smoke')) and raises(lambda:check_files({'miiv':demo},False,'smoke')))
    # ---- PhysioNet repair against a local mock server (auth, resume, checksum, quarantine) ----
    import threading,hashlib,base64,http.server,os
    from v10_preflight import repair_from_physionet,table_sizes
    with tempfile.TemporaryDirectory() as td:
        srv=Path(td)/'srv';sums={}
        for stem,mn in FULL_MIN_BYTES['miiv'].items():
            data=(b'0123456789'*(mn//10+1)) if stem=='icu/icustays' else b'x'
            f=srv/(stem+'.csv.gz');f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data);sums[stem]=hashlib.sha256(data).hexdigest()
        (srv/'SHA256SUMS.txt').write_text(''.join(f'{h}  {k}.csv.gz\n' for k,h in sums.items()))
        cut={'once':True}
        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_GET(self):
                if self.headers.get('Authorization')!='Basic '+base64.b64encode(b'u:p').decode():self.send_response(401);self.end_headers();return
                data=(srv/self.path.split('/files/x/')[-1]).read_bytes();rng=self.headers.get('Range');start=int(rng.split('=')[1].rstrip('-')) if rng else 0
                body=data[start:];send=body
                if cut['once'] and self.path.endswith('icustays.csv.gz') and not rng:send=body[:len(body)//2];cut['once']=False
                self.send_response(206 if rng else 200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(send);self.close_connection=True
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),H);threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}/files/x/';root=Path(td)/'mimic'
        fake_release(root,'miiv',('icu/icustays',))
        try:repair_from_physionet('miiv',root,'u','p',base=base,log=lambda *a:None);first=False
        except OSError:first=True
        acts=repair_from_physionet('miiv',root,'u','p',base=base,log=lambda *a:None)
        server.shutdown()
        check('physionet_repair_resumes_and_verifies',first and len(acts)==1 and hashlib.sha256((root/'icu/icustays.csv.gz').read_bytes()).hexdigest()==sums['icu/icustays']
              and all(r['status']=='ok' for r in table_sizes('miiv',root)) and (root/'_quarantined_demo_files/icu/icustays.csv.gz').is_file())
    from v11_tests import run_v11_checks
    checks+=[{'check':'v11_'+k,'passed':v} for k,v in run_v11_checks().items()]
    print('V10 engineering checks:',len(checks),'PASS')
    return checks
