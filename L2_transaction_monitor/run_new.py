"""
run_new.py  —  Score a BRAND-NEW transaction against the data-folder context.

Unlike run_one.py (which picks an existing row from transactions.csv), this takes
a transaction you supply as JSON and runs it through all six detectors. The CSV
data in `data/` provides the CONTEXT each detector needs:

  * account_details.csv  -> account age / KYC / dormancy / travel profile (C4, C6)
  * case_history.csv      -> the sender's prior activity (C6 geo history)
  * transactions.csv      -> sibling transactions of the sender (C1 velocity /
                             structuring, C3 graph cluster, C5 cross-border legs)
  * watchlist.csv         -> sanctions / watchlist entities (C2)

The new transaction is REGISTERED into the in-memory context so sibling-based
detectors (C1/C3/C5) see it as a first-class participant in the cluster.

Reference an EXISTING sender_account_id / sender_pan so the dataset actually has
context for it (otherwise the account-based checks have nothing to compare to).

Usage (from the repo root, D:\\Bank-Project\\Compliance-pipeline):

    # write an editable sample first
    python -m L2_transaction_monitor.run_new --make-sample mytx.json

    # then edit mytx.json and run it
    python -m L2_transaction_monitor.run_new --json mytx.json
"""

import argparse
import json

from .data_layer import DataLayer
from .orchestrator import monitor_sync
from .run_one import _print_row


def _make_sample(path):
    """Write an editable sample transaction referencing an existing account."""
    sample = {
        "tx_id": "TXNEW0001",
        "timestamp": "2026-06-14T03:20:00",
        "channel": "UPI",
        "amount_inr": "480000",
        "sender_account_id": "ACC29699",
        "sender_name": "Suresh Bose",
        "sender_pan": "VVLKR4510I",
        "sender_dob": "1975-06-14",
        "sender_bank": "ICIC",
        "sender_ifsc": "AXIS0861",
        "sender_vpa": "acc29699@okaxis",
        "receiver_account_id": "EXT99999",
        "receiver_name": "Unknown Beneficiary",
        "receiver_pan": "",
        "receiver_dob": "",
        "receiver_bank": "HDFC",
        "receiver_vpa": "unknown@okhdfc",
        "receiver_state": "",
        "receiver_city": "",
        "tx_location_city": "Dubai",
        "tx_location_state": "",
        "tx_location_country": "AE",
        "tx_location_lat": "25.2048",
        "tx_location_lon": "55.2708",
        "device_id": "DEV-UNKNOWN-9",
        "purpose_code": "P0099",
        "is_cross_border": "1",
        "fx_usd_inr": "83.2",
        "usd_equiv": "5769",
        "beneficiary_id": "BENE-NEW-1",
        "tx_status": "SUCCESS",
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sample, f, indent=2)
    print(f"Wrote editable sample -> {path}")
    print("Edit it (keep an EXISTING sender_account_id/sender_pan for context), then run:")
    print(f"   python -m L2_transaction_monitor.run_new --json {path}")


def _register(dl, tx):
    """Make the new transaction a first-class participant in the context so the
    sibling/graph/cross-border detectors include it."""
    dl.transactions.append(tx)
    s = tx.get("sender_account_id")
    r = tx.get("receiver_account_id")
    if s:
        dl.tx_out[s].append(tx)
    if r:
        dl.tx_in[r].append(tx)
    xb = tx.get("is_cross_border")
    if xb == "1" or xb is True:
        dl.xborder_by_pan[tx.get("sender_pan", "")].append(tx)


def _print_context(dl, tx):
    """Show how much dataset context exists for this transaction's sender."""
    s = tx.get("sender_account_id", "")
    acc = dl.account_for(s)
    print("DATASET CONTEXT FOR SENDER")
    print("-" * 70)
    print(f"  account in account_details.csv : {'YES' if acc else 'NO (no C4/C6 account context)'}")
    if acc:
        for k in ("account_age_days", "kyc_status", "account_dormancy_days",
                  "travel_profile", "home_city", "home_country"):
            if acc.get(k) not in (None, ""):
                print(f"     {k:<22} {acc.get(k)}")
    print(f"  prior history legs             : {len(dl.history.get(s, []))}")
    # -1 because we just registered the new tx itself as a sibling
    print(f"  sibling outbound txns (sender) : {max(len(dl.tx_out.get(s, [])) - 1, 0)}")
    print(f"  cross-border legs for this PAN : {len(dl.xborder_by_pan.get(tx.get('sender_pan',''), []))}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="Path to a JSON file holding ONE transaction")
    ap.add_argument("--make-sample", metavar="PATH",
                    help="Write an editable sample transaction to PATH and exit")
    args = ap.parse_args()

    if args.make_sample:
        _make_sample(args.make_sample)
        return
    if not args.json:
        ap.error("provide --json <file> (or --make-sample <file> to create one)")

    with open(args.json, encoding="utf-8") as f:
        tx = json.load(f)

    dl = DataLayer()
    _register(dl, tx)

    _print_row(tx)
    _print_context(dl, tx)

    result = monitor_sync(tx, dl)

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
