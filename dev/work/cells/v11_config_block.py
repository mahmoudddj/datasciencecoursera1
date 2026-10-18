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
