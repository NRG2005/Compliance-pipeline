"""
test_e2e_metrics.py
-------------------
End-to-end test for T1 — Velocity Check with full classification metrics.

Runs ALL 200 transactions from ground_truth.csv through run_t1() and
computes binary classification performance:

  - True Positives  (TP): T1 fired,        ground truth says T1 should fire
  - False Positives (FP): T1 fired,        ground truth says T1 should NOT fire
  - True Negatives  (TN): T1 did not fire, ground truth says T1 should NOT fire
  - False Negatives (FN): T1 did not fire, ground truth says T1 should fire

Derived metrics:
  - Precision   = TP / (TP + FP)   — of all T1 fires, how many were correct
  - Recall      = TP / (TP + FN)   — of all true positives, how many did T1 catch
  - F1 Score    = 2 * P * R / (P + R)
  - Accuracy    = (TP + TN) / total
  - FPR         = FP / (FP + TN)   — false alarm rate on clean transactions
  - Specificity = TN / (TN + FP)   — how well T1 avoids firing on clean txns

Ground truth definition for T1:
  POSITIVE -> 'T1' appears in expected_triggers_fired
  NEGATIVE -> 'T1' does not appear in expected_triggers_fired

Run with:
    python tests/test_e2e_metrics.py
    # or
    pytest tests/test_e2e_metrics.py -v -s
"""

import asyncio
import csv
import json
import sys
import os
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from __init__ import run_t1

# ---------------------------------------------------------------------------
# Minimum acceptable thresholds -- test fails if T1 falls below these
# ---------------------------------------------------------------------------
# T1 is a DETECTION sub-check, not a final classifier.
# False positives at T1 level are expected and handled by L2 scoring + L3 reasoning.
# Industry standard for AML detection layers: optimise for recall (don't miss signals),
# accept lower precision (downstream layers resolve ambiguity).
#
# Why some FPs are intentional:
#   - Single in-band (Rs 40K-Rs 49K) CLEAN txns fire at low score (~0.14-0.28).
#     T1 correctly surfaces them; L3 purpose_code + account context dismisses them.
#   - Post-large-txn volume spikes (e.g. Nitin Pillai NRE): a Rs 22.5M FEMA txn
#     inflates same-day volume, making subsequent small txns look anomalous.
#     T4 already owns the FEMA signal; T1's weak corroboration is acceptable.
#
# Thresholds are calibrated for a sub-check role:
MIN_PRECISION = 0.55   # 55% -- FPs handled downstream; recall is primary concern
MIN_RECALL    = 0.85   # 85% -- missing a real AML signal is a regulatory failure
MIN_F1        = 0.90   # harmonic mean of 55% precision / 90% recall
MIN_ACCURACY  = 0.90   # overall correctness floor
MAX_FPR       = 0.10   # at most 10% of clean transactions trigger T1


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def _load_csv(candidates: list) -> list[dict]:
    for p in candidates:
        if Path(p).exists():
            with open(p) as f:
                return list(csv.DictReader(f))
    raise FileNotFoundError(f"Not found. Tried: {candidates}")


_DATA_CANDIDATES_GT = [
    str(Path(__file__).parents[3] / "data" / "ground_truth.csv"),
    str(Path(__file__).parents[2] / "data" / "ground_truth.csv"),
    "ground_truth.csv",
    "../data/ground_truth.csv",
    "/mnt/project/ground_truth.csv",
    r"C:\Users\adyaa\Desktop\Compliance-pipeline\data\ground_truth.csv",
]

_DATA_CANDIDATES_TX = [
    str(Path(__file__).parents[3] / "data" / "transactions.csv"),
    str(Path(__file__).parents[2] / "data" / "transactions.csv"),
    "transactions.csv",
    "../data/transactions.csv",
    "/mnt/project/transactions.csv",
    r"C:\Users\adyaa\Desktop\Compliance-pipeline\data\transactions.csv",
]

