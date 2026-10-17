"""Build the post-hoc evaluation notebook (bedside-score comparators, onset-anchored AUROC,
patient-level AUROC, seed ensemble). It reads a finished run's saved test predictions and
feature shards only; it never trains, recalibrates or touches the sealed holdout."""
import json, sys
from pathlib import Path

MD0 = r"""# Sepsis V11 — evaluation analyses on a finished run (no training)

Reads the saved **internal-test** predictions of a finished run and the hourly feature shards.
It never trains, recalibrates, re-thresholds or opens the sealed 20% holdout. Runs on a CPU runtime in minutes.

**Prespecified on 17 Oct 2026, before any of these analyses were computed** (also written to `analysis_protocol.json`):

1. **Bedside-score comparators** on exactly the same test patient-hours and target (sepsis onset within the next 6 h):
   qSOFA, SIRS and SOFA-proxy (platelets, bilirubin, MAP<70, creatinine, GCS; not full SOFA).
   *Primary* version: number of criteria met among those measured (a missing criterion counts as not met, as most EHR score tools do).
   *Secondary* version: complete score only (hours without all components rank lowest).
2. **Onset-anchored AUROC** at k = 6, 4 and 2 h before onset: for each sepsis stay, the score at the eligible hour with
   onset − hour in (k−1, k]; for each never-septic stay, one eligible hour drawn at random (seed 42, the same hour for every model).
   This mirrors the fixed-time-to-onset framing of most published studies. It is NOT the hourly sliding-window AUROC.
3. **Patient-level AUROC**: highest pre-onset hourly score per stay; sepsis stay vs never-septic stay. Longer stays have more
   chances of a high maximum (length-of-stay bias); reported for comparison with the original PhysioNet OSTA metric only.
4. **Seed ensemble** (only when the run has several seeds): mean of the seeds' raw model logits per hour, as in the original OSTA.

Every number is reported with its definition. Hourly sliding-window AUROC remains the primary result. 95% CIs: patient-cluster
bootstrap, 200 resamples; paired differences vs OSTA use the same resamples. All outputs are aggregate tables."""

C1 = r"""# 1. Settings: change RUN_KEY only (the finished run to analyse).
import os, json, time, importlib.util
from pathlib import Path
RUN_KEY = 'ed26e1692aa04d2c'          # corrected 10k interim run; use the 3-seed run's key when it finishes
PROJECT_PATH = os.environ.get('SEPSIS_PROJECT_ROOT', '')
DATA_ROOT_OVERRIDE = os.environ.get('SEPSIS_ANALYSIS_DATA_ROOT', '')   # testing only
N_BOOT = 200; SEED = 42; KS = [6, 4, 2]
ARMS = ['osta','gated_attention','ungated_attention','observer_features','output_fusion','cnn','logistic','boosted_tree']
SCORES = {'qSOFA': ['qSOFA_Resp','qSOFA_SBP','qSOFA_GCS'],
          'SIRS': ['SIRS_Temp','SIRS_HR','SIRS_Resp','SIRS_WBC'],
          'SOFAproxy': ['SOFAproxy_Coag','SOFAproxy_Liver','SOFAproxy_MAP','SOFAproxy_Creatinine','SOFAproxy_CNS']}
if not PROJECT_PATH and importlib.util.find_spec('google') and importlib.util.find_spec('google.colab'):
    from google.colab import drive
    if not os.path.isdir('/content/drive/MyDrive'): drive.mount('/content/drive')
    base = Path('/content/drive/.shortcut-targets-by-id/1A7VFDTLnevMBChDvADRU2QJBzHf3s9pF/sepsis_colab_project')
    PROJECT = base if base.is_dir() else Path('/content/drive/MyDrive/sepsis_colab_project')
else:
    PROJECT = Path(PROJECT_PATH or 'sepsis_colab_project')
RUN = PROJECT/'validation_v10'/'runs'/RUN_KEY
if not (RUN/'run_protocol.json').is_file(): raise FileNotFoundError(f'Run not found: {RUN}')
if not (RUN/'COMPLETE.json').is_file(): print('NOTE: run is INCOMPLETE; analysing the arms/datasets finished so far')
PROTO = json.loads((RUN/'run_protocol.json').read_text())
DATA_ROOT = Path(DATA_ROOT_OVERRIDE) if DATA_ROOT_OVERRIDE else PROJECT/'validation_v10'/'data'/PROTO['data_key']
OUT = RUN/'analysis_v1'; OUT.mkdir(exist_ok=True)
proto_file = OUT/'analysis_protocol.json'
if not proto_file.is_file():   # first write keeps the prespecification timestamp
    proto_file.write_text(json.dumps({'prespecified_on':'2026-10-17','first_run_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'run_key':RUN_KEY,'definitions':'see notebook header (items 1-4)','bootstrap':N_BOOT,'seed':SEED,'k_hours':KS,
        'scores':SCORES,'arms':ARMS}, indent=1))
print('Run:', RUN, '| mode:', PROTO.get('mode'), '| stage:', PROTO.get('study_stage','')[:60])"""

