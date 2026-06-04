"""
Main function for L2 Transaction Monitor.
This function will orchestrate the execution of the four parallel checks (T1-T4)
and combine their outputs into a single suspicion score.
"""
import asyncio
from L2_transaction_monitor.t1_velocity import check_velocity
from L2_transaction_monitor.t2_watchlist import check_watchlist
from L2_transaction_monitor.t3_risk_score import calculate_risk_score
from L2_transaction_monitor.t4_geo_anomaly import check_geo_anomaly

async def transaction_monitor(transaction_data):
    """
    Runs all transaction monitoring checks in parallel.
    """
    # TODO: Fetch necessary data for each check (e.g., history, account info)
    
    results = await asyncio.gather(
        check_velocity(transaction_data),
        check_watchlist(transaction_data),
        calculate_risk_score(transaction_data),
        check_geo_anomaly(transaction_data)
    )
    
    velocity_result, watchlist_result, risk_result, geo_result = results

    weighted_components = {
        "t1_velocity": 0.0 if velocity_result is None else float(velocity_result),
        "t2_watchlist": 0.0 if watchlist_result is None else float(watchlist_result),
        "t3_risk_score": float(risk_result.get("risk_score", 0.0)),
        "t4_geo_anomaly": 0.0 if geo_result is None else float(geo_result),
    }

    # Temporary first-pass weighting while only T3 is implemented.
    suspicion_score = round(
        (0.15 * weighted_components["t1_velocity"])
        + (0.25 * weighted_components["t2_watchlist"])
        + (0.45 * weighted_components["t3_risk_score"])
        + (0.15 * weighted_components["t4_geo_anomaly"]),
        3,
    )

    print(f"L2: Weighted components: {weighted_components}")
    print(f"L2: T3 findings: {risk_result.get('faults', [])}")
    
    return suspicion_score
