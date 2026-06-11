"""
Main function for L2 Transaction Monitor.
This function will orchestrate the execution of the six parallel checks (C1-C6)
and combine their outputs into a single suspicion score.
"""
import asyncio
from L2_transaction_monitor.c1_velocity_and_structuring import check_velocity_and_structuring
from L2_transaction_monitor.c2_sanctions_and_watchlist import check_sanctions_and_watchlist
from L2_transaction_monitor.c3_graph_network_flow import analyze_graph_network_flow
from L2_transaction_monitor.c4_account_risk_and_dormancy import calculate_account_risk_and_dormancy
from L2_transaction_monitor.c5_fema_lrs import fema_lrs_analysis
from L2_transaction_monitor.c6_geo_anomaly import check_geo_anomaly

async def transaction_monitor(transaction_data):
    """
    Runs all transaction monitoring checks in parallel.
    
    Returns:
        suspicion_score: Combined weighted score from all six checks (0-1)
    """
    # TODO: Fetch necessary data for each check (e.g., history, account info)
    
    results = await asyncio.gather(
        check_velocity_and_structuring(transaction_data),
        check_sanctions_and_watchlist(transaction_data),
        analyze_graph_network_flow(transaction_data),
        calculate_account_risk_and_dormancy(transaction_data),
        fema_lrs_analysis(transaction_data),
        check_geo_anomaly(transaction_data)
    )
    
    c1_res, c2_res, c3_res, c4_res, c5_res, c6_res = results
    
    # Placeholder for combining results from all 6 checks.
    # C4 returns a risk dict (from the old T3 logic).
    c4_score = float(c4_res.get("risk_score", 0.0)) if isinstance(c4_res, dict) else 0.0
    
    suspicion_score = round(
        (0.15 * (0.0 if c1_res is None else float(c1_res))) +
        (0.20 * (0.0 if c2_res is None else float(c2_res))) +
        (0.10 * (0.0 if c3_res is None else float(c3_res))) +
        (0.35 * c4_score) +
        (0.10 * (0.0 if c5_res is None else float(c5_res))) +
        (0.10 * (0.0 if c6_res is None else float(c6_res))),
        3
    )

    if isinstance(c4_res, dict):
        print(f"L2: C4 Account Risk findings: {c4_res.get('faults', [])}")

    
    return suspicion_score
