"""Quick validation script to verify L2 scoring against test transactions."""
import asyncio
import json
import sys
sys.path.insert(0, "/Users/nihalraviganesh/Documents/compliance-pipeline")
from L2_transaction_monitor.main import transaction_monitor

async def main():
    with open("/Users/nihalraviganesh/Documents/compliance-pipeline/L3_TestTransactions.json") as f:
        transactions = json.load(f)

    print("=" * 80)
    print("L2 Transaction Monitor — Scoring Validation")
    print("=" * 80)

    for txn in transactions:
        result = await transaction_monitor(txn)
        print(f"\n{'─' * 60}")
        print(f"TX: {result['tx_id']}  |  Scenario: {txn.get('scenario_tag')}")
        print(f"  Composite Score : {result['composite_score']:.4f}  →  {result['risk_level']}")
        print(f"  T1 Velocity     : {result['component_scores']['t1_velocity']:.4f}")
        print(f"  T2 Watchlist    : {result['component_scores']['t2_watchlist']:.4f}")
        print(f"  T3 Risk Score   : {result['component_scores']['t3_risk_score']:.4f}")
        print(f"  T4 Geo Anomaly  : {result['component_scores']['t4_geo_anomaly']:.4f}")
        if result['critical_boost_applied']:
            print(f"  ⚠ Critical boost applied (floor raised to 0.75)")

    print(f"\n{'=' * 80}")

asyncio.run(main())
