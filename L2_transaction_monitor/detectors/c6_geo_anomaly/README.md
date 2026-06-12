# C6 — Geo-Anomaly  (weight 0.10)

Absorbs **T4** (geo-location anomaly). Flags impossible travel between sessions
and sudden high-value activity from a new geo/device cluster, judged against the
account's historical pattern.

```python
from L2_transaction_monitor.c6_geo_anomaly import run_c6
result = run_c6(transaction, account_history, mode="slm")  # "deterministic" | "slm" | "both"
# -> {"check": "C6_GEO_ANOMALY", "label": 0|1, "verdict", "confidence", "reason", ...}
```

| Module | Responsibility |
|---|---|
| `features.py` | `extract_features` — new/rare location, foreign/FATF, impossible travel, new device, balance drain, odd hour (measure only) |
| `detector.py` | deterministic baseline (noisy-OR combine → binary label) |
| `slm_classifier.py` | phi4 prompt classifier + transparent reference reasoner |
| `thresholds.py` | all C6 policy values |

**Regulatory anchor:** a derived behavioural signal with **no dedicated clause**.
Supports the EWS mandate of RBI FRM Master Directions 2024 (Clause 8.3) and the
risk-based approach of the RBI Authentication Mechanisms Directions 2025. Do not
cite as a discrete requirement.

Evaluated F1 (real phi4-mini, full dataset): **0.919** vs 0.732 deterministic.
See [`c3_c6_docs/C3_C6_DESIGN.md`](../c3_c6_docs/C3_C6_DESIGN.md) and run
`python L2_transaction_monitor/c3_c6_evaluation/evaluate.py`.
