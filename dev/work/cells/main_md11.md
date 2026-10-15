## 5. Build availability-aware features
Raw-table events are staged once per cohort (`raw_stage_v10/<key>`); hourly features are built in resumable batches. Every predictor has an observed-value mask; measured channels also carry measurement age. The registry and coverage audit below stop the run if a core channel was never captured.
