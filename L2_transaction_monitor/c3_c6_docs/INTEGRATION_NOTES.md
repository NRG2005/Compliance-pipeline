# L2 Integration Notes — making the six-check unit run end-to-end

This branch integrates **C3 (graph/network flow)** and **C6 (geo-anomaly)** into the
dev-branch L2 pipeline, and makes the whole `transaction_monitor` unit actually run.

## TL;DR
Running the unit revealed that, on dev-branch, the aggregator and the six checks
did **not** agree on a contract: `main.py` did `float(cN_res)` but **every** check
returns a dict (or fails to import). The unit could not run as a whole. The fixes
below make it run today and combine all six, with each teammate's check sharpening
as they finish wiring.

Verified: `transaction_monitor(tx)` returns a weighted `suspicion_score` (e.g.
`0.195` on a mule+takeover sample), with C3 and C6 producing real phi4-mini scores.

## The contract every check should meet
The aggregator (`main.py`) calls each check with `transaction_data` and expects a
**[0,1] suspicion score**. To be safe it now accepts:
- a plain `float` in `[0,1]` (what C3/C6 return), **or**
- a `dict` carrying one of `score` / `risk_score` / `composite_score` / `label`.

Checks may be sync or async; the aggregator awaits coroutines. Any import error or
exception is treated as a non-firing `0.0` so one unfinished check never breaks the
unit.

## What changed on this branch

### `main.py` (rewritten — the integration point)
- Defensive imports (`_safe_import`): a check that can't import (flat imports,
  missing deps, `sys.exit`-on-import) is replaced by a 0.0 stub instead of
  crashing the whole module.
- `_run`: calls each check, awaits if it's a coroutine, and routes failures to 0.0.
- `_to_score`: collapses float-or-dict returns into a `[0,1]` score.
- Weights carried over from dev-branch: C1 .15 · C2 .20 · C3 .10 · C4 .35 · C5 .10 · C6 .10.

### C3 / C6 (ours) — fully conformant
- `analyze_graph_network_flow(transaction_data)` and `check_geo_anomaly(transaction_data)`
  are async and return a **float** (SLM confidence when the pattern fires, else 0.0).
- Packages replace the dev-branch stub files `c3_graph_network_flow.py` /
  `c6_geo_anomaly.py`. Full evidence dict still available via `run_c3` / `run_c6`.

### C1 — minimal unblock (owner: C1 dev)
- Converted the package's **flat imports to relative** (`from models import` →
  `from .models import`, etc. across `__init__.py`, `checks.py`, `slm_reasoner.py`)
  so it imports as a subpackage.
- Added the entry name `check_velocity_and_structuring` (async) that the aggregator
  imports — it wraps the existing `run_t1` and returns its dict (`composite_score`).
- **Still needed by C1 owner:** `data/transactions.csv` (loaded at import by
  `cosmos_client.py`); until present, C1 degrades to 0.0.

### C2 — minimal unblock (owner: C2 dev)
- Made the `requests` import graceful (it previously called `sys.exit(2)` on
  import, which killed the whole aggregator). The aggregator path uses the mock
  judge, so `requests` is optional there.
- **Still needed by C2 owner:** `watchlist.csv` next to the module; its entry
  returns a dict with `score` (already aggregator-compatible). Until the CSV is
  present, C2 degrades to 0.0.

### C4 / C5 — unchanged (owners: C4/C5 devs)
- C4 (`calculate_account_risk_and_dormancy`) is async and returns a dict with
  `risk_score` — already compatible. It imports `L3_regulation_interpreter.llm_client`
  and `pandas`; if that chain isn't installed it degrades to 0.0 via `_safe_import`.
- C5 (`fema_lrs_analysis`) is sync and returns a dict with `score` — compatible.
  It needs FEMA-specific fields (e.g. `fx_usd_inr`) on the payload to fire.

### `requirements.txt`
- Added `httpx` (C3/C6 SLM calls). Note C2 needs `requests`, C4 needs `pandas`
  (declared) + the L3/Gemini deps — these are the owners' to confirm.

## Current per-check status (sample run)
| Check | Wired? | Contributes now? | Blocker (owner to resolve) |
|---|---|---|---|
| C1 | ✅ | ⛔ 0.0 | `data/transactions.csv` |
| C2 | ✅ | ⛔ 0.0 | `watchlist.csv` |
| C3 | ✅ | ✅ real phi4 | — |
| C4 | ✅ | ⛔ 0.0 | L3/Gemini deps + spreadsheet/records input |
| C5 | ✅ | ⛔ 0.0 | FEMA fields on payload |
| C6 | ✅ | ✅ real phi4 | — |

The **integration layer is complete and robust** — every check is imported, called,
and combined. Each teammate's check will contribute the moment its data/deps land,
with no further wiring changes.
