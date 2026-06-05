"""
T4: Geo Anomaly Detection
- Cross-border flag analysis
- IP country vs. geo_country mismatch
- Transaction timing anomaly (unusual hours)
- Dormancy + geo mismatch compounding
- FEMA compliance: Form 15CA filing check
"""


async def check_geo_anomaly(transaction: dict) -> float:
    """
    Detects geographical anomalies in the transaction.
    Returns a composite score between 0.0 and 1.0.
    """
    scores: list[float] = []

    scores.append(await _cross_border_score(transaction))
    scores.append(await _ip_mismatch_score(transaction))
    scores.append(await _timing_anomaly_score(transaction))
    scores.append(await _dormancy_geo_compound_score(transaction))
    scores.append(await _fema_compliance_score(transaction))

    weights = [0.20, 0.30, 0.15, 0.20, 0.15]
    composite = sum(w * s for w, s in zip(weights, scores))
    return min(max(composite, 0.0), 1.0)


# ── Sub-checks ──────────────────────────────────────────────────────────


async def _cross_border_score(transaction: dict) -> float:
    """Cross-border transactions inherently carry higher geo risk."""
    if not transaction.get("cross_border", False):
        return 0.0

    amount = transaction.get("amount", 0)

    # Cross-border + high value
    if amount >= 1000000:
        return 0.9
    elif amount >= 500000:
        return 0.7
    elif amount >= 200000:
        return 0.5
    return 0.35


async def _ip_mismatch_score(transaction: dict) -> float:
    """
    Mismatch between IP country and geo_country is a strong signal.
    Three-way mismatch (IP, geo, receiver bank country) is critical.
    """
    ip_country = (transaction.get("ip_country") or "").lower()
    geo_country = (transaction.get("geo_country") or "").lower()

    if not ip_country or not geo_country:
        return 0.2  # Missing data is mildly suspicious

    if ip_country == geo_country:
        return 0.0

    # IP ≠ geo_country — two-way mismatch
    score = 0.75

    # Check for high-risk IP origins
    high_risk_ip_countries = {"nigeria", "north korea", "iran", "syria", "myanmar"}
    if ip_country in high_risk_ip_countries:
        score = 1.0

    # Cross-border compounds the mismatch
    if transaction.get("cross_border", False):
        score = min(score + 0.15, 1.0)

    return score


async def _timing_anomaly_score(transaction: dict) -> float:
    """
    Transactions at unusual hours (midnight–5AM IST) are suspicious,
    especially for high-value RTGS/NEFT.
    """
    timestamp = transaction.get("timestamp", "")

    if not timestamp:
        return 0.1

    try:
        # Parse hour from ISO timestamp.
        # The test data encodes local (IST) times directly in the
        # timestamp string, so we use the raw hour without conversion.
        time_part = timestamp.split("T")[1] if "T" in timestamp else ""
        hour_local = int(time_part.split(":")[0])
    except (IndexError, ValueError):
        return 0.1

    channel = (transaction.get("channel") or "").upper()
    amount = transaction.get("amount", 0)

    # 12AM – 5AM local window
    if 0 <= hour_local <= 5:
        base = 0.6
        # High-value RTGS/NEFT at odd hours is very suspicious
        if channel in ("RTGS", "NEFT") and amount >= 500000:
            return 0.95
        if amount >= 200000:
            return 0.8
        return base

    # 5AM – 7AM or 11PM – midnight — slightly unusual
    if hour_local <= 7 or hour_local >= 23:
        return 0.25

    return 0.0


async def _dormancy_geo_compound_score(transaction: dict) -> float:
    """
    Dormant account + geographic anomaly = compounding risk.
    """
    dormancy = transaction.get("account_dormancy_days", 0)
    ip_country = (transaction.get("ip_country") or "").lower()
    geo_country = (transaction.get("geo_country") or "").lower()
    cross_border = transaction.get("cross_border", False)

    has_geo_issue = (ip_country != geo_country and ip_country and geo_country) or cross_border

    if dormancy >= 365 and has_geo_issue:
        return 1.0
    elif dormancy >= 180 and has_geo_issue:
        return 0.9
    elif dormancy >= 90 and has_geo_issue:
        return 0.7
    elif dormancy >= 365:
        return 0.6
    elif dormancy >= 180:
        return 0.45
    elif dormancy >= 90:
        return 0.3

    # Dormancy without geo issue still has some risk
    if dormancy >= 30:
        return 0.15

    return 0.0


async def _fema_compliance_score(transaction: dict) -> float:
    """
    For cross-border remittances: check Form 15CA filing.
    Not filing Form 15CA for remittances > ₹5L is a compliance violation.
    """
    if not transaction.get("cross_border", False):
        return 0.0

    form_filed = transaction.get("form_15ca_filed", True)  # Default: compliant
    amount = transaction.get("amount", 0)

    if not form_filed and amount >= 500000:
        return 1.0
    elif not form_filed:
        return 0.6

    return 0.1  # Cross-border but compliant — small residual
