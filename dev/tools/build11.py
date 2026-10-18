"""Build Sepsis_V11_Improved_MIMIC_eICU_11_architectures.ipynb from the _10 notebook.
Embeds the v11 modules and the changed v9/v10 modules; the pinned worker and preflight stay as
embedded in _4.._10 (their keys must not move)."""
import json,gzip,base64,hashlib,io,ast,sys
from pathlib import Path
R=Path('/home/user/datasciencecoursera1');M=R/'dev/work/mods';C=R/'dev/work/cells'
nb=json.load(open(R/'Sepsis_V11_Improved_MIMIC_eICU_10_all_predictors.ipynb'));cells=nb['cells']
def src(i):return ''.join(cells[i]['source'])
def setsrc(i,s):cells[i]['source']=s
def rep(s,a,b):
    assert s.count(a)==1,a[:70];return s.replace(a,b)
def embed(raw):
    buf=io.BytesIO()
    with gzip.GzipFile(fileobj=buf,mode='wb',mtime=0,filename='') as g:g.write(raw)
    return {'sha256':hashlib.sha256(raw).hexdigest(),'data':base64.b64encode(buf.getvalue()).decode()}
# --- cell 3: embedded modules + imports ---
s3=src(3).splitlines();k=[i for i,l in enumerate(s3) if l.startswith('EMBEDDED_MODULES = ')][0]
emb=ast.literal_eval(s3[k][len('EMBEDDED_MODULES = '):])
for n in ['feature_specs.json','v10_features.py','v9_data.py','v9_models.py','v9_selftest.py','v9_train.py','v10_train.py','v10_evaluation.py','v10_protocol.py','v10_fixture.py',
          'v11_data.py','v11_models.py','v11_train.py','v11_tests.py']:
    emb[n]=embed((M/n).read_bytes())
# v10_tests: the copy embedded so far plus the v11 hook (the repo copy also carries a preflight test tied to another module version).
t=gzip.decompress(base64.b64decode(emb['v10_tests.py']['data'])).decode()
t=rep(t,"    print('V10 engineering checks:',len(checks),'PASS')\n    return checks",
        "    from v11_tests import run_v11_checks\n    checks+=[{'check':'v11_'+k,'passed':v} for k,v in run_v11_checks().items()]\n    print('V10 engineering checks:',len(checks),'PASS')\n    return checks")
emb['v10_tests.py']=embed(t.encode())
s3[k]='EMBEDDED_MODULES = '+repr(emb);txt='\n'.join(s3)
txt=rep(txt,',AIRWAY,COMORBID,EXPOSURES,ADMISSION,STATES',',AIRWAY,COMORBID,EXPOSURES,ADMISSION,STATES,PROPHYLAXIS')
txt=rep(txt,"from v10_train import run_fold","from v10_train import run_fold\nfrom v11_data import SupplementExtractor,unlabelled_stays\nfrom v11_train import run_fold_v11,PROXY_FEATURES")
setsrc(3,txt)
# --- cell 2: configuration ---
c=src(2)
c=rep(c,"FULL_SEEDS = [42]                          # 1 seed: validation of V10.5 on the 10k samples. FULL COHORT: FULL_SAMPLE_STAYS_PER_DATASET=None and FULL_SEEDS=[42,7,123]",
        "FULL_SEEDS = [42]                          # 1 seed on the 10k samples (shortlist rule); FULL COHORT: FULL_SAMPLE_STAYS_PER_DATASET=None and FULL_SEEDS=[42,7,123]")
