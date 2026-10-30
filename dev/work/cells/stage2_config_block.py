# ---- STAGE 2 (protocol section 11 and 10c.2; built 31 Oct 2026, before the freeze; nothing here runs on real data before the signed tag) ----
STAGE_2 = True                                     # the stage-2 driver (v12_train.run_stage2) replaces the stage-1 fold driver
STAGE2_ARMS = ['project','two_channel','pooled','suspicion','pretrained','predictor_sets','label_stratified','benchmarks','exploratory']   # section 11 order; remove from the END to cut the budget
STAGE2_KEEP_EARLY_ONSET = True                     # all comers: YAIB exclusion 7 (onset before ICU hour 6) is not applied; the index flags Incident vs ArrivalSepsis
STAGE2_LABEL_VARIANTS = {'miiv':'abx','eicu':'and'} # item 10 (a),(b): antibiotic-only label on MIMIC-IV, culture-paired label on eICU; labels phase only, own cache
STAGE2_REUSE_LABEL_ROOTS = []                      # earlier .../cohorts_v9/<key>/sepsis roots whose completed LABEL batches are carried over (the 20,000 labelled candidates)
STAGE2_SUSPICION_HORIZON = 3                       # item 9: 3 h before the first continued antibiotic course (6 h reading as a scoring pass)
STAGE2_TRAIN_INCLUDES_OBSERVER_FIT = True          # the retired observer bank's 30 % development split joins the training split (recorded in run_protocol.json)
STAGE2_SHARED_PHYSIOLOGY = ['Albumin','HR','Lymphocytes','NEWS2_MetAmongMeasured','NLR','Neutrophils','PTT','Resp','SF_Ratio','Temp','Temp_Max24h','Temp_Min24h','pH','qSOFA_MetAmongMeasured']   # item 2(b), from the 31 Oct run; TO FIX at the freeze from the full-release repeat
STAGE2_BEST_NON_PROJECT_ARM = 'two_channel'        # item 9: the suspicion target also runs on this arm (set before the freeze)
STAGE2_LHO_FRACTION = 0.2                          # eICU leave-hospital-out: hash-selected share of development hospitals held out (TO FREEZE)
STAGE2_FINETUNE_FRACTION = 0.1                     # item 3: target-site fine-tune on 10 % of the other database's training patients
STAGE2_PRETRAIN_EPOCHS = 5                         # item 3: weakly supervised multi-task pretraining epochs
PROTOCOL_FROZEN = False                            # False: test-split rows are written to test_rows_sealed.json and never printed. Set True ONLY in the commit after the signed tag.
PROTOCOL_FREEZE_TAG = ''                           # the signed git tag (recorded in run_protocol.json); required when PROTOCOL_FROZEN is True
