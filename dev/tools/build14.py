"""Build Sepsis_V11_Improved_MIMIC_eICU_14_stage2.ipynb from the _12 notebook (protocol section 11, 10c.2).
Embeds the v12 modules and the stage-2 worker (environment-switched label variants and exclusion 7); the v9/v10/v11
modules stay as embedded in _12. The worker hash changes, so the all-comers cohort gets its own key (intended)."""
import json,gzip,base64,hashlib,io,ast,re
from pathlib import Path
R=Path('/home/user/datasciencecoursera1');M=R/'dev/work/mods';C=R/'dev/work/cells'
nb=json.load(open(R/'Sepsis_V11_Improved_MIMIC_eICU_12_stage1b.ipynb'));cells=nb['cells']
def src(i):return ''.join(cells[i]['source'])
def setsrc(i,s):cells[i]['source']=s
def rep(s,a,b):
    assert s.count(a)==1,a[:70];return s.replace(a,b)
def embed(raw):
    buf=io.BytesIO()
    with gzip.GzipFile(fileobj=buf,mode='wb',mtime=0,filename='') as g:g.write(raw)
    return {'sha256':hashlib.sha256(raw).hexdigest(),'data':base64.b64encode(buf.getvalue()).decode()}
def code(text):return {'cell_type':'code','execution_count':None,'metadata':{},'outputs':[],'source':text.rstrip('\n')}
def md(text):return {'cell_type':'markdown','metadata':{},'source':text.rstrip('\n')}
# --- cell 3: embedded modules ---
s3=src(3).splitlines();k=[i for i,l in enumerate(s3) if l.startswith('EMBEDDED_MODULES = ')][0]
emb=ast.literal_eval(s3[k][len('EMBEDDED_MODULES = '):])
for n in ['v12_manifest.py','v12_labels.py','v12_features.py','v12_data.py','v12_models.py','v12_evaluate.py','v12_train.py','v12_cohort.py','v12_fixture.py','v12_tests.py','v9_yaib_worker.py']:
    emb[n]=embed((M/n).read_bytes())
s3[k]='EMBEDDED_MODULES = '+repr(emb);s3='\n'.join(s3)
s3=rep(s3,"    if name.startswith(('v9_','v10_')):del sys.modules[name]","    if name.startswith(('v9_','v10_','v11_','v12_')):del sys.modules[name]")
setsrc(3,s3)
# --- cell 2: configuration ---
c=src(2)
c=rep(c,"FULL_SAMPLE_STAYS_PER_DATASET = 10000      # PRESPECIFIED (16 Oct 2026, before any interim result): random sample of candidate ICU stays per database (seed RANDOM_STATE); None = all stays",
        "FULL_SAMPLE_STAYS_PER_DATASET = None       # STAGE 2: all candidate stays of both releases (section 11); the 10,000-stay samples were stage 1")
c=rep(c,"FULL_SEEDS = [42]                          # 1 seed on the 10k samples (shortlist rule); FULL COHORT: FULL_SAMPLE_STAYS_PER_DATASET=None and FULL_SEEDS=[42,7,123]",
        "FULL_SEEDS = [42,7,123]                    # section 11 seed tiering: all three for arms 1-5 (project, two-channel, pooled, suspicion, pretrained); the first for arms 6-9")
