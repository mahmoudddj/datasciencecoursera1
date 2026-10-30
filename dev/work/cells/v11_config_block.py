# ---- V11 (19 Oct 2026; every item prespecified before any _11 result) ----
V11_ARMS = ['osta','output_fusion','cnn','logistic','boosted_tree','signature_boosted_tree',   # kept / literature benchmark
            'flat_osta','grud','tcn','cnn_osta','event_osta',                                  # new supervised arms (flat_osta = organ ablation)
            'ssl_cnn_osta','ssl_cnn_flat','hazard_ssl_cnn_osta',                               # self-supervised, site encoder
            'ssl_cnn_osta_pooled','ssl_cnn_flat_pooled']                                       # self-supervised, pooled encoder (adaptation)
V11_PRIMARY_LOSS = 'utility_weighted_bce'          # 'bce' | 'tls' | 'utility_weighted_bce'; original OSTA loss retired (see _9/_10)
V11_COMPARISON_LOSSES = ['bce','tls']              # run on V11_LOSS_COMPARISON_ARMS only; selection rule = validation utility + AUPRC rank-average
V11_LOSS_COMPARISON_ARMS = ['osta','ssl_cnn_osta']
V11_SSL_EPOCHS = 5                                 # self-supervised pretraining epochs on the unlabelled corpus
V11_SSL_MAX_STAYS_PER_DATASET = 75000              # unlabelled stays per database (never cohort stays; protected patients excluded)
V11_FEATURE_WORKERS = max(1,(os.cpu_count() or 2)-1)
V11_BATCH = 32                                     # was 8; one prespecified change for every neural arm
V11_DROPOUT = 0.2; V11_WEIGHT_DECAY = 1e-4         # one prespecified regularisation step (the _9 histories peaked at epoch 1-3)
V11_TREE_MAX_ITERATIONS = 1000                     # boosted trees: patient-grouped early stopping on the validation split
RUN_TRANSFER_EVALUATION = True                     # each database's model scored on the OTHER database's development patients (holdout sealed)
RUN_NO_PROXY_SENSITIVITY = True                    # osta without hydrocortisone / imaging / prophylaxis (clinician-suspicion proxies)
# ---- STAGE 1b (protocol section 10b, 24 Oct 2026; decided after the stage-1 results, blind to the test splits) ----
STAGE_1B = True                                    # True: train only STAGE1B_ARMS x STAGE1B_INPUT_DROPOUT with plain BCE; report VALIDATION only; test rows sealed on disk
STAGE1B_ARMS = ['flat_osta','flat_osta_heads']     # flat backbone vs flat backbone + seven organ heads (uncertainty-weighted)
STAGE1B_INPUT_DROPOUT = [0.0,0.1,0.2]              # predictor groups (value+flag+age) hidden together during training
STAGE1B_LOSS = 'bce'                               # the stage-2 loss by the section 10 rule (first in 3 of 4 validation comparisons)
STAGE2_OPERATING_POINT = 'quantile'                # decided by rule 10b.2.3 on run b9b18c8632cf33d0 (31 Oct 2026); 'absolute' was the V11 default
STAGE2_PERSISTENCE = 2; STAGE2_FRESH_ONLY = False  # decided by rule 10b.2.4 on run b9b18c8632cf33d0 (31 Oct 2026): persistence 2 h, all hours
STAGE2_PROJECT_MODEL = 'flat_osta'; STAGE2_INPUT_DROPOUT = 0.0   # decided by rule 10b.2.1 on the same run; organ heads not supported, not re-tested

