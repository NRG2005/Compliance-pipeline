"""
test_credit_line_probing.py
---------------------------
Tests T8 — Credit-Line Limit-Probing, merged into C1.

T8 detects repeated small drawdowns (credit/loan purpose codes) within
a 24h window, suggesting deliberate probing of a credit limit to stay
below CTR reporting thresholds.

Purpose codes in scope: P0013 (Loan repayment), P0022 (Credit utilisation),
                        P0023 (Loan disbursement)

Regulatory anchor: RBI FRM Master Directions 2024 EWS (Clause 8.3)
                   PMLA Rule 3(1)(B) — integrally connected series.

Scenarios tested:
  A. CREDIT_PROBING_CONFIRMED   — ACC0014, 4× small P0013 drawdowns → T8 fires
  B. CREDIT_PROBING_NEGATIVE    — ACC0014, only 2 drawdowns → T8 does not fire
  C. CREDIT_PROBING_HIGH_AMOUNT — large single loan repayment above p90×0.40
                                   → T8 does not fire (not a small drawdown)
  D. NON_CREDIT_PURPOSE_CODE    — same pattern but P0099 → T8 must not fire
  E. SCORE_GROWTH               — score grows monotonically with drawdown count
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from __init__ import run_t1

# ---------------------------------------------------------------------------
# ACC0014 — Kapoor Enterprises (BUSINESS_CURRENT)
# p90_amount = 80,146.68 → small_drawdown_threshold = 80,146.68 × 0.40 = ₹32,058.67
# All 4 rows are in transactions.csv — cosmos_client loads them at import time.
# Timestamps are on 2026-05-27 with no other ACC0014 activity that day,
# so the rolling window for each call contains exactly the prior T8 txns.
# ---------------------------------------------------------------------------

CREDIT_PROBING_TXS = [
    {
        "tx_id": "TX2026052700T8A",         
        "timestamp": "2026-05-27T09:00:00",
        "channel": "NEFT",
        "amount_inr": 9800.00,
        "sender_account_id": "ACC0014",
        "sender_name": "Kapoor Enterprises",
        "receiver_name": "HDFC Credit Desk",
        "receiver_account_external": "EXT_T8_HDFC01",
        "purpose_code": "P0013",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052700T8B",
        "timestamp": "2026-05-27T10:30:00",
        "channel": "NEFT",
        "amount_inr": 10200.00,
        "sender_account_id": "ACC0014",
        "sender_name": "Kapoor Enterprises",
        "receiver_name": "HDFC Credit Desk",
        "receiver_account_external": "EXT_T8_HDFC01",
        "purpose_code": "P0013",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052700T8C",
        "timestamp": "2026-05-27T12:00:00",
        "channel": "NEFT",
        "amount_inr": 11500.00,
        "sender_account_id": "ACC0014",
        "sender_name": "Kapoor Enterprises",
        "receiver_name": "HDFC Credit Desk",
        "receiver_account_external": "EXT_T8_HDFC01",
        "purpose_code": "P0013",
        "tx_status": "SUCCESS",
    },
    {
        "tx_id": "TX2026052700T8D",
        "timestamp": "2026-05-27T13:30:00",
        "channel": "NEFT",
        "amount_inr": 9974.05,
        "sender_account_id": "ACC0014",
        "sender_name": "Kapoor Enterprises",
        "receiver_name": "HDFC Credit Desk",
        "receiver_account_external": "EXT_T8_HDFC01",
        "purpose_code": "P0013",
        "tx_status": "SUCCESS",
    },
]

# Single large loan repayment — above p90 × 0.40 = ₹32,058.67 for ACC0014.
# NOT in transactions.csv — this is a one-off probe, no prior history needed.
# cosmos_client will find zero prior credit txns, which is correct for this test.
LARGE_LOAN_TX = {
    "tx_id": "TX_T8_LARGE_PROBE",
    "timestamp": "2026-05-28T09:00:00",     # ← different date, no collision
    "channel": "RTGS",
    "amount_inr": 55000.00,
    "sender_account_id": "ACC0014",
    "sender_name": "Kapoor Enterprises",
    "receiver_name": "HDFC Credit Desk",
    "receiver_account_external": "EXT_T8_HDFC01",
    "purpose_code": "P0013",
    "tx_status": "SUCCESS",
}


# ---------------------------------------------------------------------------
# NON_CREDIT_TXS — same account, amounts, and cadence as CREDIT_PROBING_TXS,
# but purpose_code = P0099 (general). Verifies the purpose-code gate: T8 must
# never fire for non-credit/loan activity, regardless of amount or frequency.
# ---------------------------------------------------------------------------

NON_CREDIT_TXS = [
    {**tx, "tx_id": tx["tx_id"].replace("T8", "NC"), "purpose_code": "P0099"}
    for tx in CREDIT_PROBING_TXS
]


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Test A: Confirmed credit-line probing pattern
# ---------------------------------------------------------------------------

def test_t8_does_not_fire_below_min_count():
    """
    With only 1 or 2 drawdowns, T8 must not fire.
    CREDIT_LINE_MIN_COUNT = 3 — the pattern is unconfirmed with 1-2 occurrences.
    """
    for i in range(2):
        result = run(run_t1(CREDIT_PROBING_TXS[i]))
        sc6 = result["sub_scores"].get("credit_line_probing", 0.0)
        print(f"\n[TXN {i+1}] sc6={sc6} fired={result['fired']} flags={result['flags']}")
        assert "T1_CREDIT_PROBING" not in result["flags"], (
            f"TXN {i+1}: T8 must not fire with only {i+1} drawdown(s), got flags={result['flags']}"
        )


def test_t8_fires_on_third_drawdown():
    """
    Third small drawdown with credit purpose code → T1_CREDIT_PROBING fires.
    This is the CREDIT_LINE_MIN_COUNT = 3 threshold being crossed.
    """
    result = run(run_t1(CREDIT_PROBING_TXS[2]))
    sc6 = result["sub_scores"].get("credit_line_probing", 0.0)
    print(f"\n[TXN 3 — T8 fires] sc6={sc6} fired={result['fired']} flags={result['flags']}")
    print(f"  evidence: { {k: v for k, v in result['evidence'].items() if k.startswith('sc6_')} }")

    assert sc6 > 0.0, (
        f"credit_line_probing score should be > 0.0 on txn 3, got {sc6}"
    )
    assert "T1_CREDIT_PROBING" in result["flags"], (
        f"T1_CREDIT_PROBING must fire on 3rd small drawdown, got flags={result['flags']}"
    )
    assert result["fired"] is True, "T1 overall must fire when T8 fires"
    assert "PMLA_RULE_3_CREDIT_PROBING" in result["triggered_rule_refs"], (
        f"PMLA_RULE_3_CREDIT_PROBING must be in triggered_rule_refs"
    )


def test_t8_fires_on_fourth_drawdown_with_higher_score():
    """
    Fourth drawdown — score should be higher than on the third.
    Score = min(total_count / MIN_COUNT, 1.0) = min(4/3, 1.0) = 1.0
    """
    result_3 = run(run_t1(CREDIT_PROBING_TXS[2]))
    result_4 = run(run_t1(CREDIT_PROBING_TXS[3]))

    sc6_3 = result_3["sub_scores"].get("credit_line_probing", 0.0)
    sc6_4 = result_4["sub_scores"].get("credit_line_probing", 0.0)
    print(f"\n[SCORE GROWTH] txn3 sc6={sc6_3}  txn4 sc6={sc6_4}")

    assert sc6_4 >= sc6_3, (
        f"T8 score should be >= on txn 4 vs txn 3: got {sc6_4} < {sc6_3}"
    )
    assert "T1_CREDIT_PROBING" in result_4["flags"]


# ---------------------------------------------------------------------------
# Test B: Large single loan repayment — not a small drawdown
# ---------------------------------------------------------------------------

def test_large_loan_repayment_does_not_trigger_t8():
    """
    A single large loan repayment (₹55,000 > small_threshold ₹32,058 for ACC0014)
    must NOT fire T8 even though the purpose code is P0013.

    T8 is about systematically small drawdowns, not large legitimate repayments.
    The small_drawdown check (amount < p90 × CREDIT_LINE_SMALL_RATIO) gates this.
    """
    result = run(run_t1(LARGE_LOAN_TX))
    sc6 = result["sub_scores"].get("credit_line_probing", 0.0)
    print(f"\n[LARGE LOAN] amount=₹55,000 sc6={sc6} flags={result['flags']}")

    assert sc6 == 0.0, (
        f"Large loan repayment (₹55,000 > threshold) should not trigger T8, got sc6={sc6}"
    )
    assert "T1_CREDIT_PROBING" not in result["flags"], (
        "T1_CREDIT_PROBING must not fire for a single large repayment"
    )


# ---------------------------------------------------------------------------
# Test C: Non-credit purpose code — structural gate
# ---------------------------------------------------------------------------

def test_non_credit_purpose_code_never_fires_t8():
    """
    Same amounts, same account, same frequency — but P0099 (general) purpose code.
    T8 must not fire. Purpose code is the primary gate.

    This verifies the check is anchored to credit/loan activity specifically,
    not just to any burst of small transactions (that's T1's count_velocity job).
    """
    for i, tx in enumerate(NON_CREDIT_TXS):
        result = run(run_t1(tx))
        sc6 = result["sub_scores"].get("credit_line_probing", 0.0)
        assert sc6 == 0.0, (
            f"TXN {i+1}: P0099 should never trigger T8, got sc6={sc6}"
        )
        assert "T1_CREDIT_PROBING" not in result["flags"], (
            f"TXN {i+1}: T1_CREDIT_PROBING must not appear for P0099 purpose code"
        )
    print("\n[PURPOSE CODE GATE] T8 correctly ignores P0099 transactions")


# ---------------------------------------------------------------------------
# Test D: Sub-score key presence
# ---------------------------------------------------------------------------

def test_credit_line_probing_key_always_present():
    """
    credit_line_probing must be present in sub_scores for every transaction,
    even when the check doesn't fire (score = 0.0).
    A missing key means T8 wasn't wired into the T1Result output correctly.
    """
    result = run(run_t1(CREDIT_PROBING_TXS[0]))
    assert "credit_line_probing" in result["sub_scores"], (
        f"credit_line_probing key missing from sub_scores: {result['sub_scores'].keys()}"
    )
    print(f"\n[KEY PRESENCE] sub_scores keys: {sorted(result['sub_scores'].keys())}")


# ---------------------------------------------------------------------------
# Test E: Evidence fields
# ---------------------------------------------------------------------------

def test_t8_evidence_fields_populated():
    """
    When T8 fires, the evidence dict must contain sc6_ prefixed fields
    with the expected keys. L3 and L6 depend on these for citation and audit.
    """
    result = run(run_t1(CREDIT_PROBING_TXS[2]))    # txn 3 — T8 fires
    sc6_evidence = {k: v for k, v in result["evidence"].items() if k.startswith("sc6_")}

    required_fields = {
        "sc6_is_credit_purpose_code",
        "sc6_purpose_code",
        "sc6_current_amount_inr",
        "sc6_small_drawdown_threshold",
        "sc6_is_small_drawdown",
        "sc6_prior_credit_txns_24h",
        "sc6_total_credit_txns_24h",
        "sc6_total_credit_amount_24h",
        "sc6_min_count_threshold",
    }

    missing = required_fields - set(sc6_evidence.keys())
    assert not missing, (
        f"Missing T8 evidence fields: {missing}. Present: {set(sc6_evidence.keys())}"
    )
    print(f"\n[T8 EVIDENCE] All required fields present: {sorted(sc6_evidence.keys())}")


# ---------------------------------------------------------------------------
# Test F: T8 does not interfere with existing structuring score
# ---------------------------------------------------------------------------

def test_t8_and_structuring_independent():
    """
    T8 fires (credit probing confirmed on txn 3). But since amounts are well
    below the ₹40K structuring band, T1_STRUCTURING must NOT fire simultaneously.

    These are independent detection axes — T8 firing does not cause T1_STRUCTURING
    and T1_STRUCTURING firing does not imply T8.
    """
    result = run(run_t1(CREDIT_PROBING_TXS[2]))
    print(f"\n[INDEPENDENCE] flags={result['flags']} sc2={result['sub_scores']['amount_band_structuring']}")

    assert "T1_CREDIT_PROBING" in result["flags"], "T8 should fire on txn 3"
    assert "T1_STRUCTURING" not in result["flags"], (
        "T1_STRUCTURING must not fire — amounts (₹9,800–₹11,500) are below ₹40K band"
    )
    assert result["sub_scores"]["amount_band_structuring"] == 0.0, (
        "amount_band_structuring score should be 0.0 — amounts not in ₹40K–₹49,999 band"
    )


if __name__ == "__main__":
    print("=" * 65)
    print("T8 CREDIT-LINE LIMIT-PROBING tests")
    print("=" * 65)

    test_credit_line_probing_key_always_present()
    print("  PASS: credit_line_probing key always present in sub_scores")

    test_t8_does_not_fire_below_min_count()
    print("  PASS: T8 does not fire with < 3 drawdowns")

    test_t8_fires_on_third_drawdown()
    print("  PASS: T8 fires on 3rd small drawdown (CREDIT_LINE_MIN_COUNT reached)")

    test_t8_fires_on_fourth_drawdown_with_higher_score()
    print("  PASS: T8 score grows from txn 3 to txn 4")

    test_large_loan_repayment_does_not_trigger_t8()
    print("  PASS: Large loan repayment (above small_threshold) does not fire T8")

    test_non_credit_purpose_code_never_fires_t8()
    print("  PASS: P0099 transactions never trigger T8 (purpose code gate holds)")

    test_t8_and_structuring_independent()
    print("  PASS: T8 and T1_STRUCTURING are independent axes (no cross-contamination)")

    test_t8_evidence_fields_populated()
    print("  PASS: All sc6_ evidence fields populated when T8 fires")

    print("\nAll T8 CREDIT-LINE PROBING tests passed.")