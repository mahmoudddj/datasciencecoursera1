# Prompt for a new Claude session: target trial emulation side project

Copy everything below the line into a new conversation together with the files `TTE_IDEAS.md`, `TTE_Feasibility_MIMIC_eICU.ipynb`, `tte_feasibility_cells.py`, `build_tte_notebook.py` and `test_tte_synthetic.py`.

---

I am a clinical pharmacist and PhD candidate. My PhD is an early sepsis warning model on MIMIC-IV 3.1 and eICU-CRD 2.0 (both PhysioNet, credentialed access, data use agreement signed). This is a separate side project on **causal inference by target trial emulation** using the same two databases. The sepsis work is out of scope here; do not ask about it.

**What exists.** `TTE_IDEAS.md` lists eight candidate target trials (early vasopressors, balanced crystalloid vs saline, hydrocortisone in shock, dexmedetomidine vs propofol, PPI vs H2RA, transfusion thresholds, RRT timing, antibiotic timing after the first culture), a benchmarking paper that emulates published ICU trials in both databases, and two eICU-specific ideas (hospital preference as an instrument; transportability from MIMIC-IV to eICU). `TTE_Feasibility_MIMIC_eICU.ipynb` is a Colab notebook that reads the raw PhysioNet tables from my Google Drive with DuckDB and writes one CSV of aggregate counts per question and database (eligible stays, both arms, deaths per arm, timing, hospitals contributing). Its queries were tested on synthetic tables with the real column names (`test_tte_synthetic.py`), never on the real data from the assistant's side.

**Where the data are.** On my Google Drive: MIMIC-IV 3.1 at `/content/drive/MyDrive/mimic-iv-3.1/mimic-iv-3.1` (folders `hosp/` and `icu/`, gzipped CSV), eICU-CRD 2.0 at `/content/drive/MyDrive/eicu-collaborative-research-database-2.0/eicu-collaborative-research-database-2.0`. A demo MIMIC folder also exists on the Drive and must never be used. The notebook auto-locates both or takes `TTE_MIMIC_ROOT` / `TTE_EICU_ROOT`. If a Colab local copy exists at `/content/local_raw`, it is preferred (faster).

**Rules you must keep.**
1. Patient-level data never leave the Colab runtime. In chat you receive and discuss aggregate tables only; counts below 11 are masked. Never ask me to paste rows.
2. Every emulation gets a written protocol with the seven target-trial components (eligibility, strategies, assignment, time zero, outcome, follow-up, causal contrast, analysis plan) **before** any outcome is computed. Time zero must coincide with eligibility and strategy assignment. Immortal time is handled by cloning-censoring-weighting or sequential trials, never by comparing survivors.
3. No peeking: feasibility counts (exposure and outcome totals) are allowed; effect estimates are computed once per prespecified protocol.
4. Report with the TARGET guideline for emulations and STROBE; include negative-control outcomes and a quantitative bias analysis.
5. I run all notebooks myself on Colab and paste back printed aggregates. You write code, I execute. Always "Run all" instructions; never partial cells.
6. No model identifiers or chat links in any file I would share.

**What I want from you, in order.**
1. Read `TTE_IDEAS.md`. Ask me which questions interest me most (my interest is causal inference methods applied to ICU pharmacotherapy; vasopressors, steroids, sedation and antibiotics are closest to my practice).
2. Tell me to run the feasibility notebook and paste the table. Interpret it: which questions are feasible in which database, and why some fail (missing exposure records, few events, no time zero).
3. For the two or three strongest questions, write the full target trial protocol as a document (one per question), then the analysis plan, then the Colab notebook that builds the emulation cohort from the raw tables (eligibility at every hour, clones, censoring indicators, hourly covariates for the weight models), using DuckDB for extraction and Python for the weighting. Reuse the feasibility notebook's table views and patterns.
4. Propose the benchmarking paper (emulate published ICU trials in both databases and compare with the trials' estimates) as the first manuscript, with a protocol I can preregister on OSF.
5. Keep a `DECISIONS.md` with every design decision and its date.

Start by summarising back to me, in one paragraph, what this project is and what the first three steps are, then ask your questions.
