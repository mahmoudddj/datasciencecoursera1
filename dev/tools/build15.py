"""Build Sepsis_V11_Improved_MIMIC_eICU_15_pathophysiology_full.ipynb from the _14 notebook (protocol 10c.1, full-release
repeat; section 11 step 1). Data stages of _14 are reused unchanged (same keys, nothing trained); the training and summary
cells are replaced by the descriptive study cells of dev/work/cells/pathophys_15.py."""
import json,ast
from pathlib import Path
R=Path('/home/user/datasciencecoursera1');C=R/'dev/work/cells'
nb=json.load(open(R/'Sepsis_V11_Improved_MIMIC_eICU_14_stage2.ipynb'));cells=nb['cells']
def src(i):return ''.join(cells[i]['source'])
def rep(s,a,b):
    assert s.count(a)==1,a[:70];return s.replace(a,b)
c=src(2)
a=c.index("STUDY_STAGE = (");b=c.index("DATA_SOURCE = ")
c=c[:a]+"""STUDY_STAGE = ('PATHOPHYSIOLOGY STUDY, FULL-RELEASE REPEAT (protocol section 10c.1; section 11 step 1, before the freeze): the descriptive study of '
    'incident (ICU-acquired) sepsis, septic-on-arrival and early-ICU-onset stays and matched controls on the all-comers full-release data build, '
    'training-split and non-cohort patients only. Fixes the shared physiology set of item 2(b) and decides the contingent deterioration target '
    'of item 11 by the rules of 10c.1. No model is trained; no validation, calibration, test or holdout patient is read.')
"""+c[b:]
c=rep(c,"STAGE2_ARMS = ['project','two_channel','pooled','suspicion','pretrained','predictor_sets','label_stratified','benchmarks','exploratory']",
        "STAGE2_ARMS = []                                   # this notebook trains nothing (the list is unused here)")
cells[2]['source']=c
assert src(16).startswith('# 5c. Unlabelled corpus') and src(17).startswith('# 6-7. Stage 2')
keep=cells[:17]
parts=(C/'pathophys_15.py').read_text().split('# %% ')
new=[]
for p in parts[1:]:
    kind,body=p.split('\n',1);body=body.rstrip('\n')
    if kind.strip()=='MD':new.append({'cell_type':'markdown','metadata':{},'source':body})
    else:ast.parse(body);new.append({'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':body})
verification=[cl for cl in cells if cl['cell_type']=='markdown' and ''.join(cl['source']).startswith('## Verification record')]
nb['cells']=keep+new+verification;cells=nb['cells']
cells[0]['source']=src(0).replace('notebook `_14_stage2`, the prespecified full-cohort run','notebook `_15_pathophysiology_full`, the descriptive repeat before the freeze',1)
cells[1]['source']="""## Pathophysiology study, full-release repeat (this `_15_pathophysiology_full`; protocol section 10c.1 and section 11 step 1)

Runs the `_14_stage2` data stages unchanged (all comers, exclusion 7 dropped; everything cached by key is reused) and then the descriptive study of `_13` on the full release: incident, septic-on-arrival and early-ICU-onset stays and matched controls, training-split and non-cohort patients only. Its outputs fix the shared physiology set (item 2(b)) and decide the contingent deterioration target (item 11) before the protocol is frozen. No model is trained; no validation, calibration, test or holdout patient is read.

---
"""+src(1)
for cl in cells:
    if cl['cell_type']=='code':ast.parse(''.join(cl['source']));cl['outputs']=[];cl['execution_count']=None
nb['metadata']['sepsis_validation']={'status':'fixture run before release'}
import nbformat
_,nb=nbformat.validator.normalize(nb) if hasattr(nbformat.validator,'normalize') else (0,nb)
out=R/'Sepsis_V11_Improved_MIMIC_eICU_15_pathophysiology_full.ipynb';out.write_text(json.dumps(nb,indent=1,ensure_ascii=False));print('written',out.stat().st_size//1024,'KB','cells',len(cells))
