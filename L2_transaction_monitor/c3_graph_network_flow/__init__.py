"""
C3 — Graph / Network Flow  (absorbs T5 mule fan-in/out + T9 layering round-trip)
--------------------------------------------------------------------------------
Two public entry points:

  * `analyze_graph_network_flow(transaction_data)` — async, the signature the L2
    aggregator (main.py) calls in its asyncio.gather over C1–C6.
  * `run_c3(case, mode=...)` — the synchronous core used by the evaluation harness.

    from L2_transaction_monitor.c3_graph_network_flow import run_c3
    result = run_c3(case, mode="slm")

`mode`:
  "deterministic" -> rules-only baseline (detector.predict)
  "slm"           -> phi4 contextual classifier on the same graph features
  "both"          -> returns both, with the SLM as the authoritative `label`

Weight in the C-layer composite: 0.17.
"""

import asyncio

from .detector import predict as _det_predict
from . import slm_classifier


def _suspicion_float(result: dict) -> float:
    """Collapse a run_c3 result dict into a [0,1] suspicion float for the L2
    aggregator. Confidence when the SLM flags it; the deterministic score in
    rules-only mode; 0.0 when the check does not fire."""
    if result.get("label") != 1:
        return 0.0
    val = result.get("confidence")
    if val is None:
        val = result.get("score", result.get("deterministic_score", 1.0))
    return round(float(val), 4)


def run_c3(case: dict, mode: str = "slm") -> dict:
    det = _det_predict(case)
    if mode == "deterministic":
        return det

    fan = det["evidence"]["fan_in_out"]
    rt = det["evidence"]["round_trip"]
    slm = slm_classifier.classify(fan, rt)

    if mode == "slm":
        return {
            "check": "C3_GRAPH_FLOW",
            "weight": 0.17,
            "label": slm["label"],
            "predictor": slm["predictor"],
            "verdict": slm["verdict"],
            "confidence": slm["confidence"],
            "reason": slm["reason"],
            "deterministic_score": det["score"],
            "fan_in_out": fan,
            "round_trip": rt,
        }

    return {
        "check": "C3_GRAPH_FLOW",
        "weight": 0.17,
        "label": slm["label"],
        "deterministic": det,
        "slm": slm,
    }


async def analyze_graph_network_flow(transaction_data: dict, mode: str = "slm") -> float:
    """
    L2-aggregator entry point (async, awaited inside main.py's asyncio.gather).

    Returns a FLOAT in [0, 1] — C3's suspicion contribution — because the L2
    aggregator combines the checks as `float(c3_res)` weighted by 0.10. The value
    is the SLM's confidence when it flags a mule/layering pattern, else 0.0.

    The aggregator passes the transaction payload. C3 operates on a 72h
    transaction sub-graph ("case") for the account cluster — expected on
    `transaction_data["graph_case"]` once L1 supplies it; 0.0 if absent.

    run_c3 is synchronous (it may call the SLM), so it is offloaded to a worker
    thread to avoid blocking the event loop. Use `run_c3(...)` directly for the
    full evidence dict.
    """
    case = (transaction_data or {}).get("graph_case")
    if not case:
        return 0.0
    result = await asyncio.to_thread(run_c3, case, mode)
    return _suspicion_float(result)


__all__ = ["run_c3", "analyze_graph_network_flow"]
