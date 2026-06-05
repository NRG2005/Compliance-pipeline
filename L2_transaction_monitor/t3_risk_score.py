"""
T3: Adaptive Risk Score
- Account maturity assessment
- Transaction amount vs. historical profile
- Occupation / income plausibility
- Dormancy-based reactivation risk
- Pre-computed risk label anchor (t3_risk_label)
- Prior flag / STR memory
- Transaction type and channel context
"""


async def calculate_risk_score(transaction: dict) -> float:
    """
    Calculates a composite risk score for the transaction based on
    account characteristics, behavioural deviation, and contextual signals.

    Returns a float between 0.0 and 1.0.
    """
    scores: list[float] = []

    scores.append(await _account_maturity_score(transaction))
    scores.append(await _amount_deviation_score(transaction))
    scores.append(await _occupation_plausibility_score(transaction))
    scores.append(await _dormancy_reactivation_score(transaction))
    scores.append(await _risk_label_anchor(transaction))
    scores.append(await _prior_flags_score(transaction))
    scores.append(await _txn_context_score(transaction))

    weights = [0.12, 0.22, 0.12, 0.12, 0.14, 0.14, 0.14]
    weighted_avg = sum(w * s for w, s in zip(weights, scores))

    # Signal convergence: count how many sub-signals are elevated (> 0.5)
    fired = sum(1 for s in scores if s > 0.5)
    top_score = max(scores) if scores else 0.0

    if fired >= 5:
        composite = 0.4 * top_score + 0.6 * weighted_avg + 0.15
    elif fired >= 4:
        composite = 0.4 * top_score + 0.6 * weighted_avg + 0.1
    elif fired >= 3:
        composite = 0.35 * top_score + 0.65 * weighted_avg + 0.05
    else:
        composite = 0.3 * top_score + 0.7 * weighted_avg

    return min(max(composite, 0.0), 1.0)


# ── Sub-checks ──────────────────────────────────────────────────────────


async def _account_maturity_score(transaction: dict) -> float:
    """
    Newer accounts carry higher inherent risk.
    RBI simplified-KYC accounts < 12 months are under enhanced monitoring.
    """
    age_days = transaction.get("account_age_days", 0)

    if age_days <= 30:
        return 1.0
    elif age_days <= 60:
        return 0.9
    elif age_days <= 90:
        return 0.8
    elif age_days <= 180:
        return 0.65
    elif age_days <= 365:
        return 0.4
    elif age_days <= 730:
        return 0.15
    return 0.05


async def _amount_deviation_score(transaction: dict) -> float:
    """
    Compare current transaction amount against the account's
    average monthly transaction value.
    High multiples → anomalous.
    """
    amount = transaction.get("amount", 0)
    avg_monthly_value = transaction.get("avg_monthly_txn_value_inr", 1)

    if avg_monthly_value <= 0:
        avg_monthly_value = 1

    ratio = amount / avg_monthly_value

    if ratio >= 15:
        return 1.0
    elif ratio >= 8:
        return 0.9
    elif ratio >= 4:
        return 0.85
    elif ratio >= 2:
        return 0.7
    elif ratio >= 1.0:
        return 0.5
    elif ratio >= 0.5:
        return 0.3
    elif ratio >= 0.1:
        return 0.15
    return 0.05


async def _occupation_plausibility_score(transaction: dict) -> float:
    """
    Flag when transaction amount is implausible for declared occupation.
    Only scored when occupation_category is present.
    """
    occupation = (transaction.get("occupation_category") or "").lower()
    amount = transaction.get("amount", 0)

    if not occupation:
        # No occupation data — penalty scales with amount
        if amount >= 500000:
            return 0.4
        elif amount >= 100000:
            return 0.25
        return 0.1

    # Low-income occupation categories
    low_income = ["daily wage", "student", "unemployed", "homemaker", "agriculture"]
    is_low_income = any(cat in occupation for cat in low_income)

    if is_low_income:
        if amount >= 200000:
            return 1.0
        elif amount >= 100000:
            return 0.85
        elif amount >= 50000:
            return 0.65
        return 0.2

    # Salaried — generally consistent
    if "salaried" in occupation or "professional" in occupation:
        if amount >= 2000000:
            return 0.5
        return 0.05

    # Business — higher amounts plausible
    if "business" in occupation or "self-employed" in occupation:
        if amount >= 5000000:
            return 0.4
        return 0.05

    return 0.1


async def _dormancy_reactivation_score(transaction: dict) -> float:
    """
    Accounts dormant > 365 days that suddenly transact are high-risk
    (RBI requires re-KYC after 12-month dormancy).
    """
    dormancy = transaction.get("account_dormancy_days", 0)

    if dormancy >= 365:
        return 1.0
    elif dormancy >= 180:
        return 0.8
    elif dormancy >= 90:
        return 0.55
    elif dormancy >= 30:
        return 0.3
    return 0.0


async def _risk_label_anchor(transaction: dict) -> float:
    """
    Use the pre-computed t3_risk_label as an anchoring signal.
    This represents the upstream risk-tier classification.
    """
    label = (transaction.get("t3_risk_label") or "").upper()

    if label == "HIGH":
        return 0.9
    elif label == "MEDIUM":
        return 0.5
    elif label == "LOW":
        return 0.1
    return 0.3


async def _prior_flags_score(transaction: dict) -> float:
    """Prior flags and STRs as a risk memory signal."""
    flags = transaction.get("previous_flags", 0)
    strs = transaction.get("previous_strs", 0)

    score = 0.0
    if strs >= 2:
        score = 1.0
    elif strs == 1:
        score = 0.75

    if flags >= 3:
        score = max(score, 0.85)
    elif flags >= 2:
        score = max(score, 0.65)
    elif flags >= 1:
        score = max(score, 0.4)

    return score


async def _txn_context_score(transaction: dict) -> float:
    """
    Transaction type + channel context.
    Fund transfers are inherently riskier than bill payments.
    High-value fund transfers via UPI are unusual.
    """
    txn_type = (transaction.get("transaction_type") or "").lower()
    channel = (transaction.get("channel") or "").upper()
    amount = transaction.get("amount", 0)

    score = 0.0

    # Transaction type base risk
    if txn_type in ("fund_transfer", "remittance_outward"):
        score = 0.35
    elif txn_type in ("cash_withdrawal", "cash_deposit"):
        score = 0.3
    elif txn_type in ("bill_payment", "utility_payment"):
        score = 0.0

    # Channel context
    if channel == "UPI" and amount >= 200000:
        # UPI with very large amount is unusual (UPI limit typically ₹1L)
        score = max(score, 0.6)
    elif channel == "RTGS" and amount >= 1000000:
        # RTGS for large amounts: depends on dormancy context
        score = max(score, 0.4)

    # Receiver type context
    receiver_type = (transaction.get("receiver_type") or "").lower()
    if receiver_type == "utility" or receiver_type == "merchant":
        score = min(score, 0.1)

    return score
