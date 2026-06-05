"""
T2: Watchlist & Entity Risk Check
- FIU-IND sanctioned entity flag (t2_watchlist_hit)
- Negative news flag
- PEP (Politically Exposed Person) check
- KYC weakness indicator
- Prior STR / flag history
- Receiver-type risk assessment
"""


async def check_watchlist(transaction: dict) -> float:
    """
    Checks entity-level risk signals present in the transaction payload.
    Uses pre-computed boolean flags instead of fuzzy name matching.

    Returns a float between 0.0 and 1.0.
    """
    scores: list[float] = []

    scores.append(await _watchlist_hit_score(transaction))
    scores.append(await _negative_news_score(transaction))
    scores.append(await _pep_score(transaction))
    scores.append(await _kyc_weakness_score(transaction))
    scores.append(await _prior_str_score(transaction))
    scores.append(await _receiver_risk_score(transaction))

    # Weighted — watchlist hit dominates when present
    weights = [0.30, 0.15, 0.15, 0.15, 0.15, 0.10]
    composite = sum(w * s for w, s in zip(weights, scores))

    # If watchlist hit or PEP, floor the score
    if transaction.get("t2_watchlist_hit", False):
        composite = max(composite, 0.85)
    if transaction.get("is_pep", False):
        composite = max(composite, 0.7)

    return min(max(composite, 0.0), 1.0)


# ── Sub-checks ──────────────────────────────────────────────────────────


async def _watchlist_hit_score(transaction: dict) -> float:
    """Direct watchlist match is the strongest signal."""
    if transaction.get("t2_watchlist_hit", False):
        return 1.0
    return 0.0


async def _negative_news_score(transaction: dict) -> float:
    """Negative news flag from screening systems."""
    if transaction.get("negative_news_flag", False):
        return 1.0
    return 0.0


async def _pep_score(transaction: dict) -> float:
    """Politically Exposed Person flag."""
    if transaction.get("is_pep", False):
        return 1.0
    return 0.0


async def _kyc_weakness_score(transaction: dict) -> float:
    """
    Weak KYC (e.g. Aadhaar OTP only) increases entity risk,
    especially for high-value transactions.
    """
    kyc = (transaction.get("kyc_status") or "").lower()
    amount = transaction.get("amount", 0)

    if "full" in kyc:
        return 0.0

    # Aadhaar OTP = limited / simplified KYC
    if "aadhaar" in kyc or "otp" in kyc:
        if amount >= 200000:
            return 0.95
        elif amount >= 50000:
            return 0.75
        return 0.55

    # Unknown / missing KYC
    if kyc == "" or "pending" in kyc or "none" in kyc:
        return 1.0

    return 0.3


async def _prior_str_score(transaction: dict) -> float:
    """Prior Suspicious Transaction Reports and flags on this account."""
    strs = transaction.get("previous_strs", 0)
    flags = transaction.get("previous_flags", 0)

    score = 0.0
    if strs >= 2:
        score = 1.0
    elif strs == 1:
        score = 0.75

    # Prior flags add additional risk
    if flags >= 3:
        score = max(score, 0.85)
    elif flags >= 2:
        score = max(score, 0.65)
    elif flags >= 1:
        score = max(score, 0.4)

    return score


async def _receiver_risk_score(transaction: dict) -> float:
    """
    Assess risk based on receiver characteristics.
    Payments bank / individual receivers for large amounts are riskier.
    """
    receiver_type = (transaction.get("receiver_type") or "").lower()
    receiver_bank = (transaction.get("receiver_bank") or "").lower()
    amount = transaction.get("amount", 0)

    score = 0.0

    # Utility / merchant receivers are low risk
    if receiver_type in ("utility", "merchant", "government"):
        return 0.0

    # Payments bank as receiver for large amounts
    if "payments bank" in receiver_bank and amount >= 100000:
        score = max(score, 0.7)
    elif "payments bank" in receiver_bank:
        score = max(score, 0.3)

    # Individual receiver + high value
    if receiver_type == "individual" and amount >= 500000:
        score = max(score, 0.5)
    elif receiver_type == "individual" and amount >= 100000:
        score = max(score, 0.25)

    return score
