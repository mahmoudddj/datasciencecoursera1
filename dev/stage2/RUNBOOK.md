# From here to the final run: the step-by-step runbook (1 Nov 2026)

Every step below is either yours (Colab, signatures, people) or mine (code and documents). Nothing trains on the full cohort before step 6. Standing rules throughout: Run all only, one heavy notebook at a time, `FORCE_*` False, `RELEASE_FINAL_HOLDOUT` False until step 9, no edits to a running notebook, no Gemini edits, aggregates only in chat (counts under 11 masked), data only in the credentialed owner's account.

## Step 0. Housekeeping (you, today)

- Pull the branch `claude/tender-keller-5szu1g`; the notebook is `Sepsis_V11_Improved_MIMIC_eICU_14_stage2.ipynb`.
- Check free space on the project Drive: at least 300 GB (the all-comers feature shards are roughly ten times the 10,000-stay build).
- Note the stage-1 cohort root on Drive for the 10,000-stay plans, `sepsis_colab_project/cohorts_v9/<key>/sepsis`; it goes into `STAGE2_REUSE_LABEL_ROOTS` so the completed label batches are reused.
- Read the live Colab unit rate once a runtime is attached (Resources pane). It decides the Colab-versus-cloud question after arm 1.

## Step 1. Consultant survey (you, start now; runs in parallel with steps 2 and 3)

- Insert the ethics reference (an exemption or expedited review for an anonymous professional survey) in the invitation of `dev/consultants/Consultant_Survey.docx`.
- Decide the sample: the participating units only, or also through a national society. Minimum 30 complete responses for the publishable report; fewer still settle the three protocol choices.
- Distribute; collect; send me the anonymous responses as a table (no names). The appendix of the survey gives the adoption rule for each of the three choices; I apply them and write the results into protocol item 12.

## Step 2. Full-release data build (you on Colab, 2 to 3 days of CPU runtime; no model trained)

Settings in cell 1 of `_14_stage2` before Run all:

| Setting | Value |
|---|---|
| `RUN_MODE` | `'full'` |
| `FULL_SAMPLE_STAYS_PER_DATASET` | `None` |
| `STAGE2_ARMS` | `[]` (data build only; the notebook writes `DATA_BUILD_ONLY.json` and trains nothing) |
| `STAGE2_REUSE_LABEL_ROOTS` | `['/content/drive/MyDrive/sepsis_colab_project/cohorts_v9/<stage-1 key>/sepsis']` |
| `LOCAL_DATA_COPY` | `True` |
| `LABEL_PARALLEL_BATCHES` | `8` (the RAM guard lowers it to what the runtime allows, about 3 on the 51 GB CPU runtime) |
| everything else | as committed |

- Runtime: CPU, high RAM. Run all. When the 24-hour limit stops the session, reattach and Run all again; every label batch and feature batch resumes from its marker.
- Optional, saves about two days: run the same cells on a Google Cloud 32-core, 256 GB machine for about one day (about $25) after I have tested the environment rebuild on the fixture there. Only worth it if the Google account is yours and the data stay in it.
- Send me the printed cell outputs (attrition by batch, the index table by database and incident status, the stage-2 table summary, the manifest audit). I check the counts before anything else runs.

## Step 3. Full-release pathophysiology repeat (built; you run it on CPU, hours)

- `Sepsis_V11_Improved_MIMIC_eICU_15_pathophysiology_full.ipynb` (built by `dev/tools/build15.py` from `_14`; fixture run passed) reuses the `_14` data stages by key and runs the `_13` study on the full release, training-split and non-cohort patients only. Early-ICU-onset stays with pre-onset hours are read from the all-comers cohort index; stays septic at or before arrival (no pre-onset hours, not in the index) from the unlabelled corpus as before. Run it after step 2 with the same cell-1 paths; `STAGE2_ARMS` is unused there.
- You run it once on the CPU runtime and send me the aggregate outputs and figures.
- From it I fix the shared physiology set (protocol item 2(b)) and decide whether the deterioration target (item 11) is prespecified, by the rules already in Section 10c.1.

## Step 4. Write the decisions in (me, one day after steps 1 and 3)

- Protocol item 12: the consultants' answers and the three resulting values (credit for post-antibiotic warnings; course definition; alert level and budget).
- Protocol item 2(b): the shared physiology set; `STAGE2_SHARED_PHYSIOLOGY` in the notebook.
- Section 15 decisions, confirmed by you and the partner: the training split (observer-fit patients join training, or not) and the leave-hospital-out grouping (hash-selected 20 % of eICU development hospitals).
- `STAGE2_BEST_NON_PROJECT_ARM` stays `two_channel` unless you decide otherwise.
- The final `PRIOR_TEST_EXPOSURE` text: everything viewed to date, including the stage-1b validation rows and both pathophysiology runs.
- Rebuild `_14_stage2`, rerun the fixture gate, commit.

