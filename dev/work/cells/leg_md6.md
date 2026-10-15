## 5. Locate data and reuse extraction
Identical to the main notebook (same cohort keys, so existing ricu imports and YAIB cohorts are reused). The strict CSV parser, RAM watchdog, balanced batches, Python 3.10/R 4.2.2 pins and eICU nested-dictionary repair are unchanged. A dictionary preflight message is not evidence of clinical labels; check `labels_complete.json` and the worker logs.
