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
c=c[:a]+"""STUDY_STAGE = ('PATHOPHYSIOLOGY STUDY (protocol section 10c.1, revised design of 29 Oct 2026 under review): descriptive study of incident (ICU-acquired) sepsis, '
    'septic-on-arrival and early-ICU-onset stays (excluded by YAIB exclusion 7; features from the unlabelled corpus, onset from the label batches) and matched controls, '
    'with deteriorating/improving courses from the raw mortality tables and paired SOFA components. Training-split and non-cohort patients only. '
    'Fresh measurements only; rank-based Cliff delta with stay bootstrap; cross-database rule; data-driven analyses (departure timing, sign order, '
    'phenotypes at onset, compensation states, therapy-stratified reads, selection check, hospital heterogeneity). No model is trained; no validation, test or holdout patient is read.')
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
cells[1]['source']="""## Pathophysiology study (this `_13_pathophysiology`, 29 Oct 2026; protocol section 10c.1, revised design under the partner's review)

Runs the data stages exactly as `_11`/`_12` (everything is reused), loads the unlabelled corpus index, and then describes, on training-split and non-cohort patients only, four septic strata (incident, septic on arrival, early ICU onset; controls with a matched pseudo-onset) and their course (deteriorating / improving from the raw mortality tables and paired SOFA components). Outputs are aggregate: trajectories, measurement rates, rank-based Cliff's deltas with cross-database classification, departure timing, order of signs within patients, phenotypes at onset, compensation states, temperature-heart-rate coupling, therapy-stratified reads, selection check, hospital heterogeneity, lactate clearance, therapy exposure, hypothesis scoring, figures, the stage-2 predictor-set definitions and a text digest. No model is trained. Settings to confirm with the partner are at the top of cell 7a (course horizon 48 h, vasopressor escalation 0.1 NE-eq, 3,000 controls per database).

---
"""+src(1)
for cl in cells:
    if cl['cell_type']=='code':ast.parse(''.join(cl['source']));cl['outputs']=[];cl['execution_count']=None
import nbformat
_,nb=nbformat.validator.normalize(nb) if hasattr(nbformat.validator,'normalize') else (0,nb)
out=R/'Sepsis_V11_Improved_MIMIC_eICU_13_pathophysiology.ipynb';out.write_text(json.dumps(nb,indent=1,ensure_ascii=False));print('written',out.stat().st_size//1024,'KB','cells',len(cells))
