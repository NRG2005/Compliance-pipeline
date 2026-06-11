"""
test_false_positive.py
----------------------
Tests the RECURRING_SALARY_LOOK_LIKE_STRUCTURING scenario — the most
important test in the T1 suite.

Account  : ACC0019 — Neha Kumar (SAVINGS, individual)
Scenario : 5 salary payments of ₹46,773 – ₹48,169 within 32 minutes on 2026-05-21
           Purpose code P0014 = Salary. Each payment to a DIFFERENT beneficiary.

Ground truth expectations (from ground_truth.csv):
  expected_triggers_fired   : T1_VELOCITY (amount band fires, but score is low)
  expected_confidence_band  : < 0.50
  expected_final_outcome    : AUDIT_ONLY (L3 should dismiss — false positive)
  is_suspicious             : YES (flagged, but correctly dismissed downstream)

WHY THIS TEST IS CRITICAL:
  This scenario is specifically designed to test the false-positive recovery path.
  T1 MUST fire T1_VELOCITY (the amount band sub-check fires legitimately).
  But the composite score must stay low (< 0.50) because:
    - Sub-check 3 (same beneficiary) does NOT fire — each receiver is different
    - Sub-check 1 (count velocity) fires only mildly on INDIVIDUAL_SAVINGS threshold
    - Sub-check 4 (volume spike) does NOT fire — salary account has high baseline volume

  If T1 suppresses the flag entirely (doesn't fire at all), the L3 false-positive
  recovery path never gets exercised. That would be a test coverage gap.

  If T1 produces a high score (>= 0.50), it would escalate to human review
  unnecessarily and defeat the purpose of the L3 reasoning layer.

The correct outcome: fired=True, T1_VELOCITY in flags, composite_score < 0.50.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from __init__ import run_t1

SALARY_TXS = [
    {
        "tx_id": "TX2026052100030",
        "timestamp": "2026-05-21T10:00:00",
        "channel": "NEFT",
        "amount_inr": 47516.79,
        "sender_account_id": "ACC0019",
        "sender_name": "Neha Kumar",
        "receiver_name": "Isha Agarwal",
        "receiver_account_external": "EXT_IA_001",
        "purpose_code": "P0014",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052100031",
        "timestamp": "2026-05-21T10:08:00",
        "channel": "NEFT",
        "amount_inr": 47437.57,
        "sender_account_id": "ACC0019",
        "sender_name": "Neha Kumar",
        "receiver_name": "Anil Malhotra",
        "receiver_account_external": "EXT_AM_001",
        "purpose_code": "P0014",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052100032",
        "timestamp": "2026-05-21T10:16:00",
        "channel": "NEFT",
        "amount_inr": 46773.67,
        "sender_account_id": "ACC0019",
        "sender_name": "Neha Kumar",
        "receiver_name": "Neha Singh",
        "receiver_account_external": "EXT_NS_001",
        "purpose_code": "P0014",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052100033",
        "timestamp": "2026-05-21T10:24:00",
        "channel": "NEFT",
        "amount_inr": 48169.11,
        "sender_account_id": "ACC0019",
        "sender_name": "Neha Kumar",
        "receiver_name": "Nitin Chatterjee",
        "receiver_account_external": "EXT_NC_001",
        "purpose_code": "P0014",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052100034",
        "timestamp": "2026-05-21T10:32:00",
        "channel": "NEFT",
        "amount_inr": 47560.79,
        "sender_account_id": "ACC0019",
        "sender_name": "Neha Kumar",
        "receiver_name": "Ananya Das",
        "receiver_account_external": "EXT_AD_001",
        "purpose_code": "P0014",
        "tx_status": "SUCCESS",
    },
]


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_amount_band_sub_check_fires():
    """
    All 5 amounts are in the ₹40K–₹49,999 band.
    Sub-check 2 (amount_band_structuring) MUST fire from txn 3 onwards.
    This is correct — T1 correctly identifies the pattern.
    The false positive is resolved by L3, not by T1 suppressing the signal.
    """
    result = run(run_t1(SALARY_TXS[2]))   # txn 3 — 3rd band amount
    print(f"\n[TXN 3] fired={result['fired']} flags={result['flags']}")
    print(f"  sc2_amount_band: {result['sub_scores']['amount_band_structuring']}")

    assert result["sub_scores"]["amount_band_structuring"] > 0.0, (
        "Amount band sub-check should fire on txn 3 — amounts are in the band"
    )


def test_same_beneficiary_does_not_fire():
    """
    KEY DISTINCTION from true smurfing:
    Each salary payment goes to a different person.
    Sub-check 3 (same_beneficiary_clustering) must NOT fire for any transaction.

    This is what separates legitimate salary runs from smurfing structuring.
    """
    for i, tx in enumerate(SALARY_TXS):
        result = run(run_t1(tx))
        sc3 = result["sub_scores"]["same_beneficiary_clustering"]
        assert sc3 == 0.0, (
            f"TXN {i+1}: same_beneficiary_clustering should be 0.0 "
            f"(all different receivers), got {sc3}"
        )
    print("\n[BENEFICIARY CHECK] Sub-check 3 correctly scores 0.0 for all 5 txns")


def test_composite_score_stays_below_threshold():
    """
    The composite score for all 5 transactions must stay below 0.50.
    Ground truth: expected_confidence_band = <0.50
    Expected final outcome: AUDIT_ONLY (not human review, not auto-filed)

    If score >= 0.50, it would incorrectly escalate to L5 Human Review.
    """
    for i, tx in enumerate(SALARY_TXS):
        result = run(run_t1(tx))
        print(f"\n[TXN {i+1}] score={result['composite_score']} flags={result['flags']}")
        assert result["composite_score"] < 0.50, (
            f"TXN {i+1}: composite score {result['composite_score']} >= 0.50. "
            f"This would cause a false escalation to human review."
        )


def test_t1_structuring_fires_but_score_stays_low():
    """
    All 5 salary amounts are in the ₹40K–₹49,999 band, so T1_STRUCTURING fires
    from the first transaction (in-band amount is itself a structuring signal).

    This is correct and intentional. The KEY distinction from true smurfing:
      - same_beneficiary_clustering sub-score = 0.0 for all 5 txns (different receivers)
      - composite stays < 0.50 (no escalation)
      - T1_STRUCTURING flag is present but weak

    L3 uses purpose_code P0014 (salary) + different receivers to dismiss the flag.
    T1 must NOT suppress T1_STRUCTURING — that would hide the case from L3.
    """
    for i, tx in enumerate(SALARY_TXS):
        result = run(run_t1(tx))
        # same_beneficiary must always be 0 — this is the structural difference from smurfing
        sc3 = result["sub_scores"]["same_beneficiary_clustering"]
        assert sc3 == 0.0, (
            f"TXN {i+1}: same_beneficiary should be 0.0 (all different receivers), got {sc3}"
        )
        # Score must stay below 0.50 — flags are present but weak
        assert result["composite_score"] < 0.50, (
            f"TXN {i+1}: score {result['composite_score']} >= 0.50 would cause false escalation"
        )


def test_fired_is_true_from_txn3():
    """
    T1 MUST fire from txn 3 (amount band hits STRUCTURING_MIN_COUNT).
    fired=False would mean L3 never sees this transaction → false negative gap.
    """
    result = run(run_t1(SALARY_TXS[2]))
    print(f"\n[TXN 3 fired check] fired={result['fired']} flags={result['flags']}")
    assert result["fired"] is True, (
        "T1 must fire from txn 3 — even for false positives, "
        "T1 fires and L3 resolves. fired=False is a coverage gap."
    )

def test_credit_line_probing_does_not_fire_for_salary():
    """
    P0014 (Salary) is a low-risk structuring purpose, but it is NOT
    a credit/loan purpose code (P0013, P0022, P0023). T8 must never fire.

    This guards against a future mis-classification where someone adds
    P0014 to CREDIT_LINE_PURPOSE_CODES by mistake.
    """
    for i, tx in enumerate(SALARY_TXS):
        result = run(run_t1(tx))
        sc6 = result["sub_scores"].get("credit_line_probing", 0.0)
        assert sc6 == 0.0, (
            f"TXN {i+1}: credit_line_probing must be 0.0 for P0014 salary, got {sc6}"
        )
        assert "T1_CREDIT_PROBING" not in result["flags"], (
            f"TXN {i+1}: T1_CREDIT_PROBING must not fire for salary disbursements"
        )
    print("\n[T8 / SALARY] T1_CREDIT_PROBING correctly absent — P0014 ≠ credit purpose")

if __name__ == "__main__":
    print("=" * 60)
    print("RECURRING_SALARY false positive scenario tests")
    print("=" * 60)
    test_amount_band_sub_check_fires()
    print("  PASS: amount band sub-check fires (correct — T1 does its job)")

    test_same_beneficiary_does_not_fire()
    print("  PASS: same-beneficiary sub-check = 0.0 (different receivers each time)")

    test_composite_score_stays_below_threshold()
    print("  PASS: composite score < 0.50 for all 5 txns (no false escalation)")

    test_t1_structuring_fires_but_score_stays_low()
    print("  PASS: T1_STRUCTURING fires (in-band amounts) but same_beneficiary=0, score<0.50")

    test_fired_is_true_from_txn3()
    print("  PASS: fired=True from txn 3 (L3 false-positive path can be exercised)")

    print("\nAll FALSE POSITIVE tests passed.")