## Step 5. Freeze: sign, hash, register (you and the partner, one sitting)

1. On the commit from step 4, run `python3 dev/tools/freeze_record.py` from the repository root. It writes `FREEZE_RECORD.md` with the SHA-256 of the protocol, the notebook, every module and the survey, and the exact commands. Commit that file.
2. Each of you signs a tag on that commit with your own key (SSH signing is the simplest: `git config --global gpg.format ssh`, `git config --global user.signingkey ~/.ssh/id_ed25519.pub`, then `git tag -s protocol-freeze-<date>-candidate` and `-partner`). Push both tags. `git tag -v` verifies them.
3. Export the protocol to PDF (`pandoc PROTOCOL.md -o Study_Protocol_frozen.docx`, then save as PDF) and open an OSF registration: attach the PDF and `FREEZE_RECORD.md`, enter the commit and the two tag names. Record the registration DOI in `FREEZE_RECORD.md`. (A Zenodo snapshot of the repository is the alternative if you prefer a repository DOI.)
4. The next commit sets `PROTOCOL_FROZEN = True` and `PROTOCOL_FREEZE_TAG` in cell 1; I rebuild the notebook. The notebook refuses full-cohort training without both.
5. From this point any change goes to `PROTOCOL_DEVIATIONS.md` with its date and reason; the code is not edited between runs.

## Step 6. Arm 1, the project model (you on Colab, about 3 to 4 days of A100)

- Settings: `STAGE2_ARMS = ['project']`, `PROTOCOL_FROZEN = True`, A100 runtime. Run all. Reattach and Run all after each 24-hour stop; arms resume from `last.pt`.
- Send me `team_summary/` (tables, figure, digest) and `run_protocol.json`. Validation rows and, now that the protocol is frozen, the development test rows are reported; the sealed 20 % holdout is still untouched.
- Record the live unit rate and the epoch time printed in `stage2.log`.

## Step 7. Decide where the rest runs (you, after arm 1)

- Unit rate about 5 to 6 per hour: stay on Colab for everything; expect about $150 to $250 beyond the subscription.
- Unit rate about 13 per hour and a Google Cloud account in your name with A100 quota: arms 2 to 5 on a spot A100 there (I prepare the machine image and test it on the fixture first); arms 6 to 9 stay on Colab.
- Otherwise buy units (about $300 in total) and stay on Colab.

## Step 8. Arms 2 to 9 in order (you, 8 to 10 days of A100 plus a CPU day for the tabular benchmarks)

- Extend `STAGE2_ARMS` one arm at a time in the section-11 order: `two_channel`, `pooled`, `suspicion`, `pretrained` (three seeds each), then `predictor_sets`, `label_stratified`, `benchmarks`, `exploratory` (one seed). Completed arms are skipped on every rerun, so the list can simply grow.
- The `benchmarks` arm's logistic regression and boosted trees want the high-RAM CPU runtime (`TABULAR_MAX_GB`); the GRU-D and TCN parts want the GPU. Run that arm twice if needed; each part keeps its marker.
- If the budget runs out, cut from the end (`exploratory` first, then `benchmarks`), and record the cut in `PROTOCOL_DEVIATIONS.md`.
- After each arm, send me the team summary; I update the results document. No model is chosen on test rows; every prespecified arm is reported.

## Step 9. Open the holdout once (you and the partner, after every arm is reported)

- The development results document is complete and the analysis plan for the holdout (the prespecified cross-database directions) is agreed in writing.
- `RELEASE_FINAL_HOLDOUT = True`, run once, report as written; the setting goes back to False afterwards.

## Step 10. After the results

- The full-cohort pathophysiology study (item 18), unblinded and including the holdout, as discussion material.
- Reporting with TRIPOD+AI and PROBAST+AI; the consultant survey as its own report under CHERRIES or CROSS.
- The hospital-aware arm stays postponed to the discussion, as decided.

## What I do next, in order

1. Apply the consultants' answers and the shared physiology set when they arrive (step 4), rebuild, rerun the gate, and hand you the commit for the freeze (step 5).
2. The Google Cloud environment test on the fixture only if step 7 calls for it (Colab is the working assumption).