C2 = r"""# 2. Helpers: point estimates and patient-cluster bootstrap (shared resamples for paired differences).
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score
def _metrics(y, s, w=None):
    return roc_auc_score(y, s, sample_weight=w), average_precision_score(y, s, sample_weight=w)
def evaluate(frame, cols, ref='osta', n_boot=N_BOOT, seed=SEED):
    y = frame.y.to_numpy(); idx, groups = pd.factorize(frame.Group_ID.astype(str), sort=True)
    point = {c: _metrics(y, frame[c].to_numpy()) for c in cols}
    rng = np.random.default_rng(seed); draws = {c: [] for c in cols}
    for _ in range(n_boot):
        w = rng.multinomial(len(groups), np.full(len(groups), 1/len(groups)))[idx].astype(float)
        if w[y == 1].sum() == 0 or w[y == 0].sum() == 0: continue
        keep = w > 0
        for c in cols: draws[c].append(_metrics(y[keep], frame[c].to_numpy()[keep], w[keep]))
    rows = []
    for c in cols:
        d = np.array(draws[c]); lo, hi = np.quantile(d, [.025, .975], axis=0)
        row = {'model_or_score': c, 'n_rows': len(frame), 'positives': int(y.sum()),
               'AUROC': point[c][0], 'AUROC_lo': lo[0], 'AUROC_hi': hi[0],
               'AUPRC': point[c][1], 'AUPRC_lo': lo[1], 'AUPRC_hi': hi[1]}
        if ref in draws and c != ref:
            diff = np.array(draws[ref])[:, 0] - d[:, 0]
            row.update({'OSTA_minus_this_AUROC': point[ref][0] - point[c][0],
                        'diff_lo': np.quantile(diff, .025), 'diff_hi': np.quantile(diff, .975)})
        rows.append(row)
    return pd.DataFrame(rows)
def show(df, name):
    df.to_csv(OUT/name, index=False); display(df.round(3)); print('saved', OUT/name)"""

C3 = r"""# 3. Load test predictions for every arm and seed, and the bedside-score inputs for the same hours.
index = pd.read_parquet(DATA_ROOT/'index.parquet')
WIDE, SEEDCOLS = {}, {}
for ds in ['miiv', 'eicu']:
    base = None; SEEDCOLS[ds] = {}
    for arm in ARMS:
        for f in sorted((RUN/'rich'/ds).glob(f'seed_*/{arm}/predictions_normal.parquet')):
            seed = f.parts[-3].split('_')[1]; col = f'{arm}_s{seed}'
            p = pd.read_parquet(f, columns=['Patient_ID','Group_ID','Hour','y','OnsetHour','logit'])
            p['Patient_ID'] = p.Patient_ID.astype(str); p['Group_ID'] = p.Group_ID.astype(str); p['Hour'] = p.Hour.round(3)
            if base is None: base = p.drop(columns='logit')
            p = p[['Patient_ID','Hour','y','logit']].rename(columns={'logit': col, 'y': 'y_'+col})
            n0 = len(base); base = base.merge(p, on=['Patient_ID','Hour'], how='inner', validate='one_to_one')
            if len(base) != n0 or not (base['y_'+col] == base.y).all(): raise ValueError(f'{ds}/{col}: prediction rows do not match')
            base = base.drop(columns='y_'+col); SEEDCOLS[ds].setdefault(arm, []).append(col)
    if base is None: print(f'{ds}: no finished predictions yet; skipped'); continue
    # One column per arm: first seed (s42); plus the ensemble when there are several seeds.
    for arm, cols in SEEDCOLS[ds].items():
        base[arm] = base[cols[0]]
        if len(cols) > 1: base[arm+'_ensemble'] = base[cols].mean(axis=1)
    # Bedside-score inputs, read from the hourly feature shards of the test stays only.
    need = sorted({c for cs in SCORES.values() for c in cs})
    ix = index[index.Patient_ID.astype(str).isin(set(base.Patient_ID))]
    parts = []
    for file, g in ix.groupby('file'):
        sh = pd.read_parquet(file)
        sh = sh[sh.Patient_ID.astype(str).isin(set(g.Patient_ID.astype(str)))]
        keep = ['Patient_ID','Hour'] + [c for c in need if c in sh.columns]
        parts.append(sh[keep])
    feats = pd.concat(parts, ignore_index=True); feats['Patient_ID'] = feats.Patient_ID.astype(str); feats['Hour'] = feats.Hour.astype(float).round(3)
    n0 = len(base); base = base.merge(feats, on=['Patient_ID','Hour'], how='left', validate='one_to_one')
    if len(base) != n0: raise ValueError('feature join changed the row count')
    for name, comps in SCORES.items():
        present = [c for c in comps if c in base.columns]
        if len(present) < len(comps): print(f'{ds}: {name} skipped, missing columns {set(comps)-set(present)}'); continue
        base[name] = base[present].fillna(0).sum(axis=1)                       # primary: criteria met among measured
        complete = base[present].notna().all(axis=1)
        base[name+'_complete'] = base[present].sum(axis=1).where(complete, -1)  # secondary: complete score only
        print(f'{ds}: {name} complete on {complete.mean():.1%} of test hours')
    WIDE[ds] = base
    print(ds, '| test rows', len(base), '| stays', base.Patient_ID.nunique(), '| arms', list(SEEDCOLS[ds]),
          '| seeds per arm', {a: len(c) for a, c in SEEDCOLS[ds].items()})"""