c=rep(c,"LABEL_PARALLEL_BATCHES = 6 ","LABEL_PARALLEL_BATCHES = 8 ")
a=c.index("STUDY_STAGE = (");b=c.index("DATA_SOURCE = ")
c=c[:a]+"""STUDY_STAGE = ('STAGE 2 (protocol section 11, revised 31 Oct 2026 after the pre-freeze review; built before the freeze): all comers of both releases '
    '(YAIB exclusion 7 dropped, incident cohort primary), the arms in the section-11 order with seed tiering, the two-channel model, pooled training, '
    'the suspicion-anchored target (3 h), weakly supervised multi-task pretraining, predictor-set and baseline-relative arms, the label-stratified arm, '
    'the literature benchmarks and the exploratory pair; scoring passes on saved predictions (pre-treatment, documentation strata, label sensitivities, '
    'abstention variants, threshold transport, temporal validation). Until PROTOCOL_FROZEN is True after the signed tag, test-split rows are sealed on disk '
    'and only validation rows are printed; the protected holdout is untouched.')
"""+c[b:]
c=rep(c,"STAGE_1B = True ","STAGE_1B = False")
c=re.sub(r"STAGE2_OPERATING_POINT = 'absolute'.*","STAGE2_OPERATING_POINT = 'quantile'                # decided by rule 10b.2.3 on run b9b18c8632cf33d0 (31 Oct 2026)",c)
c=re.sub(r"STAGE2_PERSISTENCE = 1; STAGE2_FRESH_ONLY = False.*","STAGE2_PERSISTENCE = 2; STAGE2_FRESH_ONLY = False  # decided by rule 10b.2.4 on run b9b18c8632cf33d0 (31 Oct 2026): persistence 2 h, all hours\nSTAGE2_PROJECT_MODEL = 'flat_osta'; STAGE2_INPUT_DROPOUT = 0.0   # decided by rule 10b.2.1 on the same run; organ heads not supported",c)
c=rep(c,"PRIOR_TEST_EXPOSURE = (","PRIOR_TEST_EXPOSURE = (")
c=rep(c,"""    'No result with RELEASE_FINAL_HOLDOUT=True has ever been produced or viewed.')""",
"""    'Stage-1b VALIDATION results of run b9b18c8632cf33d0 (_12, 10,000-stay samples) were viewed on 31 Oct 2026; its test rows stayed sealed. '
    'The revised pathophysiology study (_13, training-split and non-cohort patients only) was viewed on 30-31 Oct 2026. Stage 2 was written after that and before any stage-2 code ran on data. '
    'No result with RELEASE_FINAL_HOLDOUT=True has ever been produced or viewed.')""")
c=rep(c,"AUTO_FIND_RAW = True",(C/'stage2_config_block.py').read_text().rstrip('\n')+"\nAUTO_FIND_RAW = True")
c=rep(c,"assert FULL_SAMPLE_STAYS_PER_DATASET is None or FULL_SAMPLE_STAYS_PER_DATASET>=5000, 'Interim sample too small for full training'",
        "assert FULL_SAMPLE_STAYS_PER_DATASET is None or FULL_SAMPLE_STAYS_PER_DATASET>=5000, 'Interim sample too small for full training'\nassert not (PROTOCOL_FROZEN and not PROTOCOL_FREEZE_TAG.strip()), 'PROTOCOL_FROZEN needs the signed tag'")
setsrc(2,c)
# --- cell 4: checks ---
setsrc(4,"""# 3. Nonclinical engineering checks; detailed output goes to a log.
import contextlib,io
from v10_tests import run_checks
from v12_tests import run_checks as run_checks_v12,run_checks_models_and_scoring,run_checks_stores
with (LOG_ROOT/'engineering_checks.log').open('w') as log, contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
    CHECKS=run_checks()+run_checks_v12()+run_checks_models_and_scoring()+run_checks_stores(RUNTIME_ROOT/'v12_check_fixture')
atomic_json(LOG_ROOT/'engineering_checks.json',CHECKS)
print(len(CHECKS),'engineering checks passed (stage 1 + stage 2 modules). This does not validate real clinical extraction.')""")
# --- cell 8: cohort key (all comers) ---
c8=src(8)
c8=rep(c8,"    COHORT_PROTOCOL={'version':'v9_balanced_2','raw':RAW_FINGERPRINTS,'yaib':YAIB_COHORTS_COMMIT,",
          "    COHORT_PROTOCOL={'version':'v12_all_comers' if STAGE2_KEEP_EARLY_ONSET else 'v9_balanced_2','raw':RAW_FINGERPRINTS,'yaib':YAIB_COHORTS_COMMIT,'stage2':{'keep_early_onset':STAGE2_KEEP_EARLY_ONSET},")