a=c.index("TRAIN_LOSS = ");b=c.index("TABULAR_MAX_GB")
c=c[:a]+"# Loss and arms are set in the V11 block below (the original OSTA loss was retired after _9/_10; 'osta_original' remains selectable in v9_train).\n"+c[b:]
a=c.index("STUDY_STAGE = (");b=c.index("DATA_SOURCE = ")
c=c[:a]+"""STUDY_STAGE = ('V11 ARCHITECTURE AND LOSS COMPARISON on the same prespecified 10,000-stay samples, 1 seed, V10.5 features + prophylaxis. '
    'Arms: OSTA, output fusion, CNN-Transformer, logistic, boosted trees (grouped early stopping), signature boosted trees (PhysioNet 2019 '
    'winner method), flat OSTA (organ ablation), GRU-D, causal TCN, CNN->OSTA, event attention, self-supervised CNN->OSTA / flat head '
    '(site and pooled unlabelled corpora), hazard head; mean ensemble. Losses: utility-weighted BCE (primary), BCE, temporal label '
    'smoothing; selection by validation utility+AUPRC rank-average. Transfer to the other database\\'s development patients, conformal '
    'policy, lead time versus first antibiotic. Final holdout sealed; not for model selection.')
"""+c[b:]
c=rep(c,"RUN_FULL_LABEL_BASELINE = True","RUN_FULL_LABEL_BASELINE = False          # dropped in V11 (never changed results in _8/_9)")
c=rep(c,"RUN_RAW_TABULAR_CONTROL = True           # raw-vs-engineered control also for logistic/boosted trees",
        "RUN_RAW_TABULAR_CONTROL = True           # raw-vs-engineered control also for logistic/boosted trees\n"+(C/'v11_config_block.py').read_text().rstrip('\n'))
c=rep(c,"""    'No result with RELEASE_FINAL_HOLDOUT=True has ever been produced or viewed.')""",
"""    'Results of _9 (run f842f399b7a05bce) and its training histories were viewed on 19 Oct 2026; the V11 arms, losses, protocol changes, '
    'selection rules and the retirement of the original OSTA loss were then fixed in writing before any V11 result existed. '
    'No result with RELEASE_FINAL_HOLDOUT=True has ever been produced or viewed.')""")
setsrc(2,c)
# --- cells 14..20 ---
assert src(14).startswith("if DATA_SOURCE=='clinical':\n    # Raw-table event stage");setsrc(14,(C/'main_12_v11.py').read_text().rstrip('\n'))
assert src(15).startswith('# Feature registry');setsrc(15,(C/'main_13.py').read_text().rstrip('\n'))
assert src(16).startswith('# 6. Resolve');setsrc(16,(C/'main_14_v11.py').read_text().rstrip('\n'))
assert src(17).startswith('# 7. Matched');setsrc(17,(C/'main_15_v11.py').read_text().rstrip('\n'))
assert src(18).startswith('# 7b. Team summary');setsrc(18,(C/'team_summary_v11.py').read_text().rstrip('\n'))
assert src(20).startswith('# Concise summary');setsrc(20,(C/'main_17_v11.py').read_text().rstrip('\n'))
# new SSL corpus cell after the registry cell
new={'cell_type':'code','execution_count':None,'id':'c011ssl','metadata':{},'outputs':[],'source':(C/'ssl_corpus_v11.py').read_text().rstrip('\n')}
cells.insert(16,new)
# markdown
setsrc(0,(C/'v11_intro.md').read_text().rstrip('\n'))
setsrc(1,(C/'v11_changes.md').read_text().rstrip('\n')+'\n\n---\n### Earlier history (V10.5, V10.3 and V10.2 changes, kept for the audit trail)\n\n'+src(1).split('\n',1)[1])
m=src(20);m=rep(m,'## 8. Results and completion','## 8. Results and completion\nRows: internal development test per database (`condition=normal`), the conformal secondary policy, the trajectory-rich subset, and transfer rows (`<other>_from_<target>`: a model of one database scored on the other database\'s development patients with the first database\'s calibration). Loss comparators are named `<arm>@<loss>`. Prespecified rules (loss, organ structure, shortlist) are printed from validation numbers in 7b.');setsrc(20,m)
for cl in cells:
    if cl['cell_type']=='code':ast.parse(''.join(cl['source']));cl['outputs']=[];cl['execution_count']=None
nb['metadata']['sepsis_validation']={'status':'fixture run before release'}
out=R/'Sepsis_V11_Improved_MIMIC_eICU_11_architectures.ipynb'
out.write_text(json.dumps(nb,indent=1,ensure_ascii=False));print('written',out.stat().st_size//1024,'KB','cells',len(cells))