C4 = r"""# 4. Analysis 1: hourly sliding-window AUROC/AUPRC — models vs bedside scores (same hours, same 6-h target).
def model_cols(ds):
    cols = [a for a in ARMS if a in WIDE[ds]]
    cols += [a+'_ensemble' for a in ARMS if a+'_ensemble' in WIDE[ds]]
    cols += [s for s in SCORES if s in WIDE[ds]] + [s+'_complete' for s in SCORES if s+'_complete' in WIDE[ds]]
    return cols
HOURLY = pd.concat([evaluate(WIDE[ds], model_cols(ds)).assign(dataset=ds, analysis='hourly sliding window') for ds in WIDE])
show(HOURLY, 'hourly_models_vs_bedside_scores.csv')"""

C5 = r"""# 5. Analysis 2: onset-anchored AUROC at k hours before onset (fixed-time framing used by most published studies).
ONSET = []
for ds, w in WIDE.items():
    sepsis_stays = set(w.loc[w.y.eq(1), 'Patient_ID'])
    never = w[w.OnsetHour.isna()]
    controls = never.groupby('Patient_ID').sample(n=1, random_state=SEED)   # one random hour per never-septic stay; same rows for every k and model
    for k in KS:
        lead = w.OnsetHour - w.Hour
        cand = w[w.Patient_ID.isin(sepsis_stays) & (lead > k - 1) & (lead <= k)]
        pos = cand.sort_values('Hour').groupby('Patient_ID').tail(1)
        frame = pd.concat([pos.assign(y=1), controls.assign(y=0)], ignore_index=True)
        r = evaluate(frame, model_cols(ds)).assign(dataset=ds, analysis=f'onset-anchored, {k} h before onset',
                                                   sepsis_stays=len(pos), control_stays=len(controls))
        ONSET.append(r)
ONSET = pd.concat(ONSET); show(ONSET, 'onset_anchored_auroc.csv')"""

C6 = r"""# 6. Analysis 3: patient-level AUROC (highest pre-onset hourly score per stay; length-of-stay bias noted).
PATIENT = []
for ds, w in WIDE.items():
    cols = model_cols(ds)
    agg = w.groupby('Patient_ID').agg({**{c: 'max' for c in cols}, 'y': 'max', 'Group_ID': 'first', 'OnsetHour': 'first'}).reset_index()
    agg = agg[agg.y.eq(1) | agg.OnsetHour.isna()]     # sepsis stays vs never-septic stays
    PATIENT.append(evaluate(agg, cols).assign(dataset=ds, analysis='patient-level (max pre-onset score)'))
PATIENT = pd.concat(PATIENT); show(PATIENT, 'patient_level_auroc.csv')"""

C7 = r"""# 7. One compact table for slides: OSTA, gated attention, best other model, and the three bedside scores.
pick = ['osta','osta_ensemble','gated_attention','gated_attention_ensemble','cnn','logistic','boosted_tree','qSOFA','SIRS','SOFAproxy']
ALL = pd.concat([HOURLY, ONSET, PATIENT])
SLIDE = ALL[ALL.model_or_score.isin(pick)].copy()
SLIDE['AUROC (95% CI)'] = SLIDE.apply(lambda r: f"{r.AUROC:.3f} ({r.AUROC_lo:.3f}-{r.AUROC_hi:.3f})", axis=1)
SLIDE = SLIDE.pivot_table(index=['dataset','model_or_score'], columns='analysis', values='AUROC (95% CI)', aggfunc='first')
SLIDE.to_csv(OUT/'slide_summary_auroc.csv'); display(SLIDE)
print('All tables saved in', OUT, '| definitions in analysis_protocol.json and the notebook header.')"""

def cell(src, kind='code'):
    c = {'cell_type': kind, 'metadata': {}, 'source': src.strip('\n').splitlines(True)}
    if kind == 'code': c.update(execution_count=None, outputs=[])
    return c

nb = {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {'kernelspec': {'name': 'python3', 'display_name': 'Python 3'},
      'language_info': {'name': 'python'}}, 'cells': [cell(MD0, 'markdown'), cell(C1), cell(C2), cell(C3), cell(C4), cell(C5), cell(C6), cell(C7)]}
out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('Sepsis_V11_Analysis_comparators.ipynb')
out.write_text(json.dumps(nb, indent=1, ensure_ascii=False)); print('wrote', out)
