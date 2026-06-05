"""
T1: Velocity Check
- Hourly and daily transaction frequency analysis
- Structuring detection (amounts near reporting thresholds)
- Linked account proliferation
- Volume spike detection vs historical average
- Funds flow pattern analysis
"""

async def check_velocity(transaction: dict) -> float:
    """
    Analyzes the transaction for velocity-based suspicious patterns.
    Returns a composite score between 0.0 and 1.0.
    """
    scores = []
    scores.append(await _hourly_burst_score(transaction))
    scores.append(await _daily_spike_score(transaction))
    scores.append(await _structuring_score(transaction))
    scores.append(await _linked_accounts_score(transaction))
    scores.append(await _funds_pattern_score(transaction))
    scores.append(await _value_spike_score(transaction))

    # Use max-weighted blend: take the max of individual scores
    # and blend with weighted average to avoid dilution
    weights = [0.20, 0.15, 0.20, 0.15, 0.15, 0.15]
    weighted_avg = sum(w * s for w, s in zip(weights, scores))

    # Also count how many sub-signals fired (> 0.5)
    fired = sum(1 for s in scores if s > 0.5)
    top_score = max(scores) if scores else 0.0

    # Multi-signal convergence: if 3+ signals fire, boost aggressively
    if fired >= 4:
        composite = 0.5 * top_score + 0.5 * weighted_avg + 0.15
    elif fired >= 3:
        composite = 0.45 * top_score + 0.55 * weighted_avg + 0.1
    elif fired >= 2:
        composite = 0.4 * top_score + 0.6 * weighted_avg + 0.05
    else:
        composite = 0.3 * top_score + 0.7 * weighted_avg

    return min(max(composite, 0.0), 1.0)


# ── Sub-checks ──────────────────────────────────────────────────────────


async def _hourly_burst_score(transaction: dict) -> float:
    """High score when hourly txn count is abnormally high."""
    txn_1h = transaction.get("txn_count_1h", 0)
    avg_monthly = transaction.get("avg_monthly_txn_count", 1)

    # Expected hourly rate = avg_monthly / (30 days * 12 working hours)
    expected_hourly = max(avg_monthly / 360, 0.05)
    ratio = txn_1h / expected_hourly

    # Also score raw count — more than 5 txns/hour is unusual regardless
    raw_score = 0.0
    if txn_1h >= 10:
        raw_score = 0.95
    elif txn_1h >= 6:
        raw_score = 0.75
    elif txn_1h >= 4:
        raw_score = 0.5

    ratio_score = 0.0
    if ratio >= 30:
        ratio_score = 1.0
    elif ratio >= 15:
        ratio_score = 0.9
    elif ratio >= 8:
        ratio_score = 0.75
    elif ratio >= 4:
        ratio_score = 0.55
    elif ratio >= 2:
        ratio_score = 0.3

    return max(raw_score, ratio_score)


async def _daily_spike_score(transaction: dict) -> float:
    """High score when 24h txn count is a large fraction of monthly average."""
    txn_24h = transaction.get("txn_count_24h", 0)
    avg_monthly = transaction.get("avg_monthly_txn_count", 1)

    ratio = txn_24h / max(avg_monthly, 1)

    # Ghost account: 19 txns in 24h vs avg 4/month → ratio = 4.75
    if ratio >= 3.0:
        return 1.0
    elif ratio >= 1.5:
        return 0.9
    elif ratio >= 0.7:
        return 0.75
    elif ratio >= 0.4:
        return 0.55
    elif ratio >= 0.2:
        return 0.35

    # Also flag high raw daily count
    if txn_24h >= 15:
        return 0.7
    elif txn_24h >= 10:
        return 0.5

    return 0.05


async def _structuring_score(transaction: dict) -> float:
    """
    Detect amounts just below common Indian reporting thresholds:
      - ₹50,000  (UPI per-txn soft limit / CTR threshold)
      - ₹2,00,000 (cash deposit CTR)
      - ₹5,00,000 (high-value alert threshold)
      - ₹10,00,000 (CTR aggregate / RTGS minimum)
    """
    amount = transaction.get("amount", 0)
    score = 0.0

    # ₹50K threshold: amounts in 45K-49,999 band
    if 45000 <= amount <= 49999:
        proximity = 1.0 - (50000 - amount) / 5000
        score = max(score, 0.7 + 0.3 * proximity)

    # ₹2L threshold: amounts in 1.8L-1.99L band
    if 180000 <= amount <= 199999:
        proximity = 1.0 - (200000 - amount) / 20000
        score = max(score, 0.6 + 0.3 * proximity)

    # ₹5L threshold: amounts in 4.5L-4.99L band
    if 450000 <= amount <= 499999:
        proximity = 1.0 - (500000 - amount) / 50000
        score = max(score, 0.55 + 0.3 * proximity)

    # ₹10L threshold: amounts in 9L-9.99L band
    if 900000 <= amount <= 999999:
        proximity = 1.0 - (1000000 - amount) / 100000
        score = max(score, 0.55 + 0.35 * proximity)

    # Very large amounts get a baseline
    if amount >= 1000000:
        score = max(score, 0.45)
    elif amount >= 500000:
        score = max(score, 0.35)
    elif amount >= 200000:
        score = max(score, 0.2)

    return score


async def _linked_accounts_score(transaction: dict) -> float:
    """High score when many linked accounts (suggests mule network)."""
    linked = transaction.get("linked_accounts_count", 0)

    if linked >= 10:
        return 1.0
    elif linked >= 8:
        return 0.9
    elif linked >= 6:
        return 0.75
    elif linked >= 4:
        return 0.55
    elif linked >= 3:
        return 0.35
    elif linked >= 2:
        return 0.15
    return 0.0


async def _funds_pattern_score(transaction: dict) -> float:
    """Keyword analysis on the funds_in_out_pattern text field."""
    pattern = (transaction.get("funds_in_out_pattern") or "").lower()

    suspicious_keywords = [
        ("split", 0.25),
        ("sub-", 0.2),
        ("immediately", 0.25),
        ("forwarded", 0.3),
        ("near zero", 0.3),
        ("lump sum", 0.2),
        ("multiple", 0.15),
        ("different accounts", 0.2),
        ("distributed", 0.2),
        ("dormant", 0.25),
        ("unknown corporate", 0.25),
        ("within", 0.1),
    ]

    clean_keywords = [
        ("regular", -0.2),
        ("consistent pattern", -0.25),
        ("predictable", -0.2),
        ("salary credit", -0.2),
        ("bill payment", -0.15),
    ]

    score = 0.0
    for keyword, delta in suspicious_keywords + clean_keywords:
        if keyword in pattern:
            score += delta

    return min(max(score, 0.0), 1.0)


async def _value_spike_score(transaction: dict) -> float:
    """
    Compare current txn amount to average monthly txn value.
    Extreme spikes indicate anomalous behaviour.
    """
    amount = transaction.get("amount", 0)
    avg_value = transaction.get("avg_monthly_txn_value_inr", 1)
    if avg_value <= 0:
        avg_value = 1

    ratio = amount / avg_value

    if ratio >= 15:
        return 1.0
    elif ratio >= 8:
        return 0.9
    elif ratio >= 4:
        return 0.8
    elif ratio >= 2:
        return 0.65
    elif ratio >= 1.0:
        return 0.45
    elif ratio >= 0.5:
        return 0.25
    return 0.05
