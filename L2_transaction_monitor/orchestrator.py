"""
orchestrator.py  —  Layer 2 Transaction Monitor (unified)

Runs the six detection categories C1–C6 in parallel for one transaction, against
the unified dataset, and combines them into:

  * a hard FLAG  (suspicious / not) — raised if ANY category hard-fires
  * a weighted suspicion score (0–1) using the spec's C1–C6 weights, emitted as
    the continuous signal that Layer 3 routes on and ranks by.

Decision rule (per the agreed design): OR-of-hard-triggers gates the flag; the
weighted sum is computed and passed downstream but does NOT gate the flag. This
is what lets a narrow-but-real C5 (weight 0.07) or C6 (0.10) breach contribute
to whole-dataset recall instead of being buried under a single sum threshold.

Each detector keeps its own detection logic untouched; this module only adapts
the unified row into the shape each one expects (via data_layer adapters) and
normalises every detector's output to a common {fired, score, trigger} contract.
"""

import asyncio
from datetime import datetime

from .data_layer import (
    DataLayer,
    c1_baseline,
    c1_recent_dicts,
    c6_account_history,
    c6_transaction,
    _f,
    _parse_ts,
)

# --- spec weights (C1–C6 sum to 1.00) -------------------------------------
WEIGHTS = {
    "C1": 0.27,
    "C2": 0.20,
    "C3": 0.17,
    "C4": 0.19,
    "C5": 0.07,
    "C6": 0.10,
}


# ===========================================================================
# Per-category runners. Each returns: {"fired": bool, "score": float,
#                                       "trigger": str|None}
# ===========================================================================

# ---- C1 Velocity & Structuring -------------------------------------------
from .detectors import c1_adapter
from .detectors.c1_velocity_and_structuring import slm_reasoner as c1_slm


async def run_c1(row, dl):
    res = c1_adapter.evaluate_row(row, dl)
    if not res["fired"]:
        return res
    # phi4 reviews the fired velocity/structuring pattern (C1's designed
    # reasoning role) and can deprioritise a clear false positive (e.g. salary
    # disbursement). Any failure / sub-threshold score leaves the fire intact.
    try:
        tx_payload = {
            "tx_id": row.get("tx_id"),
            "amount_inr": _f(row.get("amount_inr")),
            "purpose_code": row.get("purpose_code", ""),
            "receiver_name": row.get("receiver_name", ""),
            "channel": row.get("channel", ""),
        }
        reasoning = await c1_slm.run_slm_reasoning(
            tx_payload, res.get("evidence", {}), res["score"], [res["trigger"]]
        )
        if (
            reasoning
            and reasoning.get("false_positive_likelihood") == "HIGH"
            and reasoning.get("recommended_action") == "DEPRIORITISE"
        ):
            return {"fired": False, "score": 0.0, "trigger": None}
    except Exception:
        pass
    return res


# ---- C2 Sanctions & Watchlist --------------------------------------------
from .detectors import c2_sanctions_and_watchlist as c2mod


def _c2_event(row):
    return {
        "tx_id": row["tx_id"],
        "timestamp": row.get("timestamp"),
        "channel": row.get("channel"),
        "amount_inr": _f(row.get("amount_inr")),
        "sender": {
            "account_id": row.get("sender_account_id"),
            "name": row.get("sender_name"),
            "pan": row.get("sender_pan"),
            "dob": row.get("sender_dob"),
        },
        "receiver": {
            "account_id": row.get("receiver_account_id"),
            "name": row.get("receiver_name"),
            "pan": row.get("receiver_pan"),
            "dob": row.get("receiver_dob"),
        },
    }


async def run_c2(row, dl):
    res = c2mod.evaluate_row(row, dl.watchlist)
    return res


# ---- C3 Graph / Network Flow ---------------------------------------------
from .detectors import c3_graph_network_flow as c3mod


async def run_c3(row, dl):
    # phi4 is the authoritative C3 classifier on every case; the deterministic
    # graph rules supply the score magnitude and the automatic fallback.
    return c3mod.evaluate_row_slm(row, dl)


# ---- C4 Account Risk & Dormancy ------------------------------------------
from .detectors import c4_account_risk_and_dormancy as c4mod


