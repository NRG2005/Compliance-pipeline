"""
run_one.py  —  Run ONE transaction through the full L2 pipeline (terminal demo).

Loads the unified dataset, picks a single transaction (by --tx-id, or the first
one), runs all six detectors via the orchestrator (which now consults real phi4
over Ollama for C1-C6, with deterministic fallback), and prints a readable
breakdown of what fired and why.

Usage (from the repo root, D:\\Bank-Project\\Compliance-pipeline):

    python -m L2_transaction_monitor.run_one
    python -m L2_transaction_monitor.run_one --tx-id TX20260601000693
    python -m L2_transaction_monitor.run_one --first-fired
"""

import argparse
import json

from .data_layer import DataLayer
from .orchestrator import monitor_sync


def _print_row(row):
    print("INPUT TRANSACTION")
    print("-" * 70)
    for k in ("tx_id", "timestamp", "channel", "amount_inr",
              "sender_account_id", "sender_name", "receiver_account_id",
              "receiver_name", "device_id", "tx_location_city",
              "tx_location_country", "purpose_code", "is_cross_border"):
        if row.get(k) not in (None, ""):
            print(f"  {k:<22} {row.get(k)}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tx-id", help="Transaction id to run (default: first row)")
    ap.add_argument("--first-fired", action="store_true",
                    help="Run the first transaction that raises a flag")
    args = ap.parse_args()

    dl = DataLayer()

    if args.first_fired:
        row = None
        for r in dl.transactions:
            if monitor_sync(r, dl)["flag"]:
                row = r
                break
        if row is None:
            print("No firing transaction found."); return
    elif args.tx_id:
        row = next((r for r in dl.transactions if r["tx_id"] == args.tx_id), None)
        if row is None:
            print(f"tx_id {args.tx_id} not found."); return
    else:
        row = dl.transactions[0]

    _print_row(row)

    result = monitor_sync(row, dl)

    print("L2 VERDICT")
    print("-" * 70)
    print(f"  flag             {result['flag']}")
    print(f"  suspicion_score  {result['suspicion_score']}")
    print(f"  fired_categories {result['fired_categories']}")
    print(f"  triggers         {result['triggers']}")
    print()
    print("PER-DETECTOR DETAIL")
    print("-" * 70)
    for cat, r in result["per_category"].items():
        mark = "FIRED" if r.get("fired") else "clear"
        line = f"  {cat}  [{mark}]  score={r.get('score')}"
        if r.get("trigger"):
            line += f"  trigger={r.get('trigger')}"
        if r.get("predictor"):
            line += f"  predictor={r.get('predictor')}"
        print(line)
        if r.get("reason"):
            print(f"        reason: {r['reason']}")
    print()
    print("RAW JSON")
    print("-" * 70)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
