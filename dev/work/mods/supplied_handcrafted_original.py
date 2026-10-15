"""
Medical Index + Change/Trend features for sepsis prediction.

WHY THESE, SPECIFICALLY:
Wang et al., 2025, npj Digital Medicine (systematic review of 91 sepsis
prediction studies) found that hand-crafted features were the only
methodology factor that significantly improved the Official Utility Score
(meta-regression coefficient = 0.16, P = 0.003). Breaking that down further,
two specific sub-types drove it:
  - "Medical Index" features (composite scores with medical meaning, e.g.
    qSOFA calculated from raw vitals) -- coefficient = 0.10, P = 0.016,
    the single strongest contributor identified.
  - "Change/Trend" features (slope/trend of a variable over its feature
    window, e.g. slope of heart rate over the past 4 hours) -- P = 0.008.
The review's own example of a high-value Medical Index feature: "Age x
Systolic Blood Pressure" ranked in the top 10 most important features in
Camacho-Cogollo et al.'s study.

WHAT THIS IS AND ISN'T:
This is NOT a reconstruction of TREWScore's exact 54-predictor list -- that
list is not public in machine-readable form (it exists only in the original
paper's supplementary PDF and a flowchart figure we could not access). What
IS confirmed, from an independent transportability study that mapped all 54
TREWScore predictors to a new hospital, is that TREWScore's predictor set
includes SBP, DBP, MAP, HR, RR, GCS, WBC, BUN, BUN/Creatinine ratio, SOFA
components, and SIRS criteria -- all implemented causally below, using only
values available up to and including the current hour, per this project's
causal-masking discipline.

Every function takes already-causal (forward-filled, point-in-time) values
for the CURRENT hour and/or a trailing window -- never a future value.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


# ============================================================================
# MEDICAL INDEX features (composite scores with medical meaning)
# ============================================================================

def mean_arterial_pressure(sbp, dbp):
    """MAP = DBP + 1/3(SBP - DBP). One of TREWScore's confirmed predictors."""
    return dbp + (sbp - dbp) / 3.0


def shock_index(hr, sbp):
    """HR / SBP. Simple, standard severity ratio; rises early in shock."""
    sbp_safe = np.where(sbp > 0, sbp, np.nan)
    return hr / sbp_safe


def bun_creatinine_ratio(bun, creatinine):
    """BUN / Creatinine. A confirmed TREWScore predictor (BUN/CR in its legend)."""
    cr_safe = np.where(creatinine > 0, creatinine, np.nan)
    return bun / cr_safe


def age_x_sbp(age, sbp):
    """Age x SBP interaction -- the review's own cited top-10 feature example
    (Camacho-Cogollo et al.)."""
    return age * sbp


def qsofa(resp, sbp, gcs=None):
    """Quick SOFA (Singer et al. 2016, Sepsis-3): 0-3 points.
    resp>=22, SBP<=100, altered mentation (GCS<15). GCS is optional --
    PhysioNet-style datasets often lack it; qSOFA is still computed on the
    two available criteria if so (this is a real, stated limitation, not a
    silent gap: see Phase 3 of the getting-started guide, where GCS is
    flagged as a feature to newly collect from MIMIC-IV/eICU/HiRID)."""
    resp = np.asarray(resp, dtype=float); sbp = np.asarray(sbp, dtype=float)
    pts = (resp >= 22).astype(float) + (sbp <= 100).astype(float)
    if gcs is not None:
        gcs = np.asarray(gcs, dtype=float)
        pts = pts + (gcs < 15).astype(float)
    return pts  # range 0-3 (or 0-2 without GCS)


