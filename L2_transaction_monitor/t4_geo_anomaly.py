"""
T4: Geo Anomaly
---------------
Deterministic geo-location anomaly check (NO language model at this layer).

It answers one question: "is the LOCATION of this transaction unusual for this
account, given where the account normally transacts from?"

Three independent signals are combined into one 0.0–1.0 score:

  1. NEW / RARE location   — current location vs the account's historical
                             location distribution (the "moving average of
                             account state" — a rolling frequency of where the
                             account transacts).
  2. FOREIGN jurisdiction  — current country differs from the account's home
                             country; weighted higher for FATF high-risk states.
  3. IMPOSSIBLE TRAVEL     — distance from the previous transaction location is
                             too large for the elapsed time (only evaluated when
                             coordinates + a previous timestamp are available).

Input contract
--------------
transaction: dict — must contain a `location` field. Accepted shapes:
    "Mumbai, IN"
    {"city": "Mumbai", "country": "IN", "lat": 19.07, "lon": 72.87}
  plus the usual `timestamp` (ISO-8601) for impossible-travel timing.

account_history: dict — the account's geo state. All keys optional; the check
  degrades gracefully if absent:
    {
      "home_country": "IN",
      "known_locations": {"Mumbai": 120, "Pune": 18}   # or ["Mumbai", "Pune"]
      "last_location": {"city": "Mumbai", "country": "IN",
                        "lat": 19.07, "lon": 72.87,
                        "timestamp": "2026-05-22T09:00:00"},
    }

Output: dict shaped like the other L2 checks so the aggregator in main.py can
consume it uniformly:
    {"check", "fired", "score", "triggered_rule", "evidence"}
"""

from datetime import datetime
from math import asin, cos, radians, sin, sqrt

# ---------------------------------------------------------------------------
# Thresholds / config — kept here so a policy change is a config change,
# not a code change (same philosophy as t1_velocity/thresholds.py).
# ---------------------------------------------------------------------------

# Score contributions for each signal (combined via "noisy-OR", capped at 1.0).
SCORE_NEW_LOCATION       = 0.50   # location never seen in account history
SCORE_RARE_LOCATION_MAX  = 0.30   # max contribution when location is seen but rare
SCORE_FOREIGN_COUNTRY    = 0.40   # current country != home country
SCORE_FATF_HIGH_RISK     = 0.85   # foreign AND a FATF high-risk jurisdiction
SCORE_IMPOSSIBLE_TRAVEL  = 0.95   # physically implausible movement

# A location seen in fewer than this share of past transactions counts as "rare".
RARE_LOCATION_SHARE = 0.05        # < 5% of history

# Fire (flag for investigation) at or above this combined score.
FIRED_THRESHOLD = 0.50

# Impossible travel: implied speed above this (km/h) is implausible for legit use.
# ~900 km/h ≈ commercial jet cruise; anything faster implies two actors / fraud.
MAX_PLAUSIBLE_SPEED_KMH = 900.0

# FATF "high-risk and other monitored jurisdictions" (illustrative POC subset).
# In production, source this from L7 Regulatory Watch instead of hard-coding.
FATF_HIGH_RISK_COUNTRIES = {
    "KP",  # North Korea
    "IR",  # Iran
    "MM",  # Myanmar
    "SY",  # Syria
    "AF",  # Afghanistan
    "YE",  # Yemen
}

