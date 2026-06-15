"""
demo.py  —  One file to drive the live Azure -> local pipeline demo.

This merges the two former demo helpers (publish_demo_set.py + run_from_azure.py)
into a single command with subcommands. The pipeline itself is unchanged: events
come from the real Azure Storage Queue `tx-events`, and compute runs locally
(L1 routing -> L2 detectors + phi4) on this desktop.

Subcommands
-----------
  clear                     Empty the Azure `tx-events` queue AND the local
                            case-memory cache (so nothing short-circuits).

  publish [--tx-ids a,b,c]  Publish a curated list of known-suspicious
                            transactions (one per category C1-C6 + one clean
                            control). Pass --tx-ids to publish your own set.

  run [--count N]           Pull N messages from the Azure queue and run each
                            through the local pipeline (default 1).

  all [--count N]           clear -> publish -> run, in one shot. --count
                            defaults to the number of transactions published.

Prerequisites (one-time):
  1. Deploy the storage account + queue:   see infra/main.bicep
  2. Generate .env:                         ./infra/setup-env.ps1 -ResourceGroup rg-compliance-demo
  3. Ollama running locally:                ollama serve   (model phi4-mini pulled)

Typical demo flow:
    python demo.py clear
    python demo.py publish
    python demo.py run --count 7
  (or simply:)
    python demo.py all
"""

import argparse
import asyncio
import csv
import json
from pathlib import Path

from config import get_config
from L0_event_ingestion.event_receiver import (
    receive_message,
    delete_message,
    get_queue_length,
    get_queue_client,
)
from L1_orchestrator.orchestrator import handle_event

TRANSACTIONS_CSV = Path("L2_transaction_monitor/data/transactions.csv")
CASE_MEMORY = Path("data/case_memory.json")

# One confirmed-suspicious tx per category (from ground_truth.csv) + a clean one.
DEMO_TX_IDS = [
    "TX20260603000642",  # C6  FATF high-risk jurisdiction
    "TX20260603000268",  # C2  watchlist hit
    "TX20260603000484",  # C4  dormant-account reactivation
    "TX20260602000291",  # C3  classic mule fan-in
    "TX20260603000066",  # C1  structuring / smurfing
    "TX20260602000569",  # C5  FEMA-LRS ceiling breach
    "TX20260602001527",  # CLEAN control (should NOT flag)
]


# --------------------------------------------------------------------------- #
# publish / clear  (formerly publish_demo_set.py)
# --------------------------------------------------------------------------- #
def _load_rows():
    with open(TRANSACTIONS_CSV, encoding="utf-8") as f:
        return {r["tx_id"]: r for r in csv.DictReader(f)}


def clear():
    client = get_queue_client()
    client.clear_messages()
    print("Azure queue 'tx-events' cleared.")
    if CASE_MEMORY.exists():
        CASE_MEMORY.unlink()
        print("Local case-memory cache cleared (data/case_memory.json).")
    else:
        print("No local case-memory cache to clear.")


def publish(tx_ids):
    rows = _load_rows()
    client = get_queue_client()
    published, missing = 0, []
    for tx_id in tx_ids:
        row = rows.get(tx_id)
        if not row:
            missing.append(tx_id)
            continue
        clean_row = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
        client.send_message(json.dumps(clean_row))
        published += 1
        print(f"  published {tx_id:<20} | {clean_row.get('channel'):<5} "
              f"| Rs {clean_row.get('amount_inr'):<10} "
              f"| {clean_row.get('tx_location_city')}, {clean_row.get('tx_location_country')}")
    print(f"\nPublished {published} transaction(s) to the Azure queue.")
    if missing:
        print(f"WARNING: tx_ids not found in transactions.csv: {missing}")
    print("Now run:  python demo.py run --count", published)
    return published


def publish_files(paths):
    """Publish one or more hand-made transaction JSON FILES to the Azure queue.

    Lets you give your own transaction via the CLI -> queue -> pull, instead of
    selecting an existing row by tx_id. Each file must hold ONE transaction dict.
    """
    client = get_queue_client()
    published = 0
    for path in paths:
        with open(path, encoding="utf-8") as f:
            tx = json.load(f)
        client.send_message(json.dumps(tx))
        published += 1
        print(f"  published {str(tx.get('tx_id')):<22} | {tx.get('channel'):<5} "
              f"| Rs {tx.get('amount_inr')} "
              f"| {tx.get('tx_location_city')}, {tx.get('tx_location_country')}  ({path})")
    print(f"\nPublished {published} transaction(s) to the Azure queue.")
    print("Now run:  python demo.py run --count", published)
    return published


