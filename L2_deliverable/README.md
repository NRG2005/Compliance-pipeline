# Layer 2 — Transaction Monitor (Agentic AI Compliance Pipeline)

Pure suspicion detection for the Indian-fintech compliance pipeline. Six
detection categories (C1–C6) run **in parallel** for every transaction and are
combined into a single Layer-2 verdict:

- a **flag** (suspicious / not) — raised if *any* category hard-fires
- a **weighted suspicion score** (0–1) using the C1–C6 weights, emitted as the
  continuous signal Layer 3 routes on.

The evaluation reports **one** confusion matrix for the whole Layer-2 layer
against `ground_truth.csv` (not six separate ones).

## Detection categories

| Cat | Detector | Core logic (unchanged) | Weight |
|-----|----------|------------------------|--------|
| C1  | Velocity & Structuring | rolling-window velocity, same-beneficiary structuring, credit-line probing | 0.27 |
| C2  | Sanctions & Watchlist  | two-stage fuzzy + identifier match, PAN/DOB disambiguation, SLM judge for borderline | 0.20 |
| C3  | Graph / Network Flow   | mule fan-in/out + layering round-trip over the transaction network | 0.17 |
| C4  | Account Risk & Dormancy| dormant-reactivation + new-account-high-value | 0.19 |
| C5  | Cross-Border / FEMA-LRS | per-PAN YTD LRS ceiling, gift-ratio, same-beneficiary split, SLM judge for borderline | 0.07 |
| C6  | Geo-Anomaly            | noisy-OR over new-device / new-location / impossible-travel / FATF / balance-drain, travel-profile gated | 0.10 |

## Project layout

```
L2_deliverable/
├─ run_l2.py                      ← run this
├─ requirements.txt
└─ L2_transaction_monitor/
   ├─ orchestrator.py             ← runs C1–C6 in parallel, combines verdict
   ├─ evaluate_l2.py              ← whole-dataset confusion matrix + F1
   ├─ data_layer.py               ← loads the 4 CSVs once, maps columns to each detector
   ├─ c1_adapter.py               ← C1 velocity/structuring (unified-schema)
   ├─ c2_sanctions_and_watchlist.py
   ├─ c3_graph_network_flow/      ← C3 package (detector + graph builder)
   ├─ c4_account_risk_and_dormancy.py
   ├─ c5_fema_lrs.py
   ├─ c6_geo_anomaly/             ← C6 package (detector + features)
   ├─ c1_velocity_and_structuring/← original C1 checks (preserved)
   ├─ transactions.csv            ← 2000 transactions to classify
   ├─ account_details.csv         ← per-account metadata
   ├─ case_history.csv            ← 90-day prior activity per account
   ├─ watchlist.csv               ← sanctions / watchlist entities
   └─ ground_truth.csv            ← labels (is_suspicious, category, scenario)
```

## How to run in VS Code

1. Open the `L2_deliverable` folder in VS Code (`File → Open Folder…`).
2. Open a terminal (`Terminal → New Terminal`). Make sure you are *inside*
   `L2_deliverable`.
3. (Recommended) create and activate a virtual environment:
   - **Windows**: `python -m venv .venv` then `.venv\Scripts\activate`
   - **macOS/Linux**: `python3 -m venv .venv` then `source .venv/bin/activate`
4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
5. Run the evaluation:
   ```
   python run_l2.py
   ```
   Quick smoke run: `python run_l2.py --limit 200`
   List misclassified transactions: `python run_l2.py --errors`

You should see a confusion matrix followed by precision / recall / F1 / accuracy
and a per-category contribution breakdown.

## The SLM (Phi-4-mini) judge

C2 and C5 use a two-stage design: a deterministic Stage 1, then a small-language-
model judge for borderline cases. The judge call sites are unchanged. If a local
**Ollama** server is running with `phi4-mini` pulled, the live model is used; if
not, the bundled deterministic mock judge runs in its place so the pipeline is
fully runnable offline. No code change is needed either way.

## Notes

- The detectors' core detection logic is preserved from the original L2 build.
  What changed for the unified dataset is the **data-loading layer**
  (`data_layer.py` + per-category adapters), which maps the unified CSV column
  names onto the shape each detector expects.
- A small number of residual errors are intentional boundary cases (e.g. the
  first transaction in a velocity burst, the ~4.8× gift-ratio control case) and
  are left rather than overfit away.
- Regulatory citations per category follow the Layer-2 detection-category spec
  (RBI / FIU-IND / FEMA / NPCI).