def sirs_criteria(temp, hr, resp, wbc, paco2=None):
    """SIRS, as FOUR SEPARATE binary criteria plus the overall count.
    CONFIRMED from the actual TREWScore predictor-mapping figure (Niemantsverdriet
    et al. 2022, Figure 1): TREWScore encodes 'SIRS heart', 'SIRS temperature',
    'SIRS respiratory', and 'SIRS hematologic' as four INDEPENDENT engineered
    predictors, not just one combined count -- so its LASSO step can weigh each
    criterion on its own. This project's earlier interpretability finding (false
    positives are disproportionately SIRS-positive, non-infectious cases) is
    exactly why the per-criterion breakdown, not just the count, is worth keeping.
    Returns a dict: sirs_heart, sirs_temperature, sirs_respiratory,
    sirs_hematologic (each 0/1), and sirs_count (0-4, sum of the four)."""
    temp = np.asarray(temp, dtype=float); hr = np.asarray(hr, dtype=float)
    resp = np.asarray(resp, dtype=float); wbc = np.asarray(wbc, dtype=float)
    sirs_temperature = ((temp > 38) | (temp < 36)).astype(float)
    sirs_heart = (hr > 90).astype(float)
    if paco2 is not None:
        paco2 = np.asarray(paco2, dtype=float)
        sirs_respiratory = ((resp > 20) | (paco2 < 32)).astype(float)
    else:
        sirs_respiratory = (resp > 20).astype(float)
    sirs_hematologic = ((wbc > 12) | (wbc < 4)).astype(float)
    count = sirs_temperature + sirs_heart + sirs_respiratory + sirs_hematologic
    return {"sirs_heart": sirs_heart, "sirs_temperature": sirs_temperature,
            "sirs_respiratory": sirs_respiratory, "sirs_hematologic": sirs_hematologic,
            "sirs_count": count}


def highest_score_so_far(score: np.ndarray) -> np.ndarray:
    """Running (expanding) max of a score up to and including hour t -- causal
    by construction (uses only past+current values). CONFIRMED from the same
    TREWScore figure: 'highest_sofa_score' is one of its 14 engineered
    predictors, i.e. the worst SOFA-type score seen so far in the stay, not
    just the current one."""
    return pd.Series(score).astype(float).cummax().values


def hours_since_event(event_flag: np.ndarray) -> np.ndarray:
    """Hours since the most recent True in `event_flag`, up to and including
    the current hour; -1 if the event hasn't happened yet. Causal by
    construction. CONFIRMED as the shape of two TREWScore predictors:
    'time since first antibiotics' and the (unmappable) 'time since first
    organ dysfunction'. Use with an antibiotic-order flag if your dataset has
    one; PhysioNet-2019-style datasets don't, so this only becomes usable once
    the richer MIMIC-IV/eICU/HiRID medication data (Phase 1) is in."""
    flag = np.asarray(event_flag, dtype=bool)
    out = np.full(len(flag), -1.0)
    since = -1
    for t in range(len(flag)):
        if flag[t] and since == -1:
            since = 0
        elif since >= 0:
            since += 1
        out[t] = since
    return out


COMORBIDITY_FLAGS_NOTE = """
CONFIRMED TREWScore comorbidity predictors (ICD-9-coded in the original;
use whatever admission/diagnosis coding the target dataset provides -- MIMIC-IV
and eICU both have diagnosis tables): chronic_liver_disease_cirrhosis,
immunocompromised, hematological_malignancy, chronic_heart_failure,
chronic_organ_insufficiency, diabetes, metastatic_carcinoma.

IMPORTANT CAUSAL-SAFETY NOTE, confirmed directly from the source figure: it
explicitly marks several predictors as "documented within 24h" of ICU
admission and therefore "not readily available at ICU admission." If a
comorbidity is only charted a few hours into the stay, using it as a feature
from hour 0 is a genuine, easy-to-miss leak -- the model would be using
information that did not actually exist yet at that hour. Apply each
comorbidity flag starting from its own documentation timestamp forward, never
backdated to admission. This is exactly the class of bug Phase 4's truncation
test is built to catch -- run it on these specifically once implemented.
"""


