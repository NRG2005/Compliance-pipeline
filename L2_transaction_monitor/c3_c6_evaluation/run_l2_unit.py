"""
run_l2_unit.py — exercise the WHOLE L2 unit (all six checks via the aggregator)
across representative use cases, and show whether each fires as expected.

This complements `evaluate.py` (which rigorously scores the C3/C6 detectors with
F1 over a labelled dataset). This script is the end-to-end view: it feeds sample
transactions through `transaction_monitor` and prints each check's contribution
plus the combined suspicion score.

Run (from repo root):
  python L2_transaction_monitor/c3_c6_evaluation/run_l2_unit.py          # fast (mock reasoner)
  python L2_transaction_monitor/c3_c6_evaluation/run_l2_unit.py --real   # real phi4-mini (slower)

How to read it:
  - Each row is one use case. The arrow shows the COMBINED suspicion_score.
  - The per-check columns show each detector's [0,1] contribution-before-weight.
  - C3/C6 are our detectors (should fire on graph / geo anomalies).
  - C1/C2/C4/C5 show 0.00 until their owners add their data files/deps — they are
    wired and will light up automatically once those land (see INTEGRATION_NOTES.md).
  - "works?" is a quick check that the expected detector fired (score > 0.5).
"""

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def _acct(aid, dev, ifsc, holder, age):
    return {"account_id": aid, "device_id": dev, "ifsc": ifsc, "holder_name": holder, "account_age_days": age}


def _hist(**over):
    base = {
        "home_country": "IN", "known_locations": {"Mumbai": 50}, "typical_devices": ["DEV-A"],
        "balance_inr": 100000, "avg_tx_amount": 8000, "account_type": "SAVINGS", "travel_profile": "DOMESTIC_STATIC",
    }
    base.update(over)
    return base


def _tx(**over):
    base = {
        "tx_id": "T", "sender_account_id": "ACC1", "timestamp": "2026-06-01T17:00:00",
        "amount_inr": 5000, "channel": "UPI", "purpose_code": "P0099", "device_id": "DEV-A",
        "location": {"city": "Mumbai", "country": "IN", "lat": 19.07, "lon": 72.87},
    }
    base.update(over)
    return base


# A 2-hop layering loop (C3 should fire) and a 6-credit fan-out (C3 should fire).
_LAYER_CASE = {
    "case_id": "L", "trigger_account": "T", "window_hours": 72,
    "edges": [
        {"src": "T", "dst": "B", "amount_inr": 200000, "timestamp": "2026-06-01T09:00:00"},
        {"src": "B", "dst": "R", "amount_inr": 184000, "timestamp": "2026-06-01T09:30:00"},
    ],
    "accounts": {
        "T": _acct("T", "D1", "HDFC001", "Aa Bb", 400),
        "B": _acct("B", "D2", "ICIC1", "Cc Dd", 600),
        "R": _acct("R", "D1", "AXIS1", "Ee Ff", 500),
    },
}


def _fanout_case():
    edges, accts = [], {"T": _acct("T", "D-T", "HDFC1", "Mule One", 40)}
    cum = 0
    for k in range(6):
        a = 3000 + k * 100; cum += a
        accts[f"P{k}"] = _acct(f"P{k}", f"D-P{k}", "SBIN1", f"Payer {k}", 800)
        edges.append({"src": f"P{k}", "dst": "T", "amount_inr": a,
                      "timestamp": f"2026-06-01T09:0{k}:00", "src_vpa": f"v{k}@bank"})
    accts["S"] = _acct("S", "D-S", "AXIS1", "Sink Acc", 1200)
    edges.append({"src": "T", "dst": "S", "amount_inr": cum * 0.9, "timestamp": "2026-06-01T09:40:00"})
    return {"case_id": "F", "trigger_account": "T", "window_hours": 72, "edges": edges, "accounts": accts}


# (name, transaction_data, which check should fire, expected_fire?)
SCENARIOS = [
    ("clean_routine",
     _tx(amount_inr=6000, account_history=_hist()), "none", False),
    ("geo_takeover_newdevice_drain",
     _tx(amount_inr=95000, device_id="DEV-EVIL", account_history=_hist()), "C6", True),
    ("impossible_travel",
     _tx(amount_inr=60000, device_id="DEV-X",
         location={"city": "NewYork", "country": "US", "lat": 40.7, "lon": -74.0},
         account_history=_hist(last_location={"city": "Mumbai", "lat": 19.07, "lon": 72.87,
                                              "timestamp": "2026-06-01T16:30:00"})), "C6", True),
    ("nre_foreign_legit",
     _tx(amount_inr=80000, location={"city": "Dubai", "country": "AE", "lat": 25.2, "lon": 55.3},
         account_history=_hist(account_type="NRE", travel_profile="INTERNATIONAL_FREQUENT")), "C6", False),
    ("mule_fanout",
     _tx(amount_inr=5000, account_history=_hist(), graph_case=_fanout_case()), "C3", True),
    ("layering_roundtrip",
     _tx(amount_inr=5000, account_history=_hist(), graph_case=_LAYER_CASE), "C3", True),
]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true", help="use real phi4-mini (slower); default = fast mock reasoner")
    args = ap.parse_args()

    from L2_transaction_monitor.c3_graph_network_flow import slm_classifier as c3_slm
    from L2_transaction_monitor.c6_geo_anomaly import slm_classifier as c6_slm
    c3_slm.USE_MOCK = not args.real
    c6_slm.USE_MOCK = not args.real
    import L2_transaction_monitor.main as agg

    backend = "real phi4-mini (Ollama)" if args.real else "fast reference reasoner (mock)"
    print(f"L2 unit test — SLM backend: {backend}\n")
    checks = [agg.check_velocity_and_structuring, agg.check_sanctions_and_watchlist,
              agg.analyze_graph_network_flow, agg.calculate_account_risk_and_dormancy,
              agg.fema_lrs_analysis, agg.check_geo_anomaly]

    print(f"{'use case':<32}{'C1':>6}{'C2':>6}{'C3':>6}{'C4':>6}{'C5':>6}{'C6':>6}{'  SCORE':>9}  works?")
    print("-" * 92)
    passed = 0
    for name, tx, fires, expect in SCENARIOS:
        per = [await agg._run(fn, tx) for fn in checks]
        score = await agg.transaction_monitor(tx)
        fired_map = {"C1": per[0], "C2": per[1], "C3": per[2], "C4": per[3], "C5": per[4], "C6": per[5]}
        if fires == "none":
            ok = score < 0.5
        else:
            ok = fired_map[fires] > 0.5
        passed += ok
        cells = "".join(f"{p:>6.2f}" for p in per)
        print(f"{name:<32}{cells}{score:>9.3f}  {'PASS' if ok else 'FAIL'}  "
              f"({'expected ' + fires + ' to fire' if expect else 'expected quiet'})")
    print("-" * 92)
    print(f"{passed}/{len(SCENARIOS)} use cases behaved as expected.")
    print("\nNote: C1/C2/C4/C5 read 0.00 until their owners supply data/deps "
          "(transactions.csv, watchlist.csv, L3/Gemini, FEMA fields) — they are wired.")


if __name__ == "__main__":
    asyncio.run(main())
