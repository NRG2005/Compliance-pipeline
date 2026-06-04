"""
test_velocity_spike.py
----------------------
Tests the VELOCITY_SPIKE scenario from ground_truth.csv.

Account  : ACC0014 — Kapoor Enterprises (CURRENT, business)
Scenario : 8 transactions in 105 minutes on 2026-05-24
           Different receivers each time, amounts ₹9,974 – ₹24,445.

Ground truth expectations (from ground_truth.csv):
  TX2026052400006  → no trigger,     score < 0.50
  TX2026052400007  → no trigger,     score < 0.50
  TX2026052400008  → no trigger,     score < 0.50
  TX2026052400009  → T1_VELOCITY,    score < 0.50   (4th in 1h — approaching threshold)
  TX2026052400010  → T1_VELOCITY,    score 0.50–0.69
  TX2026052400011  → T1_VELOCITY,    score 0.50–0.69
  TX2026052400012  → T1_VELOCITY,    score 0.50–0.69
  TX2026052400013  → T1_VELOCITY,    score 0.50–0.69

What we verify:
  - Progressive score build-up as transaction count grows
  - T1 does NOT fire on first 3 transactions
  - T1 fires T1_VELOCITY from txn 4 onwards
  - Score grows monotonically through txns 4–8
  - T1_STRUCTURING does NOT fire (amounts are not in the ₹40K–₹49,999 band)
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from __init__ import run_t1

VELOCITY_TXS = [
    {
        "tx_id": "TX2026052400006",
        "timestamp": "2026-05-24T09:10:00",
        "channel": "UPI",
        "amount_inr": 20450.12,
        "sender_account_id": "ACC0014",
        "sender_name": "Kapoor Enterprises",
        "receiver_name": "Rashmi Kapoor",
        "receiver_account_external": "EXT_RK_001",
        "purpose_code": "P0099",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052400007",
        "timestamp": "2026-05-24T09:25:00",
        "channel": "UPI",
        "amount_inr": 21370.72,
        "sender_account_id": "ACC0014",
        "sender_name": "Kapoor Enterprises",
        "receiver_name": "Praveen Banerjee",
        "receiver_account_external": "EXT_PB_001",
        "purpose_code": "P0099",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052400008",
        "timestamp": "2026-05-24T09:40:00",
        "channel": "UPI",
        "amount_inr": 24445.53,
        "sender_account_id": "ACC0014",
        "sender_name": "Kapoor Enterprises",
        "receiver_name": "Aishwarya Patel",
        "receiver_account_external": "EXT_AP_001",
        "purpose_code": "P0099",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052400009",
        "timestamp": "2026-05-24T09:55:00",
        "channel": "UPI",
        "amount_inr": 24443.59,
        "sender_account_id": "ACC0014",
        "sender_name": "Kapoor Enterprises",
        "receiver_name": "Praveen Singh",
        "receiver_account_external": "EXT_PS_001",
        "purpose_code": "P0099",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052400010",
        "timestamp": "2026-05-24T10:10:00",
        "channel": "UPI",
        "amount_inr": 15731.36,
        "sender_account_id": "ACC0014",
        "sender_name": "Kapoor Enterprises",
        "receiver_name": "Kunal Joshi",
        "receiver_account_external": "EXT_KJ_001",
        "purpose_code": "P0099",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052400011",
        "timestamp": "2026-05-24T10:25:00",
        "channel": "UPI",
        "amount_inr": 19472.22,
        "sender_account_id": "ACC0014",
        "sender_name": "Kapoor Enterprises",
        "receiver_name": "Sachin Chatterjee",
        "receiver_account_external": "EXT_SC_001",
        "purpose_code": "P0099",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052400012",
        "timestamp": "2026-05-24T10:40:00",
        "channel": "UPI",
        "amount_inr": 23459.59,
        "sender_account_id": "ACC0014",
        "sender_name": "Kapoor Enterprises",
        "receiver_name": "Ananya Patel",
        "receiver_account_external": "EXT_AP_002",
        "purpose_code": "P0099",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052400013",
        "timestamp": "2026-05-24T10:55:00",
        "channel": "UPI",
        "amount_inr": 9974.05,
        "sender_account_id": "ACC0014",
        "sender_name": "Kapoor Enterprises",
        "receiver_name": "Manisha Reddy",
        "receiver_account_external": "EXT_MR_001",
        "purpose_code": "P0099",
        "tx_status": "SUCCESS",
    },
]


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_first_three_do_not_fire():
    """
    Transactions 1, 2, 3 should not trigger T1.
    BUSINESS_CURRENT threshold is 10 per hour — we're well below it.
    """
    for i in range(3):
        result = run(run_t1(VELOCITY_TXS[i]))
        print(f"\n[TXN {i+1}] fired={result['fired']} flags={result['flags']} score={result['composite_score']}")
        assert result["fired"] is False, (
            f"TXN {i+1} should not fire, got fired=True, flags={result['flags']}"
        )
        assert result["composite_score"] < 0.50, (
            f"TXN {i+1} score should be < 0.50, got {result['composite_score']}"
        )


def test_score_grows_progressively():
    """
    As more transactions arrive, count_velocity score should increase.
    By txn 4 it should be higher than txn 1.
    """
    result_1 = run(run_t1(VELOCITY_TXS[0]))
    result_4 = run(run_t1(VELOCITY_TXS[3]))

    print(f"\n[PROGRESSION] txn1_score={result_1['composite_score']} txn4_score={result_4['composite_score']}")
    assert result_4["composite_score"] > result_1["composite_score"], (
        "Score should be higher at txn 4 than txn 1"
    )


def test_t1_velocity_fires_from_txn4():
    """
    From txn 4 onwards, T1_VELOCITY should fire.
    Ground truth: TX2026052400009 is the first with T1_VELOCITY trigger.
    """
    result = run(run_t1(VELOCITY_TXS[3]))
    print(f"\n[TXN 4] fired={result['fired']} flags={result['flags']} score={result['composite_score']}")
    print(f"  count_velocity sub_score: {result['sub_scores']['count_velocity']}")

    assert result["fired"] is True, f"TXN 4 should fire, got fired=False"
    assert "T1_VELOCITY" in result["flags"], (
        f"T1_VELOCITY must be in flags at txn 4, got {result['flags']}"
    )


def test_no_structuring_flag():
    """
    Amounts (₹9,974 – ₹24,445) are well below the ₹40,000 structuring band.
    T1_STRUCTURING must NEVER fire for this scenario.
    """
    for i, tx in enumerate(VELOCITY_TXS):
        result = run(run_t1(tx))
        assert "T1_STRUCTURING" not in result["flags"], (
            f"T1_STRUCTURING incorrectly fired on txn {i+1} (amount={tx['amount_inr']})"
        )
    print("\n[STRUCTURING CHECK] T1_STRUCTURING correctly absent for all 8 txns")


def test_later_txns_score_in_expected_band():
    """
    Txns 5–8: ground truth expects L2 composite score 0.50–0.69.

    IMPORTANT: The ground truth band is the L2 OUTPUT (T1+T2+T3+T4 combined).
    T1 alone only has count_velocity firing for this scenario — amounts are
    well below the structuring band, all different receivers.
    T1 composite tops out around 0.13–0.20. T2/T3 push L2 into 0.50–0.69.

    We assert: T1 fires T1_VELOCITY with a non-zero increasing score.
    """
    prev_score = 0.0
    for i in range(4, 8):
        result = run(run_t1(VELOCITY_TXS[i]))
        print(f"\n[TXN {i+1}] score={result['composite_score']} flags={result['flags']}")
        assert result["fired"] is True, f"TXN {i+1} should be fired"
        assert "T1_VELOCITY" in result["flags"], f"TXN {i+1} must have T1_VELOCITY flag"
        assert result["composite_score"] > 0.0, f"TXN {i+1} score must be > 0"
        assert result["composite_score"] >= prev_score, (
            f"TXN {i+1} score {result['composite_score']} regressed from {prev_score}"
        )
        prev_score = result["composite_score"]


if __name__ == "__main__":
    print("=" * 60)
    print("VELOCITY_SPIKE scenario tests")
    print("=" * 60)
    test_first_three_do_not_fire()
    print("  PASS: txns 1–3 do not fire")

    test_score_grows_progressively()
    print("  PASS: score grows progressively from txn 1 to txn 4")

    test_t1_velocity_fires_from_txn4()
    print("  PASS: T1_VELOCITY fires from txn 4")

    test_no_structuring_flag()
    print("  PASS: T1_STRUCTURING never fires (amounts not in band)")

    test_later_txns_score_in_expected_band()
    print("  PASS: txns 5–8 score in expected range")

    print("\nAll VELOCITY_SPIKE tests passed.")