def sofa_components(platelets, bilirubin, map_, creatinine, gcs=None):
    """SOFA sub-scores (Vincent et al. 1998), 0-4 each, using the components
    computable without ABG/vasopressor-dose data (coagulation, liver,
    cardiovascular via MAP, renal; +CNS if GCS available). Respiratory SOFA
    needs PaO2/FiO2, which most EHR-derived datasets lack reliably -- omitted
    here rather than approximated, to avoid a silently wrong number. SOFA is
    a confirmed TREWScore predictor category (SOFA in its legend)."""
    platelets = np.asarray(platelets, dtype=float)
    bilirubin = np.asarray(bilirubin, dtype=float)
    map_ = np.asarray(map_, dtype=float)
    creatinine = np.asarray(creatinine, dtype=float)

    coag = np.select([platelets < 20, platelets < 50, platelets < 100, platelets < 150],
                     [4, 3, 2, 1], default=0).astype(float)
    liver = np.select([bilirubin >= 12, bilirubin >= 6, bilirubin >= 2, bilirubin >= 1.2],
                      [4, 3, 2, 1], default=0).astype(float)
    cardio = np.where(map_ < 70, 1.0, 0.0)  # without vasopressor-dose data, MAP<70 = 1
    renal = np.select([creatinine >= 5, creatinine >= 3.5, creatinine >= 2, creatinine >= 1.2],
                      [4, 3, 2, 1], default=0).astype(float)

    out = {"sofa_coag": coag, "sofa_liver": liver, "sofa_cardio": cardio, "sofa_renal": renal}
    total = coag + liver + cardio + renal
    if gcs is not None:
        gcs = np.asarray(gcs, dtype=float)
        cns = np.select([gcs < 6, gcs < 10, gcs < 13, gcs < 15], [4, 3, 2, 1], default=0).astype(float)
        out["sofa_cns"] = cns
        total = total + cns
    out["sofa_total_partial"] = total  # "partial": missing respiratory sub-score
    return out


# ============================================================================
# CHANGE/TREND features (over a trailing window) -- causal by construction.
# All use pandas .rolling(), which is backward-looking: window at hour t
# covers [t-window+1, t] only, never a future hour.
# ============================================================================

def rolling_slope(series: pd.Series, window: int) -> np.ndarray:
    """Slope of `series` over the trailing `window` hours."""
    s = pd.Series(series).astype(float)
    return ((s - s.shift(window - 1)) / float(max(window - 1, 1))).values


def rolling_variance(series: pd.Series, window: int) -> np.ndarray:
    """Variance over the trailing window. CONFIRMED as a top-ranked feature:
    a PhysioNet/CinC 2019 entry (cinc.org/2019/Program/accepted/114.html)
    using 6h overlapping windows + random forest reported its single most
    predictive feature was the variance of heart rate, ahead of any mean or
    single-value feature. Kept as its own feature (not just derived from std)
    for fidelity to that result -- tree/neural models can weight it
    differently than std even though the two are a monotonic transform of
    each other."""
    return pd.Series(series).astype(float).rolling(window, min_periods=1).var().values


def rolling_skewness(series: pd.Series, window: int) -> np.ndarray:
    """Skewness (asymmetry) over the trailing window. CONFIRMED: the same
    CinC2019 entry ranked skewness of heart rate as its #3 predictive feature
    (behind HR variance and max temperature). Clinically plausible: captures
    occasional sharp HR spikes riding on an otherwise steady baseline, which
    a mean or slope alone would miss."""
    return pd.Series(series).astype(float).rolling(window, min_periods=1).skew().values


def pairwise_vital_interactions(hr, resp, sbp, temp, spo2=None) -> dict:
    """Pairwise products/ratios between vitals. CONFIRMED approach, not a
    guess: InSight (Dascena) -- a commercially deployed sepsis algorithm with
    documented mortality-reduction outcomes at multiple hospitals (Barton et
    al. 2019, Comput Biol Med; Mao et al. 2018, BMJ Open) -- is explicitly
    built from "combinations of vital sign measurements and their changes
    over time," using exactly six vitals: SBP, DBP, HR, RR, SpO2, temperature.
    The exact combination formulas are proprietary; what's replicated here is
    the CONCEPT (pairwise interactions among the same vital-sign set), plus
    the one specific interaction the Wang et al. 2025 review names directly
    (Age x SBP, a confirmed top-10 feature in Camacho-Cogollo et al.'s study
    -- see age_x_sbp() above)."""
    hr = np.asarray(hr, dtype=float); resp = np.asarray(resp, dtype=float)
    sbp = np.asarray(sbp, dtype=float); temp = np.asarray(temp, dtype=float)
    out = {
        "HR_x_Resp": hr * resp,
        "HR_over_Resp": hr / np.where(resp != 0, resp, np.nan),
        "Temp_x_HR": temp * hr,
        "SBP_over_Resp": sbp / np.where(resp != 0, resp, np.nan),
    }
    if spo2 is not None:
        spo2 = np.asarray(spo2, dtype=float)
        out["SpO2_over_HR"] = spo2 / np.where(hr != 0, hr, np.nan)
    return out


