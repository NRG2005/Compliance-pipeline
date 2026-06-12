# C3 — Graph / Network Flow  (weight 0.17)

Absorbs **T5** (mule fan-in/out) and **T9** (PMLA s.3 layering round-trip) over a
single directed 72h transaction graph, built once and traversed twice.

```python
from L2_transaction_monitor.c3_graph_network_flow import run_c3
result = run_c3(case, mode="slm")   # "deterministic" | "slm" | "both"
# -> {"check": "C3_GRAPH_FLOW", "label": 0|1, "verdict", "confidence", "reason", ...}
```

| Module | Responsibility |
|---|---|
| `graph_builder.py` | `TxGraph.from_case` — directed graph + shared-identity helper |
| `patterns.py` | `fan_in_out_features`, `round_trip_features` (measure only) |
| `detector.py` | deterministic baseline (rules → score → binary label) |
| `slm_classifier.py` | phi4 prompt classifier + transparent reference reasoner |
| `thresholds.py` | all C3 policy values (N, ₹5k, 80%, depth, preservation…) |

**Regulatory anchor:** PMLA 2002 s.3 (layering) + Rule 3(1)(D) STR duty; RBI FRM
Master Directions 2024 EWS Clause 8.3; reference tool MuleHunter.AI (RBIH).

Evaluated F1 (real phi4-mini, full dataset): **0.914** vs 0.722 deterministic.
See [`c3_c6_docs/C3_C6_DESIGN.md`](../c3_c6_docs/C3_C6_DESIGN.md) and run
`python L2_transaction_monitor/c3_c6_evaluation/evaluate.py`.
