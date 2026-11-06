# The sepsis early-warning model landscape: what was built, what was deployed, what failed, and why

Drafted 6 Nov 2026 for the core-set design work (Stage 2, predictor-set arms). Candidate for a
standalone review paper after full-text verification of every row. This document informs the
design of the prespecified "core" predictor-set arm; it does not change the protocol.

**Method and caveats.** Built from targeted literature searches (6 Nov 2026) plus the project's
pre-freeze review. Figures below are taken from abstracts, published summaries and press
coverage; before any external use, every number must be re-verified against the full text.
AUROCs are **not comparable across rows**: the label (Sepsis-3, SIRS-era severe sepsis, CMS
SEP-1, "sepsis phenotype within 4 h"), the cohort (ED, ward, ICU), the prediction horizon, and
the evaluation design (full-window vs. onset-time) all differ. The table is for *lessons*, not
for a league table of AUROCs.

---

## Part 1 — Bedside scores (the incumbents every model is really competing with)

| Score | Inputs | Strengths | Weaknesses |
|---|---|---|---|
| SIRS | 4 (temp, HR, RR, WBC) | Simple; sensitive | Very non-specific: fires on flu, pancreatitis, post-op inflammation; abandoned as a sepsis definition by Sepsis-3 |
| qSOFA | 3 (RR, SBP, GCS) | No labs at all; Sepsis-3 endorsed for screening outside ICU | Insensitive early — often positive only when the patient is already deteriorating; poor as an *early* warning |
| MEWS | 5 vitals | Ubiquitous on paper charts | Not sepsis-specific; threshold-based, no trend information |
| NEWS2 | 7 bedside items | **Mandated across the NHS**; nurses chart every input anyway; proven deterioration signal | Not sepsis-specific; single-timepoint, ignores trajectory; alarm burden at sensitive thresholds |
| SOFA | 6 organ systems, needs labs + blood gas + vasopressor dose | Defines the Sepsis-3 label | Needs ICU-grade data (PaO2, bilirubin, creatinine, platelets, GCS, MAP/pressors); a *definition*, not an early warning |

**Lesson:** the incumbents won on *availability*, not accuracy. Any replacement must be at least
as available as NEWS2 to be adopted on a ward, and must beat it clearly on lead time and
precision to justify the change.

## Part 2 — Machine-learning systems

