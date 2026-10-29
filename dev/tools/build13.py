"""Build Sepsis_V11_Improved_MIMIC_eICU_13_pathophysiology.ipynb from the _12 notebook (protocol 10c.1).
Data stages are reused unchanged; the training cells are replaced by the descriptive study."""
import json,ast
from pathlib import Path
R=Path('/home/user/datasciencecoursera1');C=R/'dev/work/cells'
nb=json.load(open(R/'Sepsis_V11_Improved_MIMIC_eICU_12_stage1b.ipynb'));cells=nb['cells']
def src(i):return ''.join(cells[i]['source'])
def rep(s,a,b):
    assert s.count(a)==1,a[:70];return s.replace(a,b)
c=src(2)
c=rep(c,"STAGE_1B = True ","STAGE_1B = False")   # the unlabelled corpus is needed; no training in this notebook
a=c.index("STUDY_STAGE = (");b=c.index("DATA_SOURCE = ")
c=c[:a]+"""STUDY_STAGE = ('PATHOPHYSIOLOGY STUDY (protocol section 10c.1, 29 Oct 2026): descriptive comparison of incident (ICU-acquired) sepsis, '
    'arrived-septic stays (excluded by YAIB exclusion 7; features from the unlabelled corpus, onset from the label batches) and controls, '
    'on training-split and non-cohort patients only. Fresh measurements only; Cliff delta with stay bootstrap; cross-database rule. '
    'No model is trained; no validation, test or holdout patient is read.')
"""+c[b:]
cells[2]['source']=c
# keep cells 0..17 (through "6. Resolve settings"); replace the rest with the study
keep=cells[:18]
parts=(C/'pathophys_13.py').read_text().split('# %% ')
new=[]
for p in parts[1:]:
    kind,body=p.split('\n',1);body=body.rstrip('\n')
    if kind.strip()=='MD':new.append({'cell_type':'markdown','metadata':{},'source':body})
    else:ast.parse(body);new.append({'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':body})
nb['cells']=keep+new
cells=nb['cells']
cells[0]['source']=src(0).replace('_12_stage1b','_13_pathophysiology',1)
cells[1]['source']="""## Pathophysiology study (this `_13_pathophysiology`, 29 Oct 2026; protocol section 10c.1)

Runs the data stages exactly as `_11`/`_12` (everything is reused), loads the unlabelled corpus index, and then describes three groups on training-split and non-cohort patients only: incident sepsis, arrived-septic stays (YAIB exclusion 7), controls. Outputs aggregate trajectories, measurement rates, Cliff's deltas with cross-database classification, figures, and the stage-2 predictor-set definitions. No model is trained.

---
"""+src(1)
for cl in cells:
    if cl['cell_type']=='code':ast.parse(''.join(cl['source']));cl['outputs']=[];cl['execution_count']=None
out=R/'Sepsis_V11_Improved_MIMIC_eICU_13_pathophysiology.ipynb';out.write_text(json.dumps(nb,indent=1,ensure_ascii=False));print('written',out.stat().st_size//1024,'KB','cells',len(cells))