def build_medical_index_and_trend_features(df: pd.DataFrame, windows=(3, 6)) -> pd.DataFrame:
    """Given one patient's causal (forward-filled), hour-sorted dataframe with
    columns HR, SBP, DBP, Resp, Temp, WBC, BUN, Creatinine, Age, and
    optionally GCS, PaCO2, Platelets, Bilirubin_total -- returns all Medical
    Index features (point-in-time) plus Change/Trend (slope) features for the
    key vitals, exactly the two feature categories the review found to help.
    """
    g = df.sort_values("Hour").reset_index(drop=True) if "Hour" in df.columns else df.reset_index(drop=True)
    out = {}

    hr = g["HR"].astype(float).values
    sbp = g["SBP"].astype(float).values
    dbp = g["DBP"].astype(float).values
    resp = g["Resp"].astype(float).values
    temp = g["Temp"].astype(float).values
    wbc = g["WBC"].astype(float).values
    bun = g["BUN"].astype(float).values
    creat = g["Creatinine"].astype(float).values
    age = g["Age"].astype(float).values if "Age" in g.columns else np.zeros(len(g))
    gcs = g["GCS"].astype(float).values if "GCS" in g.columns else None
    paco2 = g["PaCO2"].astype(float).values if "PaCO2" in g.columns else None

    map_ = mean_arterial_pressure(sbp, dbp)
    out["MAP"] = map_
    out["ShockIndex"] = shock_index(hr, sbp)
    out["BUN_Creatinine_Ratio"] = bun_creatinine_ratio(bun, creat)
    out["Age_x_SBP"] = age_x_sbp(age, sbp)
    out["qSOFA"] = qsofa(resp, sbp, gcs)
    out.update(sirs_criteria(temp, hr, resp, wbc, paco2))

    if "Platelets" in g.columns and "Bilirubin_total" in g.columns:
        sofa = sofa_components(g["Platelets"].astype(float).values,
                               g["Bilirubin_total"].astype(float).values,
                               map_, creat, gcs)
        out.update(sofa)
        out["highest_sofa_score"] = highest_score_so_far(sofa["sofa_total_partial"])

    for name, series in [("HR", hr), ("MAP", map_), ("Resp", resp), ("Temp", temp)]:
        for w in windows:
            out[f"{name}_slope{w}"] = rolling_slope(series, w)
            out[f"{name}_var{w}"] = rolling_variance(series, w)
            out[f"{name}_skew{w}"] = rolling_skewness(series, w)

    spo2 = g["O2Sat"].astype(float).values if "O2Sat" in g.columns else None
    out.update(pairwise_vital_interactions(hr, resp, sbp, temp, spo2))

    return pd.DataFrame(out)


# ============================================================================
# Causality self-test: corrupt future raw values, rebuild, confirm no change
# ============================================================================

def assert_medical_index_causal(df_one: pd.DataFrame, windows=(3, 6)):
    g = df_one.sort_values("Hour").reset_index(drop=True) if "Hour" in df_one.columns else df_one.reset_index(drop=True)
    n = len(g)
    if n < 4:
        return True
    base = build_medical_index_and_trend_features(g, windows).values
    rng = np.random.default_rng(0)
    numeric_cols = [c for c in g.columns if c != "Hour" and pd.api.types.is_numeric_dtype(g[c])]
    for t in np.linspace(1, n - 2, num=min(5, n - 2), dtype=int):
        c = g.copy()
        fut = c.index > t
        for col in numeric_cols:
            c.loc[fut, col] = rng.normal(1e3, 1e3, int(fut.sum()))
        rebuilt = build_medical_index_and_trend_features(c, windows).values
        d = np.abs(np.nan_to_num(base[: t + 1]) - np.nan_to_num(rebuilt[: t + 1]))
        assert d.max() < 1e-8, f"LEAK at t={t}: feature changed by {d.max():.2e}"
    return True


if __name__ == "__main__":
    print(__doc__)
