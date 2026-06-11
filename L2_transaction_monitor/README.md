# L2: Transaction Monitor

This layer uses six Azure Functions running in parallel to perform deterministic checks on the transaction data.

## Category 1: Velocity & Structuring (C1)
- **C1**: Detects sub-threshold splitting over time windows. Uses windowed-aggregation engine parameterised by rail and threshold for structuring detection.

## Category 2: Sanctions & Watchlist (C2)
- **C2**: Standalone deterministic ID cross-reference against FIU-IND watchlists using fuzzy matching (rapidfuzz).

## Category 3: Graph Network Flow (C3)
- **C3**: Directed-graph traversals over Cosmos transaction edges. Depth-1 fan-in/fan-out analysis with shared graph-building primitive for depth-≤3 round-trip traversals.

## Category 4: Account Risk & Dormancy (C4)
- **C4**: Account-level scoring based on age, KYC level, and activity history. Owns dormancy detection signal.

## Category 5: Cross-Border / FEMA-LRS (C5)
- **C5**: Standalone check for PAN-level YTD outward-remittance aggregation against FEMA-LRS ceiling enforcement.

## Category 6: Geo-Anomaly (C6)
- **C6**: Transaction location vs the account's historical geographic pattern. Uses moving average of account geographic state.

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
