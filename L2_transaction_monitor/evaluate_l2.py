"""
evaluate_l2.py  —  Whole-dataset evaluation of the Layer 2 Transaction Monitor

Runs the six detectors (C1-C6) in parallel for every transaction in
transactions.csv via the L2 orchestrator, then scores the single system-wide
flag against the `is_suspicious` column in ground_truth.csv.

Output: ONE confusion matrix + precision / recall / F1 / accuracy for the whole
L2 layer (not six separate ones), plus a per-category contribution breakdown and
a per-trigger accuracy table to show where each category is pulling its weight.

Run:
    python3 evaluate_l2.py                 # full 2000-tx run
    python3 evaluate_l2.py --limit 200     # quick smoke run
    python3 evaluate_l2.py --errors        # also list misclassified tx
"""

import argparse
import asyncio
import csv
import os
import sys
import time
from collections import Counter, defaultdict

# Work whether run as a module (python -m L2_transaction_monitor.evaluate_l2)
# or as a plain script from inside the folder (python evaluate_l2.py).
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)
try:
    from L2_transaction_monitor.data_layer import DataLayer
    from L2_transaction_monitor.orchestrator import monitor, WEIGHTS
except ImportError:
    from data_layer import DataLayer
    from orchestrator import monitor, WEIGHTS


def _load_ground_truth(dl):
    gt = {}
    path = os.path.join(dl.dir, "ground_truth.csv")
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            gt[r["tx_id"]] = {
                "is_suspicious": 1 if r["is_suspicious"].strip().upper() == "YES" else 0,
                "primary_category": r["primary_category"],
                "scenario": r["scenario_label"],
                "expected_triggers": r["expected_triggers_fired"],
            }
    return gt


async def _run_all(dl, gt, limit=None):
    rows = dl.transactions[:limit] if limit else dl.transactions
    results = []
    # bounded concurrency keeps memory flat on the full set
    sem = asyncio.Semaphore(64)

    async def one(row):
        async with sem:
            return await monitor(row, dl)

    results = await asyncio.gather(*(one(r) for r in rows))
    return rows, results


def evaluate(limit=None, show_errors=False):
    dl = DataLayer()
    gt = _load_ground_truth(dl)

    t0 = time.perf_counter()
    rows, results = asyncio.run(_run_all(dl, gt, limit))
    elapsed = time.perf_counter() - t0

    tp = fp = tn = fn = 0
    errors = []
    # per-category: how many true-suspicious tx did this category catch / mis-fire
    cat_tp = Counter()    # category fired AND tx is truly suspicious
    cat_fp = Counter()    # category fired AND tx is clean
    cat_only_catch = Counter()  # category was the ONLY one firing on a true positive
    by_primary = defaultdict(lambda: [0, 0])   # primary_category -> [caught, total]

    for row, res in zip(rows, results):
        g = gt.get(row["tx_id"])
        if g is None:
            continue
        y = g["is_suspicious"]
        pred = 1 if res["flag"] else 0

        if y == 1 and pred == 1:
            tp += 1
        elif y == 0 and pred == 1:
            fp += 1
        elif y == 0 and pred == 0:
            tn += 1
        else:
            fn += 1

        for c in res["fired_categories"]:
            if y == 1:
                cat_tp[c] += 1
            else:
                cat_fp[c] += 1
        if y == 1 and len(res["fired_categories"]) == 1:
            cat_only_catch[res["fired_categories"][0]] += 1

        if y == 1:
            pc = g["primary_category"]
            by_primary[pc][1] += 1
            if pred == 1:
                by_primary[pc][0] += 1

        if pred != y:
            errors.append((row["tx_id"], g["primary_category"], g["scenario"], y, pred,
                           res["fired_categories"], res["suspicion_score"]))

    n = tp + fp + tn + fn
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    acc = (tp + tn) / n if n else 0.0

    print("=" * 66)
    print(f"LAYER 2 TRANSACTION MONITOR — whole-dataset evaluation")
    print(f"transactions: {n}   runtime: {elapsed:.1f}s   "
          f"({1000*elapsed/n:.1f} ms/tx)")
    print("=" * 66)
    print(f"                pred SUSPICIOUS   pred CLEAN")
    print(f"  true SUSPICIOUS   {tp:>6}          {fn:>6}")
    print(f"  true CLEAN        {fp:>6}          {tn:>6}")
    print("-" * 66)
    print(f"  Precision {prec:.3f}   Recall {rec:.3f}   F1 {f1:.3f}   Accuracy {acc:.3f}")
    print("=" * 66)

    print("\nPer-category contribution (fired on true-suspicious / on clean):")
    print(f"  {'cat':4} {'weight':>6}  {'caught':>7}  {'mis-fired':>9}  {'sole-catch':>10}")
    for c in ["C1", "C2", "C3", "C4", "C5", "C6"]:
        print(f"  {c:4} {WEIGHTS[c]:>6.2f}  {cat_tp[c]:>7}  {cat_fp[c]:>9}  {cat_only_catch[c]:>10}")

    print("\nRecall by primary category (of truly-suspicious tx):")
    for pc in sorted(by_primary):
        caught, total = by_primary[pc]
        r = caught / total if total else 0.0
        print(f"  {pc:6}  {caught:>4}/{total:<4}  recall={r:.3f}")

    if show_errors and errors:
        print("\n" + "-" * 66)
        print(f"Misclassified ({len(errors)}):")
        for txid, pc, sc, y, pred, fired, score in errors[:80]:
            kind = "FN" if y == 1 else "FP"
            print(f"  [{kind}] {txid} {pc:6} {sc:28} fired={fired} score={score}")
        if len(errors) > 80:
            print(f"  ... and {len(errors) - 80} more")

    return f1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--errors", action="store_true")
    args = ap.parse_args()
    evaluate(limit=args.limit, show_errors=args.errors)