# --------------------------------------------------------------------------- #
# run  (formerly run_from_azure.py)
# --------------------------------------------------------------------------- #
def _print_verdict(state):
    ev = (state.get("evidence") or {}).get("per_category", {})
    print("L2 VERDICT (computed locally)")
    print("-" * 70)
    print(f"  route            {state.get('route')}")
    print(f"  suspicion_score  {state.get('suspicion_score')}")
    print(f"  fired_categories {state.get('fired_categories')}")
    print(f"  triggers         {state.get('triggers_fired')}")
    c6 = (state.get("evidence") or {}).get("c6_slm_reasoning")
    if c6:
        print(f"  C6 phi4 verdict  {c6.get('verdict')} (conf={c6.get('confidence')}, "
              f"predictor={c6.get('predictor')})")
        if c6.get("reason"):
            print(f"  C6 phi4 reason   {c6.get('reason')}")
    if ev:
        print("\n  per-detector:")
        for cat, r in ev.items():
            mark = "FIRED" if r.get("fired") else "clear"
            line = f"    {cat}  [{mark}]  score={r.get('score')}"
            if r.get("trigger"):
                line += f"  trigger={r.get('trigger')}"
            if r.get("predictor"):
                line += f"  predictor={r.get('predictor')}"
            print(line)
            if r.get("reason"):
                print(f"          reason: {r['reason']}")
    print()


async def _run(count):
    cfg = get_config()
    if not cfg.AZURE_STORAGE_CONNECTION_STRING:
        print("ERROR: AZURE_STORAGE_CONNECTION_STRING is not set.")
        print("Run ./infra/setup-env.ps1 first to generate .env from your deployed storage account.")
        return

    print(f"Azure queue '{cfg.AZURE_STORAGE_QUEUE_NAME}' length: {get_queue_length()}")
    print("=" * 70)

    for i in range(count):
        result = receive_message()
        if not result:
            print("Queue empty — nothing to process.")
            break
        msg, tx = result
        print(f"\n>>> PULLED FROM AZURE: {tx.get('tx_id')} "
              f"| {tx.get('channel')} | Rs {tx.get('amount_inr')} "
              f"| {tx.get('tx_location_city')}, {tx.get('tx_location_country')}")
        print("-" * 70)
        state = await handle_event(tx)
        _print_verdict(state)
        delete_message(msg)   # ack so it isn't re-processed


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Azure -> local compliance pipeline demo driver.")
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("clear", help="Empty the queue + local case-memory cache, then exit")

    p_publish = sub.add_parser("publish", help="Publish the curated demo set to the Azure queue")
    p_publish.add_argument("--tx-ids", help="Comma-separated tx_ids to publish (overrides the default set)")

    p_pf = sub.add_parser("publish-file", help="Publish your own transaction JSON file(s) to the Azure queue")
    p_pf.add_argument("paths", nargs="+", help="Path(s) to JSON file(s), each holding ONE transaction")

    p_run = sub.add_parser("run", help="Pull messages from Azure and run them through the pipeline")
    p_run.add_argument("--count", type=int, default=1,
                       help="How many messages to pull from Azure (default 1)")

    p_all = sub.add_parser("all", help="clear -> publish -> run, in one shot")
    p_all.add_argument("--tx-ids", help="Comma-separated tx_ids to publish (overrides the default set)")
    p_all.add_argument("--count", type=int, default=None,
                       help="How many messages to pull (default: number published)")

    args = ap.parse_args()

    if args.command == "clear":
        clear()
        return

    if args.command == "publish":
        tx_ids = [t.strip() for t in args.tx_ids.split(",")] if args.tx_ids else DEMO_TX_IDS
        publish(tx_ids)
        return

    if args.command == "publish-file":
        publish_files(args.paths)
        return

    if args.command == "run":
        asyncio.run(_run(args.count))
        return

    if args.command == "all":
        clear()
        tx_ids = [t.strip() for t in args.tx_ids.split(",")] if args.tx_ids else DEMO_TX_IDS
        published = publish(tx_ids)
        count = args.count if args.count is not None else published
        asyncio.run(_run(count))
        return


if __name__ == "__main__":
    main()