DEFAULT_HOME_COUNTRY = "IN"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _norm(value: str) -> str:
    """Normalise a location/country token for comparison."""
    return (value or "").strip().lower()


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two lat/lon points, in kilometres."""
    r = 6371.0  # Earth radius (km)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _parse_location(raw) -> dict:
    """
    Normalise a transaction `location` field into a uniform shape:
        {"city": str|None, "country": str|None, "lat": float|None, "lon": float|None,
         "key": str}   # `key` is the canonical string used for frequency matching
    Accepts either a plain string ("Mumbai, IN") or a dict.
    """
    city = country = None
    lat = lon = None

    if isinstance(raw, dict):
        city    = raw.get("city") or raw.get("name")
        country = raw.get("country") or raw.get("country_code")
        lat     = raw.get("lat", raw.get("latitude"))
        lon     = raw.get("lon", raw.get("longitude"))
    elif isinstance(raw, str) and raw.strip():
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if parts:
            city = parts[0]
        # A trailing 2-letter token is treated as a country code.
        if len(parts) >= 2 and len(parts[-1]) == 2:
            country = parts[-1]

    # Canonical matching key: prefer city, fall back to country, then raw.
    key = _norm(city) or _norm(country) or _norm(str(raw) if raw is not None else "")

    return {
        "city":    city,
        "country": country.upper() if isinstance(country, str) else country,
        "lat":     float(lat) if lat is not None else None,
        "lon":     float(lon) if lon is not None else None,
        "key":     key,
    }


def _location_frequency(account_history: dict) -> dict:
    """
    Build a {normalised_location_key: count} frequency map from history.
    Accepts `known_locations` as either a dict (location->count) or a list.
    This is the deterministic "moving average of account state".
    """
    known = (account_history or {}).get("known_locations")
    freq: dict[str, int] = {}

    if isinstance(known, dict):
        for loc, count in known.items():
            freq[_norm(loc)] = freq.get(_norm(loc), 0) + int(count)
    elif isinstance(known, (list, tuple)):
        for loc in known:
            freq[_norm(loc)] = freq.get(_norm(loc), 0) + 1

    return freq


# ---------------------------------------------------------------------------
# Main check
# ---------------------------------------------------------------------------

async def check_geo_anomaly(transaction: dict, account_history: dict | None = None) -> dict:
    """
    Detects geographical anomalies in a single transaction.

    Returns a result dict matching the L2 sub-check contract:
        {"check", "fired", "score", "triggered_rule", "evidence"}

    No location on the transaction -> a non-firing result with score 0.0
    (we cannot judge geography we don't have; the pipeline continues).
    """
    account_history = account_history or {}

    raw_location = transaction.get("location")
    loc = _parse_location(raw_location)

    # ---- Guard: nothing to evaluate -------------------------------------
    if not loc["key"]:
        return {
            "check": "T4_GEO_ANOMALY",
            "fired": False,
            "score": 0.0,
            "triggered_rule": None,
            "evidence": {
                "reason":        "no_location_field",
                "raw_location":  raw_location,
                "signals":       [],
            },
        }

    freq = _location_frequency(account_history)
    total_seen = sum(freq.values())
    home_country = (account_history.get("home_country") or DEFAULT_HOME_COUNTRY).upper()

    signals: list[str] = []
    score_components: dict[str, float] = {}

    # ---- Signal 1: new / rare location ----------------------------------
    location_count = freq.get(loc["key"], 0)
    if total_seen == 0:
        # No history at all — can't call it "new" with confidence; treat as mild.
        share = None
    else:
        share = location_count / total_seen

    if total_seen > 0 and location_count == 0:
        signals.append("NEW_LOCATION")
        score_components["new_location"] = SCORE_NEW_LOCATION
    elif share is not None and share < RARE_LOCATION_SHARE:
        # Scale: rarer => closer to the max rare contribution.
        rarity = 1.0 - (share / RARE_LOCATION_SHARE)
        score_components["rare_location"] = round(SCORE_RARE_LOCATION_MAX * rarity, 4)
        signals.append("RARE_LOCATION")

    # ---- Signal 2: foreign / high-risk jurisdiction ---------------------
    triggered_rule = None
    cur_country = loc["country"]
    if cur_country and cur_country != home_country:
        if cur_country in FATF_HIGH_RISK_COUNTRIES:
            score_components["fatf_high_risk"] = SCORE_FATF_HIGH_RISK
            signals.append("FATF_HIGH_RISK_JURISDICTION")
            triggered_rule = "FATF_HIGH_RISK_JURISDICTION"
        else:
            score_components["foreign_country"] = SCORE_FOREIGN_COUNTRY
            signals.append("FOREIGN_COUNTRY")
            triggered_rule = triggered_rule or "FEMA_CROSS_BORDER"

    # ---- Signal 3: impossible travel ------------------------------------
    last = account_history.get("last_location") or {}
    impossible_speed = None
    distance_km = None
    hours_elapsed = None
    if (
        loc["lat"] is not None and loc["lon"] is not None
        and last.get("lat") is not None and last.get("lon") is not None
        and last.get("timestamp") and transaction.get("timestamp")
    ):
        try:
            t_now = datetime.fromisoformat(transaction["timestamp"])
            t_prev = datetime.fromisoformat(last["timestamp"])
            hours_elapsed = (t_now - t_prev).total_seconds() / 3600.0
            distance_km = _haversine_km(
                last["lat"], last["lon"], loc["lat"], loc["lon"]
            )
            if hours_elapsed > 0:
                impossible_speed = distance_km / hours_elapsed
                if impossible_speed > MAX_PLAUSIBLE_SPEED_KMH:
                    score_components["impossible_travel"] = SCORE_IMPOSSIBLE_TRAVEL
                    signals.append("IMPOSSIBLE_TRAVEL")
                    triggered_rule = "GEO_IMPOSSIBLE_TRAVEL"
            elif distance_km > 0:
                # Same/earlier timestamp but a different place => implausible.
                score_components["impossible_travel"] = SCORE_IMPOSSIBLE_TRAVEL
                signals.append("IMPOSSIBLE_TRAVEL")
                triggered_rule = "GEO_IMPOSSIBLE_TRAVEL"
        except (ValueError, TypeError):
            pass  # bad timestamps/coords — skip this signal silently

    # ---- Combine: noisy-OR so independent signals reinforce, capped 1.0 -
    # P(anomaly) = 1 - Π(1 - s_i). Strong single signals still dominate.
    product = 1.0
    for s in score_components.values():
        product *= (1.0 - s)
    score = round(min(1.0 - product, 1.0), 4)

    fired = score >= FIRED_THRESHOLD

    return {
        "check": "T4_GEO_ANOMALY",
        "fired": fired,
        "score": score,
        "triggered_rule": triggered_rule if fired else None,
        "evidence": {
            "current_location":      loc["city"] or loc["key"],
            "current_country":       cur_country,
            "home_country":          home_country,
            "location_seen_count":   location_count,
            "history_total_seen":    total_seen,
            "location_share":        round(share, 4) if share is not None else None,
            "signals":               signals,
            "score_components":      score_components,
            "distance_from_last_km": round(distance_km, 1) if distance_km is not None else None,
            "hours_since_last":      round(hours_elapsed, 2) if hours_elapsed is not None else None,
            "implied_speed_kmh":     round(impossible_speed, 1) if impossible_speed is not None else None,
            "fired_threshold":       FIRED_THRESHOLD,
        },
    }
