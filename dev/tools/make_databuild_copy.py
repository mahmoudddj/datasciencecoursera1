"""Ready-to-run copy of _14_stage2 for the pre-freeze data build on the project Drive (no edits needed in Colab).
Differs from Sepsis_V11_Improved_MIMIC_eICU_14_stage2.ipynb in exactly two lines of cell 1:
  STAGE2_ARMS = []                        data build only (writes DATA_BUILD_ONLY.json; trains nothing)
  STAGE2_REUSE_LABEL_ROOTS = [<stage-1>]  the stage-1 cohort root used for every all-comers batch plan so far
Everything else (label variants on, FORCE_* False, holdout sealed, PROTOCOL_FROZEN False) is the committed notebook."""
import json
from pathlib import Path
R=Path('/home/user/datasciencecoursera1')
REUSE='/content/drive/.shortcut-targets-by-id/1A7VFDTLnevMBChDvADRU2QJBzHf3s9pF/sepsis_colab_project/cohorts_v9/d3ca16b32309bfb8/sepsis'
nb=json.load(open(R/'Sepsis_V11_Improved_MIMIC_eICU_14_stage2.ipynb'));c=nb['cells'][2];s=''.join(c['source'])
a="STAGE2_ARMS = ['project','two_channel','pooled','suspicion','pretrained','predictor_sets','label_stratified','benchmarks','exploratory']   # section 11 order; remove from the END to cut the budget"
b="STAGE2_ARMS = []                                   # DATA BUILD ONLY (pre-freeze): no model is trained; the arms list returns after the freeze"
assert s.count(a)==1;s=s.replace(a,b)
a="STAGE2_REUSE_LABEL_ROOTS = []                      # earlier"
b=f"STAGE2_REUSE_LABEL_ROOTS = ['{REUSE}']   # stage-1 root of the batch plans in use; earlier"
assert s.count(a)==1;s=s.replace(a,b)
c['source']=s
nb['cells'][0]['source']="> **Data-build copy (pre-freeze).** Ready to run on the project Drive: cell 1 already has `STAGE2_ARMS = []` and the stage-1 reuse path. Runtime: CPU, High-RAM. Use Run all; after a stop, disconnect and delete the runtime, reconnect and Run all again.\n\n"+''.join(nb['cells'][0]['source'])
out=R/'Sepsis_V11_Improved_MIMIC_eICU_14_stage2_databuild.ipynb';out.write_text(json.dumps(nb,indent=1,ensure_ascii=False));print('written',out.name)