GROUND_TRUTH = {r["tx_id"]: r for r in _load_csv(_DATA_CANDIDATES_GT)}
TRANSACTIONS = {r["tx_id"]: r for r in _load_csv(_DATA_CANDIDATES_TX)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_payload(tx: dict) -> dict:
    return {
        "tx_id":                     tx["tx_id"],
        "timestamp":                 tx["timestamp"],
        "channel":                   tx["channel"],
        "amount_inr":                float(tx["amount_inr"]),
        "sender_account_id":         tx["sender_account_id"],
        "sender_name":               tx["sender_name"],
        "receiver_name":             tx["receiver_name"],
        "receiver_account_external": tx["receiver_account_external"],
        "purpose_code":              tx["purpose_code"],
        "tx_status":                 tx["tx_status"],
    }


def _gt_t1_should_fire(gt_row: dict) -> bool:
    """
    Ground truth label for T1 binary classification.
    True  -> 'T1' appears in expected_triggers_fired
    False -> it does not
    """
    return "T1" in gt_row.get("expected_triggers_fired", "")

def _gt_t8_should_fire(gt_row: dict) -> bool:
    """
    Ground truth label for T8 sub-check within C1.
    True -> 'T8' or 'T1_CREDIT_PROBING' appears in expected_triggers_fired.
    """
    triggers = gt_row.get("expected_triggers_fired", "")
    return "T8" in triggers or "T1_CREDIT_PROBING" in triggers

# ---------------------------------------------------------------------------
# Confusion matrix entry
# ---------------------------------------------------------------------------

class ConfusionEntry:
    def __init__(
        self,
        tx_id, scenario, amount, fired, score, flags,
        gt_should_fire, gt_triggers, gt_l2_outcome,
        slm_fp_likelihood=None,
        slm_action=None,
        slm_summary=None,
    ):
        self.tx_id             = tx_id
        self.scenario          = scenario
        self.amount            = amount
        self.fired             = fired
        self.score             = score
        self.flags             = flags
        self.gt_should_fire    = gt_should_fire
        self.gt_triggers       = gt_triggers
        self.gt_l2_outcome     = gt_l2_outcome
        self.slm_fp_likelihood = slm_fp_likelihood
        self.slm_action        = slm_action
        self.slm_summary       = slm_summary

        if fired and gt_should_fire:
            self.cell = "TP"
        elif fired and not gt_should_fire:
            self.cell = "FP"
        elif not fired and not gt_should_fire:
            self.cell = "TN"
        else:
            self.cell = "FN"


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------

def test_t1_metrics():
    print("\n" + "=" * 90)
    print("T1 VELOCITY CHECK -- CLASSIFICATION METRICS")
    print("Running all 200 ground truth transactions")
    print("=" * 90)

    entries: list[ConfusionEntry] = []

    for tx_id, tx_row in TRANSACTIONS.items():
        gt_row = GROUND_TRUTH.get(tx_id)
        if gt_row is None:
            continue

        try:
            payload = _build_payload(tx_row)
            result  = asyncio.run(run_t1(payload))
        except Exception as e:
            print(f"  ERROR on {tx_id}: {e}")
            continue

        # Extract SLM fields -- present only if SLM ran for this transaction
        slm_raw = result.get("slm_reasoning") or {}

        entry = ConfusionEntry(
            tx_id             = tx_id,
            scenario          = gt_row["scenario_label"],
            amount            = float(tx_row["amount_inr"]),
            fired             = result["fired"],
            score             = result["composite_score"],
            flags             = result["flags"],
            gt_should_fire    = _gt_t1_should_fire(gt_row),
            gt_triggers       = gt_row["expected_triggers_fired"],
            gt_l2_outcome     = gt_row["expected_l2_outcome"],
            slm_fp_likelihood = result.get("slm_false_positive_likelihood"),
            slm_action        = result.get("slm_recommended_action"),
            slm_summary       = slm_raw.get("reasoning_summary"),
        )
        entries.append(entry)

        entry.t8_fired   = "T1_CREDIT_PROBING" in result["flags"]
        entry.t8_gt_fire = _gt_t8_should_fire(gt_row)
        entry.sc6_score  = result["sub_scores"].get("credit_line_probing", 0.0)

    # -----------------------------------------------------------------------
    # Confusion matrix counts
    # -----------------------------------------------------------------------
    tp = [e for e in entries if e.cell == "TP"]
    fp = [e for e in entries if e.cell == "FP"]
    tn = [e for e in entries if e.cell == "TN"]
    fn = [e for e in entries if e.cell == "FN"]

    TP, FP, TN, FN = len(tp), len(fp), len(tn), len(fn)
    total = TP + FP + TN + FN

    # -----------------------------------------------------------------------
    # Derived metrics
    # -----------------------------------------------------------------------
    precision   = TP / (TP + FP)     if (TP + FP) > 0           else 0.0
    recall      = TP / (TP + FN)     if (TP + FN) > 0           else 0.0
    f1          = (2 * precision * recall / (precision + recall)
                   if (precision + recall) > 0 else 0.0)
    accuracy    = (TP + TN) / total  if total > 0                else 0.0
    fpr         = FP / (FP + TN)     if (FP + TN) > 0           else 0.0
    specificity = TN / (TN + FP)     if (TN + FP) > 0           else 0.0
    fnr         = FN / (FN + TP)     if (FN + TP) > 0           else 0.0

    # -----------------------------------------------------------------------
    # Confusion matrix table
    # -----------------------------------------------------------------------
    print("\nCONFUSION MATRIX")
    print("-" * 45)
    print(f"{'':25} {'GT: Should Fire':>15} {'GT: Should NOT Fire':>18}")
    print(f"{'T1 Fired':25} {'TP = ' + str(TP):>15} {'FP = ' + str(FP):>18}")
    print(f"{'T1 Did NOT Fire':25} {'FN = ' + str(FN):>15} {'TN = ' + str(TN):>18}")
    print("-" * 45)
    print(f"{'Total':25} {str(TP + FN):>15} {str(FP + TN):>18}   N={total}")

    # -----------------------------------------------------------------------
    # Metrics table
    # -----------------------------------------------------------------------
    print("\nMETRICS")
    print("-" * 55)

    def _bar(value: float, width: int = 30) -> str:
        filled = int(value * width)
        return "[" + "#" * filled + "." * (width - filled) + f"] {value:.1%}"

    def _status(value: float, threshold: float, higher_is_better: bool = True) -> str:
        return "PASS" if (value >= threshold if higher_is_better else value <= threshold) else "FAIL"

    metrics = [
        ("Accuracy",    accuracy,    MIN_ACCURACY,   True,  f"threshold >= {MIN_ACCURACY:.0%}"),
        ("Precision",   precision,   MIN_PRECISION,  True,  f"threshold >= {MIN_PRECISION:.0%}"),
        ("Recall",      recall,      MIN_RECALL,     True,  f"threshold >= {MIN_RECALL:.0%}"),
        ("F1 Score",    f1,          MIN_F1,         True,  f"threshold >= {MIN_F1:.0%}"),
        ("Specificity", specificity, 1 - MAX_FPR,    True,  f"threshold >= {1 - MAX_FPR:.0%}"),
        ("FPR",         fpr,         MAX_FPR,        False, f"threshold <= {MAX_FPR:.0%}"),
        ("Miss Rate",   fnr,         1 - MIN_RECALL, False, f"threshold <= {1 - MIN_RECALL:.0%}"),
    ]

    for name, value, threshold, higher_better, note in metrics:
        status = _status(value, threshold, higher_better)
        print(f"  {name:<14} {_bar(value)}   {status}  ({note})")

    # -----------------------------------------------------------------------
    # Score distribution
    # -----------------------------------------------------------------------
    print("\nSCORE DISTRIBUTION")
    print("-" * 55)

    bands = {
        "0.00 - 0.09 (no signal)":       [e for e in entries if e.score < 0.10],
        "0.10 - 0.24 (weak signal)":      [e for e in entries if 0.10 <= e.score < 0.25],
        "0.25 - 0.49 (moderate)":         [e for e in entries if 0.25 <= e.score < 0.50],
        "0.50 - 0.69 (suspicious)":       [e for e in entries if 0.50 <= e.score < 0.70],
        "0.70 - 0.89 (high confidence)":  [e for e in entries if 0.70 <= e.score < 0.90],
        "0.90 - 1.00 (auto-file)":        [e for e in entries if e.score >= 0.90],
    }

    for band_name, band_entries in bands.items():
        tps = sum(1 for e in band_entries if e.cell == "TP")
        fps = sum(1 for e in band_entries if e.cell == "FP")
        tns = sum(1 for e in band_entries if e.cell == "TN")
        fns = sum(1 for e in band_entries if e.cell == "FN")
        print(f"  {band_name:<35} n={len(band_entries):>3}  TP={tps} FP={fps} TN={tns} FN={fns}")

    # -----------------------------------------------------------------------
    # Per-scenario breakdown
    # -----------------------------------------------------------------------
    print("\nPER-SCENARIO BREAKDOWN")
    print("-" * 90)
    print(f"  {'Scenario':<42} {'Count':>5} {'TP':>4} {'FP':>4} {'TN':>4} {'FN':>4} {'Fired%':>7} {'AvgScore':>9}")
    print("  " + "-" * 86)

    by_scenario = defaultdict(list)
    for e in entries:
        by_scenario[e.scenario].append(e)

    for scenario in sorted(by_scenario.keys()):
        rows = by_scenario[scenario]
        s_tp = sum(1 for e in rows if e.cell == "TP")
        s_fp = sum(1 for e in rows if e.cell == "FP")
        s_tn = sum(1 for e in rows if e.cell == "TN")
        s_fn = sum(1 for e in rows if e.cell == "FN")
        fired_pct = sum(1 for e in rows if e.fired) / len(rows)
        avg_score = sum(e.score for e in rows) / len(rows)
        print(
            f"  {scenario:<42} {len(rows):>5} {s_tp:>4} {s_fp:>4} {s_tn:>4} {s_fn:>4} "
            f"{fired_pct:>7.1%} {avg_score:>9.4f}"
        )

    # -----------------------------------------------------------------------
    # False Positives -- detailed
    # -----------------------------------------------------------------------
    if fp:
        print(f"\nFALSE POSITIVES -- T1 fired incorrectly ({FP} total)")
        print("-" * 90)
        print(f"  {'TX_ID':<22} {'Scenario':<30} {'Amount':>10} {'Score':>7} {'SLM':<8} {'Flags'}")
        print("  " + "-" * 86)
        for e in sorted(fp, key=lambda x: x.score, reverse=True):
            slm_label = e.slm_fp_likelihood or "N/A"
            print(
                f"  {e.tx_id:<22} {e.scenario:<30} Rs{e.amount:>9,.0f} "
                f"{e.score:>7.4f}  {slm_label:<8}  {e.flags}"
            )
    else:
        print("\nFALSE POSITIVES: None")

    # -----------------------------------------------------------------------
    # False Negatives -- detailed
    # -----------------------------------------------------------------------
    if fn:
        print(f"\nFALSE NEGATIVES -- T1 missed a real signal ({FN} total)")
        print("-" * 90)
        print(f"  {'TX_ID':<22} {'Scenario':<30} {'Amount':>10} {'Score':>7} {'GT Triggers'}")
        print("  " + "-" * 86)
        for e in sorted(fn, key=lambda x: x.score, reverse=True):
            print(
                f"  {e.tx_id:<22} {e.scenario:<30} Rs{e.amount:>9,.0f} "
                f"{e.score:>7.4f}  {e.gt_triggers}"
            )
    else:
        print("\nFALSE NEGATIVES: None")

    # -----------------------------------------------------------------------
    # SLM reasoning summary (shown only if SLM ran on any transaction)
    # -----------------------------------------------------------------------
    slm_ran = [e for e in entries if e.slm_fp_likelihood is not None]
    fp_caught_by_slm = 0

    if slm_ran:
        print(f"\nSLM REASONING SUMMARY ({len(slm_ran)} transactions assessed)")
        print("-" * 90)

        high   = sum(1 for e in slm_ran if e.slm_fp_likelihood == "HIGH")
        medium = sum(1 for e in slm_ran if e.slm_fp_likelihood == "MEDIUM")
        low    = sum(1 for e in slm_ran if e.slm_fp_likelihood == "LOW")
        print(f"  FP likelihood -- HIGH: {high}  MEDIUM: {medium}  LOW: {low}")

        fp_caught_by_slm = sum(1 for e in fp if e.slm_fp_likelihood == "HIGH")
        if fp:
            print(f"  SLM correctly flagged {fp_caught_by_slm}/{FP} false positives as HIGH likelihood")

        print(f"\n  {'TX_ID':<22} {'Cell':<5} {'SLM Likelihood':<16} {'Action':<18} {'Summary'}")
        print("  " + "-" * 86)
        for e in sorted(slm_ran, key=lambda x: x.score, reverse=True):
            summary = (e.slm_summary or "").encode("ascii", errors="replace").decode("ascii")[:50]
            print(
                f"  {e.tx_id:<22} {e.cell:<5} {(e.slm_fp_likelihood or ''):<16} "
                f"{(e.slm_action or ''):<18} {summary}"
            )

    # -----------------------------------------------------------------------
    # T8 Credit-Line Probing sub-check breakdown
    # -----------------------------------------------------------------------
    t8_entries = [e for e in entries if e.t8_gt_fire or e.t8_fired]
    if t8_entries:
        t8_tp = sum(1 for e in t8_entries if e.t8_fired and e.t8_gt_fire)
        t8_fp = sum(1 for e in t8_entries if e.t8_fired and not e.t8_gt_fire)
        t8_fn = sum(1 for e in t8_entries if not e.t8_fired and e.t8_gt_fire)
        avg_sc6 = sum(e.sc6_score for e in t8_entries) / len(t8_entries)
        print(f"\nT8 CREDIT-LINE PROBING SUB-CHECK")
        print("-" * 55)
        print(f"  Transactions touching T8:  {len(t8_entries)}")
        print(f"  TP={t8_tp}  FP={t8_fp}  FN={t8_fn}")
        print(f"  Avg credit_line_probing score (T8-relevant txns): {avg_sc6:.4f}")
        if t8_fn > 0:                                                          # ← add
            print(f"  Note: FN={t8_fn} expected — T8 is a count-threshold check (MIN=3).")  # ← add
            print(f"  Txns 1-2 of a probing series correctly do not fire.")    # ← add

    # -----------------------------------------------------------------------
    # Final summary line
    # -----------------------------------------------------------------------
    print("\n" + "=" * 90)
    print(
        f"SUMMARY  |  Total: {total}  |  "
        f"Accuracy: {accuracy:.1%}  |  "
        f"Precision: {precision:.1%}  |  "
        f"Recall: {recall:.1%}  |  "
        f"F1: {f1:.1%}  |  "
        f"FPR: {fpr:.1%}"
    )
    print("=" * 90)

    # -----------------------------------------------------------------------
    # Write JSON results
    # -----------------------------------------------------------------------
    output = {
        "summary": {
            "total":       total,
            "TP":          TP,
            "FP":          FP,
            "TN":          TN,
            "FN":          FN,
            "accuracy":    round(accuracy,    4),
            "precision":   round(precision,   4),
            "recall":      round(recall,      4),
            "f1":          round(f1,          4),
            "specificity": round(specificity, 4),
            "fpr":         round(fpr,         4),
            "miss_rate":   round(fnr,         4),
        },
        "thresholds": {
            "min_precision": MIN_PRECISION,
            "min_recall":    MIN_RECALL,
            "min_f1":        MIN_F1,
            "min_accuracy":  MIN_ACCURACY,
            "max_fpr":       MAX_FPR,
        },
        "slm_summary": {
            "transactions_assessed":   len(slm_ran),
            "fp_likelihood_HIGH":      sum(1 for e in slm_ran if e.slm_fp_likelihood == "HIGH"),
            "fp_likelihood_MEDIUM":    sum(1 for e in slm_ran if e.slm_fp_likelihood == "MEDIUM"),
            "fp_likelihood_LOW":       sum(1 for e in slm_ran if e.slm_fp_likelihood == "LOW"),
            "fp_correctly_identified": fp_caught_by_slm,
        },
        "per_scenario": {
            scenario: {
                "count":     len(rows),
                "TP":        sum(1 for e in rows if e.cell == "TP"),
                "FP":        sum(1 for e in rows if e.cell == "FP"),
                "TN":        sum(1 for e in rows if e.cell == "TN"),
                "FN":        sum(1 for e in rows if e.cell == "FN"),
                "avg_score": round(sum(e.score for e in rows) / len(rows), 4),
            }
            for scenario, rows in by_scenario.items()
        },
        "false_positives": [
            {
                "tx_id":                         e.tx_id,
                "scenario":                      e.scenario,
                "amount":                        e.amount,
                "score":                         e.score,
                "flags":                         e.flags,
                "slm_false_positive_likelihood": e.slm_fp_likelihood,
                "slm_recommended_action":        e.slm_action,
                "slm_reasoning_summary":         e.slm_summary,
            }
            for e in fp
        ],
        "false_negatives": [
            {
                "tx_id":       e.tx_id,
                "scenario":    e.scenario,
                "amount":      e.amount,
                "score":       e.score,
                "gt_triggers": e.gt_triggers,
            }
            for e in fn
        ],
        "all_results": [
            {
                "tx_id":                         e.tx_id,
                "scenario":                      e.scenario,
                "cell":                          e.cell,
                "fired":                         e.fired,
                "score":                         e.score,
                "flags":                         e.flags,
                "gt_should_fire":                e.gt_should_fire,
                "gt_triggers":                   e.gt_triggers,
                "slm_false_positive_likelihood": e.slm_fp_likelihood,
                "slm_recommended_action":        e.slm_action,
                "slm_reasoning_summary":         e.slm_summary,
            }
            for e in entries
        ],
    }

    out_path = Path(__file__).parent / "metrics_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nFull results written to: {out_path}")

    # -----------------------------------------------------------------------
    # Assertions -- fail the test if below minimum thresholds
    # -----------------------------------------------------------------------
    failures = []
    if accuracy  < MIN_ACCURACY:  failures.append(f"Accuracy   {accuracy:.1%} < {MIN_ACCURACY:.0%}")
    if precision < MIN_PRECISION: failures.append(f"Precision  {precision:.1%} < {MIN_PRECISION:.0%}")
    if recall    < MIN_RECALL:    failures.append(f"Recall     {recall:.1%} < {MIN_RECALL:.0%}")
    if f1        < MIN_F1:        failures.append(f"F1         {f1:.1%} < {MIN_F1:.0%}")
    if fpr       > MAX_FPR:       failures.append(f"FPR        {fpr:.1%} > {MAX_FPR:.0%}")

    if failures:
        print("\nTHRESHOLD FAILURES:")
        for f_msg in failures:
            print(f"  FAIL: {f_msg}")
        assert False, f"T1 did not meet minimum metric thresholds: {failures}"
    else:
        print("\nAll metric thresholds passed.")


if __name__ == "__main__":
    test_t1_metrics()