async def run_c4(row, dl):
    res = c4mod.evaluate_row(row, dl)
    if not res["fired"]:
        return res
    # phi4 confirms or vetoes the fired dormancy / new-account case in context.
    acc = dl.account_for(row.get("sender_account_id", ""))
    verdict = c4mod.slm_confirm(acc, res["trigger"], _f(row.get("amount_inr")))
    if verdict["label"] == "NORMAL":
        return {"fired": False, "score": 0.0, "trigger": None}
    return res


# ---- C5 Cross-Border / FEMA-LRS ------------------------------------------
from .detectors import c5_fema_lrs as c5mod


async def run_c5(row, dl):
    return c5mod.evaluate_row(row, dl)


# ---- C6 Geo-Anomaly -------------------------------------------------------
from .detectors.c6_geo_anomaly.detector import predict as c6_predict
from .detectors.c6_geo_anomaly import slm_classifier as c6_slm


async def run_c6(row, dl):
    acc = dl.account_for(row["sender_account_id"])
    cur_ts = _parse_ts(row["timestamp"])
    hist = dl.history_for(row["sender_account_id"], before_ts=cur_ts)
    ah = c6_account_history(acc, hist, dl)
    out = c6_predict(c6_transaction(row), ah)
    f = out["evidence"]["features"]

    # "Signals present" pre-gate (perf): C6 is SUSPICIOUS only if a geo/device
    # trigger fires, and every trigger is a subset of these anomaly flags. If a
    # transaction sets NONE of them it is vanilla — phi4 would trivially say
    # NORMAL — so skip the call. Recall is preserved: any transaction with even
    # one anomaly signal still goes to phi4 for the contextual judgement.
    anomaly_present = (
        f.get("is_new_location") or f.get("is_rare_location") or f.get("is_foreign")
        or f.get("is_fatf_high_risk") or f.get("impossible_travel")
        or f.get("is_new_device") or f.get("is_balance_drain") or f.get("is_odd_hour")
    )
    if not anomaly_present:
        return {"fired": False, "score": 0.0, "trigger": None}

    # phi4 is the authoritative C6 classifier for every case that has a signal:
    # it reasons over the SAME features the deterministic detector measured and
    # decides SUSPICIOUS vs NORMAL using context (NRE account, frequent
    # traveller, one-off purchase) that the old hardcoded travel-profile gates
    # approximated. classify() falls back to the transparent reference reasoner
    # if Ollama is unreachable.
    verdict = c6_slm.classify(f)
    fired = verdict["label"] == 1
    if not fired:
        return {"fired": False, "score": 0.0, "trigger": None}

    # Deterministic noisy-OR supplies the score magnitude; phi4 confidence backs
    # it up when the magnitude is zero (e.g. a subtle new-device probe).
    score = out["score"] if out["score"] > 0 else round(float(verdict["confidence"]), 4)

    if f.get("impossible_travel"):
        trig = "C6_impossible_travel"
    elif f.get("is_fatf_high_risk"):
        trig = "C6_jurisdiction"
    elif f.get("is_balance_drain") and f.get("is_new_device"):
        trig = "C6_takeover"
    elif f.get("is_new_device"):
        trig = "C6_newloc_newdev" if f.get("is_new_location") else "C6_subtle_probe"
    elif f.get("is_foreign"):
        trig = "C6_foreign"
    else:
        trig = "C6_geo"
    return {"fired": fired, "score": score, "trigger": trig}


# ===========================================================================
# Orchestration
# ===========================================================================
async def monitor(row, dl):
    """Run all six detectors in parallel; combine to a flag + weighted score."""
    results = await asyncio.gather(
        run_c1(row, dl), run_c2(row, dl), run_c3(row, dl),
        run_c4(row, dl), run_c5(row, dl), run_c6(row, dl),
    )
    cats = ["C1", "C2", "C3", "C4", "C5", "C6"]
    per = dict(zip(cats, results))

    weighted = round(sum(WEIGHTS[c] * per[c]["score"] for c in cats), 4)
    fired_cats = [c for c in cats if per[c]["fired"]]
    triggers = [per[c]["trigger"] for c in fired_cats if per[c]["trigger"]]
    flag = len(fired_cats) > 0

    return {
        "tx_id": row["tx_id"],
        "flag": flag,
        "suspicion_score": weighted,
        "fired_categories": fired_cats,
        "triggers": triggers,
        "per_category": per,
    }


def monitor_sync(row, dl):
    return asyncio.run(monitor(row, dl))
