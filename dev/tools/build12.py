"""Build Sepsis_V11_Improved_MIMIC_eICU_12_stage1b.ipynb from the _11 notebook (protocol section 10b).
Re-embeds only the three changed v11 modules (models, train, tests); v9/v10 modules, the worker and the
preflight stay exactly as embedded in _11, so DATA_KEY / RAW_STAGE_KEY / cohort keys do not move."""
import json,gzip,base64,hashlib,io,ast
from pathlib import Path
R=Path('/home/user/datasciencecoursera1');M=R/'dev/work/mods';C=R/'dev/work/cells'
nb=json.load(open(R/'Sepsis_V11_Improved_MIMIC_eICU_11_architectures.ipynb'));cells=nb['cells']
def src(i):return ''.join(cells[i]['source'])
def setsrc(i,s):cells[i]['source']=s
def rep(s,a,b):
    assert s.count(a)==1,a[:70];return s.replace(a,b)
def embed(raw):
    buf=io.BytesIO()
    with gzip.GzipFile(fileobj=buf,mode='wb',mtime=0,filename='') as g:g.write(raw)
    return {'sha256':hashlib.sha256(raw).hexdigest(),'data':base64.b64encode(buf.getvalue()).decode()}
# --- cell 3: embedded modules ---
s3=src(3).splitlines();k=[i for i,l in enumerate(s3) if l.startswith('EMBEDDED_MODULES = ')][0]
emb=ast.literal_eval(s3[k][len('EMBEDDED_MODULES = '):])
for n in ['v11_models.py','v11_train.py','v11_tests.py','v9_locate_raw.py']:emb[n]=embed((M/n).read_bytes())   # locator: unreadable Drive shortcuts are skipped, not fatal
s3[k]='EMBEDDED_MODULES = '+repr(emb);setsrc(3,'\n'.join(s3))
# --- cell 2: configuration ---
c=src(2)
c=rep(c,"RUN_NO_PROXY_SENSITIVITY = True                    # osta without hydrocortisone / imaging / prophylaxis (clinician-suspicion proxies)",
        "RUN_NO_PROXY_SENSITIVITY = True                    # osta without hydrocortisone / imaging / prophylaxis (clinician-suspicion proxies)\n"
        +(C/'v11_config_block.py').read_text().split('# ---- STAGE 1b')[1].join(['# ---- STAGE 1b','']).rstrip('\n'))
a=c.index("STUDY_STAGE = (");b=c.index("DATA_SOURCE = ")
c=c[:a]+"""STUDY_STAGE = ('STAGE 1b (protocol section 10b, 24 Oct 2026) on the same prespecified 10,000-stay samples, 1 seed: flat OSTA vs flat OSTA '
    'with seven organ heads (uncertainty-weighted), input dropout 0/0.1/0.2, plain BCE. The quantile operating point and the alarm policy '
    '(persistence 1/2 h, all/fresh hours) are evaluated on the VALIDATION split only. Rules 10b.2.1-4 decide the stage-2 model, '
    'operating point and policy. Test-split rows are written to test_rows_sealed.json and never printed; no transfer, conformal or '
    'ensemble rows; the sealed holdout is untouched.')
"""+c[b:]
c=rep(c,"""    'No result with RELEASE_FINAL_HOLDOUT=True has ever been produced or viewed.')""",
"""    'Development TEST-split results of run 4cd752bef2ccbd42 (_11, both databases) were viewed on 19-22 Oct 2026. Stage 1b (protocol 10b) was '
    'written after that and before any stage-1b code ran: it is blind to the test splits (validation only) but not to stage 1. '
    'No result with RELEASE_FINAL_HOLDOUT=True has ever been produced or viewed.')""")
setsrc(2,c)
# --- cells 16..21 ---
assert src(16).startswith('# 5c. Unlabelled corpus');setsrc(16,(C/'ssl_corpus_v11.py').read_text().rstrip('\n'))
assert src(17).startswith('# 6. Resolve');setsrc(17,(C/'main_14_v11.py').read_text().rstrip('\n'))
assert src(18).startswith('# 7. V11 matched');setsrc(18,(C/'main_15_v11.py').read_text().rstrip('\n'))
assert src(19).startswith('# 7b. Team summary')
t7b=(C/'team_summary_v11.py').read_text().rstrip('\n').splitlines()
setsrc(19,'# 7b. Team summary (stage 1 layout; skipped in stage 1b, see 7a).\nif not STAGE_1B:\n'+'\n'.join('    '+l for l in t7b))
cells.insert(19,{'cell_type':'code','execution_count':None,'id':'c019s1b','metadata':{},'outputs':[],'source':(C/'team_summary_stage1b.py').read_text().rstrip('\n')})
assert src(22).startswith('# Concise summary');setsrc(22,(C/'main_17_v11.py').read_text().rstrip('\n'))
# --- markdown ---
setsrc(0,src(0).replace('notebook `_11`','notebook `_12_stage1b`',1))
setsrc(1,"""## Stage 1b (this `_12_stage1b`, 24 Oct 2026; protocol section 10b)

Decided after the stage-1 development results of run `4cd752bef2ccbd42` had been seen, before any stage-1b code ran; blind to the test splits.

| Item | What this notebook does |
|---|---|
| Arms | `flat_osta` (reference) and `flat_osta_heads` (same flat backbone + seven organ heads at the output: six SOFA organs and any-organ, each predicting a component rise within 6/12/24 h; losses combined by learned uncertainty weighting, Kendall et al. 2018) |
| Input dropout | 0, 0.1, 0.2 (a predictor's value, flag and age hidden together, training only): six trainings per database |
| Loss | plain BCE for every training (the stage-2 loss by the section 10 rule) |
| Operating point | absolute (V11) vs quantile: the calibration-split alarm fraction carried to the scored population as a quantile of its own scores (label-free; needs 10,000 scored hours, else absolute) |
| Alarm policy | persistence 1 vs 2 h; cooldown 6 h kept; all hours vs fresh-information hours only; false alarms always counted over every hour |
| What is reported | the VALIDATION grid (7a) and rules 10b.2.1-4. Test-split rows are computed, written to `test_rows_sealed.json` and never printed. No transfer, conformal, trajectory-rich or ensemble rows. No self-supervised corpus. The sealed holdout is untouched |
| Reuse | labels, raw scans, supplementary stage and features are reused unchanged (v9/v10 modules identical to `_11`); only training runs |

---
"""+src(1))
for cl in cells:
    if cl['cell_type']=='code':ast.parse(''.join(cl['source']));cl['outputs']=[];cl['execution_count']=None
nb['metadata']['sepsis_validation']={'status':'fixture run before release'}
out=R/'Sepsis_V11_Improved_MIMIC_eICU_12_stage1b.ipynb'
out.write_text(json.dumps(nb,indent=1,ensure_ascii=False));print('written',out.stat().st_size//1024,'KB','cells',len(cells))