c8=rep(c8,"print('Cohorts to build (smoke-capped label extraction):'","print('Cohorts to build (all comers; completed label batches of the earlier plans reused):'")
setsrc(8,c8)
# --- cells 12, 14, 17-18, 19-20, 22 ---
assert src(12).startswith("if DATA_SOURCE == 'clinical':\n    run_preserved('v9_extract_labels.py')"),src(12)[:80]
setsrc(12,(C/'stage2_extract.py').read_text())
assert src(14).startswith("if DATA_SOURCE=='clinical':\n    # Raw-table event stage");setsrc(14,(C/'stage2_data.py').read_text())
assert src(16).startswith('# 5c. Unlabelled corpus')
assert src(17).startswith('# 6. Resolve');assert src(18).startswith('# 7. V11 matched');assert src(19).startswith('# 7a. STAGE 1b');assert src(20).startswith('# 7b. Team summary');assert src(22).startswith('# Concise summary')
new_cells=cells[:17]+[code((C/'stage2_train.py').read_text()),code((C/'team_summary_stage2.py').read_text()),cells[21],code((C/'stage2_summary.py').read_text())]+cells[23:]
nb['cells']=new_cells;cells=nb['cells']
# --- markdown ---
setsrc(0,src(0).replace('notebook `_12_stage1b`, architectures and losses','notebook `_14_stage2`, the prespecified full-cohort run',1))
setsrc(1,"""## Stage 2 (this `_14_stage2`; protocol section 11 as revised on 31 Oct 2026)

Built after stage 1b and the revised pathophysiology study, before the freeze. Until the protocol is frozen (`PROTOCOL_FROZEN=True`, signed tag), every test-split row is sealed on disk and only validation rows are printed.

| Item | What this notebook does |
|---|---|
| Cohort | all comers of both releases: YAIB exclusion 7 (onset before ICU hour 6) is not applied; the index flags incident vs arrival sepsis; the incident cohort is primary; completed label batches of the earlier 20,000-candidate plans are reused; eight label batches in parallel, resumable |
| Label variants | antibiotic-only `sep3_alt` on MIMIC-IV, culture-paired on eICU (labels phase only): the item-10 sensitivity passes on saved predictions |
| Arms (section 11 order) | 1 project model `flat_osta` (dropout 0); 2 two-channel (physiology+host / practice) with zeroed, z-scored and quantile-mapped practice rows, the practice-only probe and the concept-grouped comparator; 3 pooled training (one normaliser per database) with eICU leave-hospital-out; 4 suspicion-anchored target (3 h, no utility; 6 h reading); 5 weakly supervised multi-task pretraining (arrival sepsis, SOFA components, treatment events) with zero-shot and 10 % fine-tune; 6 predictor sets (physiology path with/without host, shared physiology, baseline-relative/absolute/both); 7 label-stratified (documented, positive-unlabelled soft); 8 GRU-D, TCN, boosted trees, logistic; 9 exploratory SSL pair |
| Seeds | 42, 7, 123 for arms 1-5; 42 for arms 6-9 (project-model seed spread reported as the yardstick) |
| Policy | plain BCE; quantile operating point; persistence 2 h, all hours; abstention variants (reset / transparent / gated) on validation with the adoption rule |
| Scoring passes | pre-treatment hours; documented vs undocumented strata; suspicion-label and alternative-label sensitivities; threshold transport per eICU hospital; MIMIC temporal validation by anchor-year group; lead versus the first antibiotic; transfer rows |
| Training split | the retired observer bank's split joins training (70 % of development patients); recorded in `run_protocol.json` |

---
"""+src(1))
for i,cl in enumerate(cells):
    if cl['cell_type']=='markdown' and ''.join(cl['source']).startswith('## 8. Results and completion'):
        setsrc(i,"""## 8. Results and completion
Rows returned before the freeze: validation-split rows per arm (`condition=validation`) and the abstention variants. Test-split rows (`normal`, the scoring passes, transfer rows) are computed, written to `test_rows_sealed.json` in each arm folder and never printed until `PROTOCOL_FROZEN=True`. Each arm saves predictions, alarms, calibration bins, Platt parameters, threshold sweep, training history and checkpoints (`last.pt` per epoch for resumption; `completed.json` per arm).""")
    if cl['cell_type']=='markdown' and ''.join(cl['source']).startswith('## 9. Next step'):
        setsrc(i,"""## 9. Next steps
1. Consultants' answers (item 12) and the shared physiology set from the full-release pathophysiology repeat written into the protocol; then the freeze: one commit, tagged and signed by the candidate and the partner, SHA-256 hash and PDF deposited (OSF or Zenodo), `PRIOR_TEST_EXPOSURE` declared.
2. Data build on the full releases (Sections 4-5; about one day of CPU runtime), then this notebook arm by arm; `PROTOCOL_FROZEN=True` with the tag releases the test rows.
3. `RELEASE_FINAL_HOLDOUT=True` once, for the prespecified cross-database directions on the protected patients.
4. Report with TRIPOD+AI; assess risk of bias with PROBAST+AI; any post-freeze change goes to `PROTOCOL_DEVIATIONS.md`.""")
for cl in cells:
    if cl['cell_type']=='code':ast.parse(''.join(cl['source']));cl['outputs']=[];cl['execution_count']=None
nb['metadata']['sepsis_validation']={'status':'fixture run before release'}
import nbformat
_,nb=nbformat.validator.normalize(nb) if hasattr(nbformat.validator,'normalize') else (0,nb)
out=R/'Sepsis_V11_Improved_MIMIC_eICU_14_stage2.ipynb'
out.write_text(json.dumps(nb,indent=1,ensure_ascii=False));print('written',out.stat().st_size//1024,'KB','cells',len(nb['cells']))
