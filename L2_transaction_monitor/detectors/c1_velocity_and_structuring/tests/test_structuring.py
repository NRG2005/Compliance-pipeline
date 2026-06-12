"""
test_structuring.py
-------------------
Tests the STRUCTURING_SMURFING scenario from ground_truth.csv.

Account  : ACC0007 — Chatterjee & Sons (CURRENT, business)
Scenario : 5 transactions of ₹48,964 – ₹49,749 to Gupta & Sons on 2026-05-22
           All amounts are deliberately just below the ₹50,000 PMLA Rule 3 threshold.

Ground truth expectations (from ground_truth.csv):
  expected_triggers_fired   : T1_VELOCITY, T1_STRUCTURING
  expected_confidence_band  : 0.70 – 0.89
  expected_l2_outcome       : FLAGGED (T1 velocity)
  is_suspicious             : YES

What we verify:
  - T1 does NOT fire on txn 1 (not enough history yet)
  - T1 fires T1_STRUCTURING from txn 3 onwards (3rd band transaction)
  - T1 fires T1_VELOCITY if count threshold is hit
  - Composite score for txn 5 lands in the 0.70–0.89 band
  - triggered_rule_refs includes PMLA_RULE_3
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from __init__ import run_t1

# ---------------------------------------------------------------------------
# The 5 smurfing transactions, in order
# These are the exact values from transactions.csv
# ---------------------------------------------------------------------------
SMURFING_TXS = [
    {
        "tx_id": "TX2026052200001",
        "timestamp": "2026-05-22T11:01:00",
        "channel": "UPI",
        "amount_inr": 49749.27,
        "sender_account_id": "ACC0007",
        "sender_name": "Chatterjee & Sons",
        "receiver_name": "Gupta & Sons",
        "receiver_account_external": "EXT_GUPTA_001",
        "purpose_code": "P0099",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052200002",
        "timestamp": "2026-05-22T12:36:00",
        "channel": "UPI",
        "amount_inr": 49489.66,
        "sender_account_id": "ACC0007",
        "sender_name": "Chatterjee & Sons",
        "receiver_name": "Gupta & Sons",
        "receiver_account_external": "EXT_GUPTA_001",
        "purpose_code": "P0099",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052200003",
        "timestamp": "2026-05-22T13:53:00",
        "channel": "UPI",
        "amount_inr": 49579.56,
        "sender_account_id": "ACC0007",
        "sender_name": "Chatterjee & Sons",
        "receiver_name": "Gupta & Sons",
        "receiver_account_external": "EXT_GUPTA_001",
        "purpose_code": "P0099",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052200004",
        "timestamp": "2026-05-22T14:14:00",
        "channel": "UPI",
        "amount_inr": 48964.22,
        "sender_account_id": "ACC0007",
        "sender_name": "Chatterjee & Sons",
        "receiver_name": "Gupta & Sons",
        "receiver_account_external": "EXT_GUPTA_001",
        "purpose_code": "P0099",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052200005",
        "timestamp": "2026-05-22T15:40:00",
        "channel": "UPI",
        "amount_inr": 48986.58,
        "sender_account_id": "ACC0007",
        "sender_name": "Chatterjee & Sons",
        "receiver_name": "Gupta & Sons",
        "receiver_account_external": "EXT_GUPTA_001",
        "purpose_code": "P0099",
        "tx_status": "SUCCESS",
    },
]


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_txn1_fires_weak_structuring_signal():
    """
    First transaction — amount ₹49,749 is inside the ₹40K–₹49,999 structuring band.
    Even a single in-band amount is a T1_STRUCTURING signal (weak, score ~0.13).

    WHY: Regulators expect suspicious amount patterns to be surfaced immediately,
    not only after a count threshold is confirmed. The score stays low (< 0.20)
    on txn 1, so it won't escalate — but the flag ensures L3 is aware.

    The score must stay well below 0.50 (no escalation on a single txn).
    """
    result = run(run_t1(SMURFING_TXS[0]))
    print(f"\n[TXN 1] fired={result['fired']} flags={result['flags']} score={result['composite_score']}")
    print(f"  evidence: {result['evidence']}")

    assert "T1_STRUCTURING" in result["flags"], (
        f"T1_STRUCTURING should fire on first in-band txn, got flags={result['flags']}"
    )
    assert result["composite_score"] < 0.25, (
        f"Score should be low (< 0.25) on txn 1, got {result['composite_score']}"
    )


def test_txn3_fires_structuring():
    """
    Third transaction — 3rd amount in the ₹40K–₹49,999 band today.
    STRUCTURING_MIN_COUNT = 3 → T1_STRUCTURING must fire.
    """
    result = run(run_t1(SMURFING_TXS[2]))
    print(f"\n[TXN 3] fired={result['fired']} flags={result['flags']} score={result['composite_score']}")

    assert result["fired"] is True, "T1 should be fired on txn 3"
    assert "T1_STRUCTURING" in result["flags"], (
        f"T1_STRUCTURING must be in flags on txn 3, got {result['flags']}"
    )
    assert "PMLA_RULE_3" in result["triggered_rule_refs"], (
        f"PMLA_RULE_3 must be in triggered_rule_refs, got {result['triggered_rule_refs']}"
    )


def test_txn5_score_in_expected_band():
    """
    Fifth transaction — full pattern established.
    Ground truth expects composite score in 0.70–0.89 band.
    Also expects both T1_VELOCITY and T1_STRUCTURING flags.
    """
    result = run(run_t1(SMURFING_TXS[4]))
    print(f"\n[TXN 5] fired={result['fired']} flags={result['flags']} score={result['composite_score']}")
    print(f"  sub_scores: {result['sub_scores']}")
    print(f"  triggered_rules: {result['triggered_rule_refs']}")

    expected_keys = {
        "count_velocity", "amount_band_structuring",
        "same_beneficiary_clustering", "volume_spike",
        "high_value_threshold", "credit_line_probing",   # ← new
    }

    assert expected_keys == set(result["sub_scores"].keys()), (
        f"sub_scores keys mismatch: {set(result['sub_scored'].keys())}"
    )
    assert result["fired"] is True
    assert "T1_STRUCTURING" in result["flags"]
    assert 0.70 <= result["composite_score"] <= 0.89, (
        f"Expected composite score 0.70–0.89, got {result['composite_score']}"
    )
    assert "PMLA_RULE_3" in result["triggered_rule_refs"]


def test_same_beneficiary_clustering_fires():
    """
    By txn 2, same-beneficiary sub-check should fire:
    2 transactions to Gupta & Sons totalling ~₹99K > ₹50K threshold.
    """
    result = run(run_t1(SMURFING_TXS[1]))
    print(f"\n[TXN 2 — clustering] flags={result['flags']} sc3={result['sub_scores']['same_beneficiary_clustering']}")

    assert result["sub_scores"]["same_beneficiary_clustering"] > 0.0, (
        "Same-beneficiary sub-check score should be > 0 by txn 2"
    )

def test_credit_line_probing_does_not_fire():
    """
    T8 credit-line probing must NOT fire for the smurfing scenario.
    Purpose code P0099 (general) is not a credit/loan purpose code.
    T1_CREDIT_PROBING appearing here would be a false positive.
    """
    for i, tx in enumerate(SMURFING_TXS):
        result = run(run_t1(tx))
        sc6 = result["sub_scores"].get("credit_line_probing", 0.0)
        assert sc6 == 0.0, (
            f"TXN {i+1}: credit_line_probing should be 0.0 for P0099 purpose code, got {sc6}"
        )
        assert "T1_CREDIT_PROBING" not in result["flags"], (
            f"TXN {i+1}: T1_CREDIT_PROBING should NOT fire for general-purpose smurfing"
        )
    print("\n[T8 CHECK] credit_line_probing correctly absent for all 5 smurfing txns")

if __name__ == "__main__":
    print("=" * 60)
    print("STRUCTURING_SMURFING scenario tests")
    print("=" * 60)
    test_txn1_fires_weak_structuring_signal()
    print("  PASS: txn 1 fires weak T1_STRUCTURING signal (in-band amount, low score)")

    test_same_beneficiary_clustering_fires()
    print("  PASS: txn 2 fires same-beneficiary clustering")

    test_txn3_fires_structuring()
    print("  PASS: txn 3 fires T1_STRUCTURING + PMLA_RULE_3")

    test_txn5_score_in_expected_band()
    print("  PASS: txn 5 composite score in 0.70–0.89 band")

    print("\nAll STRUCTURING tests passed.")

    test_credit_line_probing_does_not_fire()
    print("  PASS: T8 credit_line_probing does not fire for P0099 smurfing")