| System (year, group) | Setting | Inputs | Algorithm | Headline performance (as published; see caveats) | Deployment status | What worked | Drawbacks / failure mode |
|---|---|---|---|---|---|---|---|
| InSight / Dascena (2016–2018) | ICU, ward, ED | **6 vital signs** (2018 version); ~8 bedside measurements (2016 Sepsis-3 version) | Gradient boosting on discretized vital-sign tuples | AUROC >0.90 for sepsis screening (SIRS-era label, multicenter retrospective); 0.88 at onset for Sepsis-3 (2016); graceful degradation under 60 % random input deletion | Commercial pilots; several small RCTs (mortality/LOS improvements reported by the vendor's own trials) | Proof that **vitals alone carry most of the screening signal**; explicit robustness-to-missingness testing | Vendor-led evidence base; SIRS-era labels inflate comparability; limited independent prospective validation; company later pivoted |
| Epic Sepsis Model v1 (deployed ~2017→) | Inpatient, all Epic customers | ~80+ EHR variables incl. practice signals | Penalized logistic regression (proprietary) | External validation (Michigan, 2021): AUROC 0.63, sensitivity 33 %, PPV 12 % | **Deployed at hundreds of hospitals before any independent validation** | Zero-effort integration (ships inside the EHR) — the strongest distribution channel in the field | The field's cautionary tale: proprietary opacity; trained partly on *treatment-contaminated* labels (clinician suspicion baked in); collapsed on independent evaluation; high alert burden; missed 67 % of cases |
| Epic Sepsis Model v2 (2024–2026) | Inpatient, 4 health systems | EHR variables (revised) | Proprietary GBM | Prospective multicenter: encounter-level AUROC 0.82–0.92 but **PPV 13–26 %**, high alert burden, large between-site variability | Deployed | Shows discrimination is fixable in-vendor | **PPV is the binding constraint, not AUROC**; between-site variability survived the redesign |
| TREWS (Johns Hopkins / Bayesian Health, 2015–2022) | ED + ward + ICU, 5 hospitals | EHR-wide (labs, vitals, history, notes-derived) | Cox-based / ML survival model | 82 % of sepsis cases identified; **89 % of alerts evaluated by a provider**; alert confirmed <3 h → ~1.9 h faster antibiotics | Prospective 2-year, 5-hospital study (Nature Medicine 2022) | **Every alert shows the triggering factors**; human-machine teaming (clinician confirms/dismisses with feedback); workflow placement | Needed a large vendor-supported programme; adoption study is observational, not an RCT; feature breadth makes portability costly |
| COMPOSER (UCSD, 2021–2024) | ED → inpatient | ~150 variables | Deep learning + **conformal "indeterminate" output** | Retrospective AUROC 0.92–0.95; deployment study: 1.9 % absolute (17 % relative) sepsis mortality reduction, +5 % bundle compliance (quasi-experimental) | Live at 2 UCSD EDs since Dec 2022, expanding | Learning to say **"I don't know"** on out-of-distribution patients cut false alarms; nurse-facing workflow | Mortality evidence is before/after causal inference, not randomized; 150-variable interface limits portability; authors have a commercialization COI |
| Sepsis Watch (Duke, 2018–2024) | ED, inpatient | 86 variables, curated | Deep learning (RNN) | Internally strong (sepsis phenotype within 4 h) | Live since Nov 2018; RRT-nurse-operated | **Two+ years of socio-technical work**: frontline nurses co-designed workflow; nurse-to-physician communication protocols; the 2024 lifecycle paper documents maintenance burden honestly | Heavy human infrastructure (dedicated RRT watchers) — most hospitals cannot staff this; model itself not the bottleneck |
| NAVOY Sepsis (AlgoDx, Sweden, 2020–2024) | ICU | **20 variables** | ML (gradient boosting) | Prospective RCT (n=304, Skåne): ~3 h earlier Sepsis-3 flagging, accuracy ~0.79; health-economic case (~€76/patient saved) | CE-marked software-as-medical-device; RCT-validated | One of the few **randomized** validations in the field; deliberately small variable set for portability; regulatory path done properly | Small trial; ICU-only; modest accuracy headline; adoption beyond trial sites unclear |
| KATE Sepsis (Mednition, 2022) | ED **triage** | Triage-moment data only | ML (GBM) | AUROC 0.94, sens 71 %, spec 95 % (retrospective, 16 hospitals) | Pilots | Predicting at a **fixed decision moment** (triage) rather than continuously — matches a real workflow slot | No prospective outcome evidence yet; triage-only scope |
| SERA (Singapore, 2021) | ED/inpatient | Structured data + **unstructured clinical notes** (NLP) | Two linked algorithms (diagnosis + early prediction) | Up to +32 % early detection, −17 % false positives vs. physician prediction (retrospective) | Not deployed (as of search) | Notes carry real signal (clinician suspicion precedes labs) | Notes-dependence kills cross-hospital portability (language, templates, documentation culture); no prospective evidence |
| PhysioNet/CinC Challenge 2019 cohort (104 teams) | ICU (3 hospital systems, 1 sequestered) | 40 provided variables | Mostly GBM ensembles; winner used path-signature features | Winner chosen on **clinical utility score** (lead-time-weighted), not AUROC | n/a (research) | Standardized a *utility* metric (early credit, light FP penalty, heavy miss penalty); forced honest hidden-test evaluation | **Every top model degraded sharply on the sequestered third hospital** — the clearest public demonstration that site-specific practice signal, not physiology, drives much of the apparent performance |
| Multi-site deep learning (Moor et al., eClinicalMedicine 2023; and successors) | ICU, multi-national | Harmonized channels across 4+ databases | Deep learning | Good internal AUROCs; consistent **drop on external sites**; hand-crafted features + classical models approached deep models | Research | Honest external-validation design; showed feature engineering ≈ deep learning when done carefully | Confirms the transfer gap is the field's central unsolved problem |
| Geriatric/localized EWS validations (2025 reviews) | Various | Various | Various | External validation "frequently exhibited a decline in performance relative to development cohorts"; only ~15 % of published models ever validated outside their home institution | Mostly never deployed | — | **Publication without external validation is the modal outcome of the field** |

## Part 3 — Cross-cutting lessons (why models fail)

1. **Nobody dies of a low AUROC; they die of an ignored alert.** ED sepsis-alert PPVs of
   5.8–54 % are reported across studies; general EHR alert override rates run as high as
   49–96 %. ESM v2 *fixed discrimination* (0.82–0.92) and still has PPV 13–26 % with high alert
   burden. The binding constraint is precision at the operating point and alerts-per-nurse-per-shift
   — our utility metric and alarm-fraction operating points are the right currency, and every
   hospital-facing claim should be stated in it.
2. **Site-specific practice signal masquerades as performance.** The CinC-2019 sequestered
   hospital, the Epic v1 collapse, and the multi-site deep-learning literature all show the same
   mechanism: models learn *when this hospital measures things* (ordering patterns, charting
   cadence) rather than physiology, then fail where practice differs. Any channel whose signal
   is mostly "someone decided to order this test" is a portability liability.
3. **Treatment/label contamination.** Epic v1 trained toward labels that embed clinician
   suspicion (antibiotics, cultures), so it partly re-announced what clinicians already knew —
   late, with extra steps. Predictors that only exist after suspicion (e.g. repeat lactates,
   procalcitonin ordered on suspicion) have the same character in feature form.
4. **Few inputs is a deployment feature, not a scientific compromise.** The systems with real
   prospective evidence cluster at the small end: InSight (6), NAVOY (20), KATE (triage-moment
   data), NEWS2 (7). Every EHR variable is an interface to map, validate, monitor for upstream
   schema drift, and re-validate after every EHR upgrade. The 150-variable systems that succeeded
   (COMPOSER, TREWS, Sepsis Watch) each needed a multi-year, vendor- or institution-scale
   integration programme that a typical hospital cannot buy.
5. **The alert must carry its own explanation.** TREWS's 89 % evaluation rate is credited to
   showing the triggering factors on every alert; Duke's adoption came from nurse-co-designed
   workflow. A clinician must be able to verify the inputs at the bedside in under a minute —
   which is only possible if the inputs are things clinicians recognize.
6. **An "I don't know" output is worth more than two AUROC points.** COMPOSER's conformal
   indeterminates are the one genuinely new deployment idea of the last five years: suppressing
   predictions on out-of-distribution patients attacks the false-alarm problem at its root.
7. **Prospective, preferably randomized, evidence is almost absent.** One small RCT (NAVOY),
   one large prospective adoption study (TREWS), one quasi-experimental deployment (COMPOSER),
   a long-running institutional deployment (Duke) — against hundreds of retrospective papers.
   ~15 % of published models were ever externally validated; almost none prospectively.
8. **Workflow placement beats model choice.** Alert acknowledgement went from 3 % to 51 % in
   one study merely by changing the delivery channel (EHR pop-up → paging). Who receives the
   alert, at what moment, with what expected action, matters more than the last decimal of
   discrimination.

## Part 4 — Implications for our core predictor set

- Define the core set by **availability tiers** (ward-chartable vitals; universally drawn routine
  labs), not by importance ranking alone — availability is what made NEWS2, InSight and NAVOY
  deployable, and unavailability is what confines SOFA-grade models to ICUs.
- Keep the engineered temporal machinery (trends, extremes, deltas, score composites) on the
  reduced channels: integration cost is per *channel*, computation is free. This is the gap in
  the literature: small-input systems so far used shallow features; wide systems used deep
  features. A **narrow-input, deep-feature** model is the untested quadrant.
- Exclude mask/ordering-practice channels from the core set (lesson 2); keep measurement age
  (staleness) only.
- Report the core arm in utility and alarm-fraction terms at fixed operating points (lesson 1),
  with the degraded-charting stress test (ward-cadence thinning; random deletion à la InSight).
- Carry the conformal indeterminate output into any hospital-facing description (lesson 6).
- All selection and any parsimony curve on training/validation splits only; the sealed holdout
  stands in for "the next hospital" (lessons 2, 7).

## Sources (to be re-verified against full texts before external use)

- InSight: [JMIR Med Inform 2016](https://medinform.jmir.org/2016/3/e28) · [BMJ Open 2018](https://bmjopen.bmj.com/content/8/1/e017833) · [multicenter preprint](https://www.biorxiv.org/content/10.1101/243964v1)
- Epic ESM v1: [Wong et al., JAMA Intern Med 2021](https://jamanetwork.com/journals/jamainternalmedicine/fullarticle/2781313) · [editorial](https://www.researchgate.net/publication/352593220_The_Epic_Sepsis_Model_Falls_Short-The_Importance_of_External_Validation)
- Epic ESM v2: [multicenter prospective validation (JAMA Netw Open, via abstract)](https://jamanetwork-com.libproxy.ajou.ac.kr/journals/jamanetworkopen/article-abstract/2845595) · [county-ED external validation](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11560849/)
- TREWS: [Henry et al., Nat Med 2022 (adoption)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9512693) · [AMA coverage](https://www.ama-assn.org/practice-management/digital-health/what-it-takes-doctors-trust-ai-triggered-sepsis-alerts)
- COMPOSER: [conformal preprint](https://www.medrxiv.org/content/10.1101/2021.05.06.21256764v1) · [UCSD deployment study coverage](https://today.ucsd.edu/story/study-ai-surveillance-tool-successfully-helps-to-predict-sepsis-saves-lives)
- Sepsis Watch: [JMIR 2020 implementation](https://medinform.jmir.org/2020/7/e15182/PDF) · [qualitative adoption study](https://jmir.org/2020/11/e22421) · [npj Digit Med 2024 lifecycle](https://www.nature.com/articles/s41746-024-01061-4.pdf)
- NAVOY: [RCT, J Crit Care 2024 (PMID 38245375)](https://www.pubmed.gov/38245375/) · [NCT04570618](https://clinicaltrials.gov/study/NCT04570618) · [proof-of-concept](https://formative.jmir.org/2021/9/e28000/PDF)
- KATE: [arXiv 2204.07657](https://arxiv.org/abs/2204.07657); SERA: [Nat Commun 2021](https://www.nature.com/articles/s41467-021-20910-4)
- CinC 2019: [Reyna et al.](https://pubmed.ncbi.nlm.nih.gov/31939789/) · [consensus analysis](https://arxiv.org/pdf/2012.11013)
- Multi-site/transfer: [eClinicalMedicine 2023](https://www.thelancet.com/journals/eclinm/article/PIIS2589-5370(23)00301-2/fulltext) · [arXiv 2107.05230](https://arxiv.org/pdf/2107.05230) · [methodological review, npj Digit Med 2025](https://www.nature.com/articles/s41746-025-01587-1)
- Alert fatigue: [PeerJ 2017 (3 % vs 51 % acknowledgement)](https://peerj.com/articles/3083) · [Frontiers Med 2025 trainee survey](https://www.frontiersin.org/journals/medicine/articles/10.3389/fmed.2025.1660390/full)
