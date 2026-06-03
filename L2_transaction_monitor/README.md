# L2: Transaction Monitor

This layer uses four Azure Functions running in parallel to perform deterministic checks on the transaction data.

- **T1: Velocity**: 90-day history, structuring detection.
- **T2: Watchlist**: FIU-IND sanctioned entities fuzzy match.
- **T3: Risk score**: Account age, history, flags, risk tier.
- **T4: Geo anomaly**: Location vs historical pattern, moving average of account state.

A weighted scoring formula combines the outputs of these checks into a single suspicion score.

## Current T3 prototype

`T3` now supports a first-pass spreadsheet-driven risk analysis flow:

- Loads `.xlsx`, `.csv`, or `.tsv` input and converts rows into normalized JSON.
- Runs local fault detection for missing fields, new accounts, prior flags, KYC issues, high-risk tier, and similar signals.
- Optionally sends the normalized JSON plus local findings to `Phi-4-mini` through Ollama for a structured risk verdict.
- Falls back to a heuristic score if Ollama is unavailable.
- When no `--tx-id` is provided, evaluates the entire dataset and reports row-level faults plus accuracy and macro F1 against the benchmark labels in the sheet.

Example run:

```bash
/Users/nihalraviganesh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  L2_transaction_monitor/t3_risk_score.py \
  --spreadsheet /path/to/sample.xlsx
```

Single-row run:

```bash
/Users/nihalraviganesh/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  L2_transaction_monitor/t3_risk_score.py \
  --spreadsheet /path/to/sample.xlsx \
  --tx-id 19
```

Optional environment variables:

- `OLLAMA_BASE_URL` - defaults to `http://localhost:11434`
- `OLLAMA_MODEL` - defaults to `phi4-mini`
- `RISK_SCORE_SHEET_NAME` - optional default Excel sheet name
