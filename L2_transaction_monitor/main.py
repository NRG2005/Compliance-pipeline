"""
Main function for L2 Transaction Monitor.
Orchestrates the four parallel checks (T1-T4) and combines their outputs
into a single composite suspicion score using a weighted formula.

Weights:
    T1 (Velocity)   : 0.35
    T2 (Watchlist)   : 0.15
    T3 (Risk Score)  : 0.35
    T4 (Geo Anomaly) : 0.15

Critical boost logic prevents high-risk signals from being diluted
by dimensions that correctly score zero (e.g., T4=0 for domestic txns).
"""

import asyncio
from L2_transaction_monitor.t1_velocity import check_velocity
from L2_transaction_monitor.t2_watchlist import check_watchlist
from L2_transaction_monitor.t3_risk_score import calculate_risk_score
from L2_transaction_monitor.t4_geo_anomaly import check_geo_anomaly


async def transaction_monitor(transaction_data: dict) -> dict:
    """
    Runs all transaction monitoring checks in parallel via asyncio.gather,
    then combines scores with a weighted formula and critical boosts.
    """
    t1_score, t2_score, t3_score, t4_score = await asyncio.gather(
        check_velocity(transaction_data),
        check_watchlist(transaction_data),
        calculate_risk_score(transaction_data),
        check_geo_anomaly(transaction_data),
    )

    all_scores = [t1_score, t2_score, t3_score, t4_score]

    weights = {
        "t1_velocity": 0.35,
        "t2_watchlist": 0.15,
        "t3_risk_score": 0.35,
        "t4_geo_anomaly": 0.15,
    }

    composite = (
        weights["t1_velocity"] * t1_score
        + weights["t2_watchlist"] * t2_score
        + weights["t3_risk_score"] * t3_score
        + weights["t4_geo_anomaly"] * t4_score
    )

    # ── Critical boost ──
    # Prevents high-risk signals from being averaged away by benign
    # dimensions (e.g., a domestic smurfing transaction will have
    # T4 geo = 0.0 and T2 watchlist near 0, but T1 velocity = 1.0).
    critical_boost = False
    max_score = max(all_scores)
    sorted_desc = sorted(all_scores, reverse=True)

    # Determine composite floor based on signal strength & convergence
    floor = 0.0

    # Tier 1: Two or more dimensions at ≥ 0.8 → overwhelming evidence
    if sorted_desc[1] >= 0.8:
        floor = 0.88

    # Tier 2: Strongest signal at ≥ 0.9 → near-certain on one dimension
    elif max_score >= 0.9:
        # Scale floor by next-best signal: if companion is moderately elevated,
        # it corroborates the primary signal
        companion = sorted_desc[1]
        if companion >= 0.5:
            floor = 0.85
        elif companion >= 0.3:
            floor = 0.82
        else:
            floor = 0.80

    # Tier 3: Any signal at ≥ 0.8 → strong single-dimension alert
    elif max_score >= 0.8:
        companion = sorted_desc[1]
        if companion >= 0.5:
            floor = 0.82
        else:
            floor = 0.75

    if composite < floor:
        composite = floor
        critical_boost = True

    composite = min(max(composite, 0.0), 1.0)

    # Risk-level classification
    if composite >= 0.80:
        risk_level = "CRITICAL"
    elif composite >= 0.60:
        risk_level = "HIGH"
    elif composite >= 0.35:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return {
        "tx_id": transaction_data.get("tx_id"),
        "composite_score": round(composite, 4),
        "risk_level": risk_level,
        "component_scores": {
            "t1_velocity": round(t1_score, 4),
            "t2_watchlist": round(t2_score, 4),
            "t3_risk_score": round(t3_score, 4),
            "t4_geo_anomaly": round(t4_score, 4),
        },
        "weights": weights,
        "critical_boost_applied": critical_boost,
    }
