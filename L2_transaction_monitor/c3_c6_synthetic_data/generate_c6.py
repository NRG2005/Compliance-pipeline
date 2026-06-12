"""
generate_c6.py  —  synthetic labelled dataset for C6 (Geo-Anomaly)
------------------------------------------------------------------
Emits c6_dataset.jsonl (written next to this file), one JSON object per line:

    {"transaction": {...}, "account_history": {...}, "label": 0|1, "scenario": "..."}

label 1 = genuinely fraudulent (account takeover / laundering geo signal)
label 0 = legitimate, even when superficially anomalous.

The mix is deliberate: ~20% are HARD contextual cases (NRE foreign transfers,
frequent-traveller new cities, sub-threshold device probes, mimicked-profile
takeovers). A rules-only detector both over- and under-fires on these; a
context-aware classifier resolves most of them. That gap is what the F1
evaluation demonstrates.
Run:  python L2_transaction_monitor/c3_c6_synthetic_data/generate_c6.py
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(20260610)

OUT = Path(__file__).parent / "c6_dataset.jsonl"
BASE = datetime(2026, 6, 1, 12, 0, 0)

CITIES = {
    "Mumbai": (19.0760, 72.8777, "IN"), "Pune": (18.5204, 73.8567, "IN"),
    "Delhi": (28.6139, 77.2090, "IN"), "Bangalore": (12.9716, 77.5946, "IN"),
    "Chennai": (13.0827, 80.2707, "IN"), "Kolkata": (22.5726, 88.3639, "IN"),
    "Jaipur": (26.9124, 75.7873, "IN"), "NewYork": (40.7128, -74.0060, "US"),
    "Dubai": (25.2048, 55.2708, "AE"), "London": (51.5074, -0.1278, "GB"),
    "Yangon": (16.8409, 96.1735, "MM"), "Singapore": (1.3521, 103.8198, "SG"),
}


def _loc(city):
    lat, lon, country = CITIES[city]
    return {"city": city, "country": country, "lat": lat, "lon": lon}


def _history(home_cities, profile, acct_type, devices, balance, avg, last_city, last_offset_h):
    lat, lon, _ = CITIES[last_city]
    return {
        "home_country": "IN",
        "known_locations": {c: random.randint(20, 120) for c in home_cities},
        "last_location": {
            "city": last_city, "lat": lat, "lon": lon,
            "timestamp": (BASE - timedelta(hours=last_offset_h)).isoformat(),
        },
        "typical_devices": devices,
        "balance_inr": balance,
        "avg_tx_amount": avg,
        "account_type": acct_type,
        "travel_profile": profile,
    }


def _tx(i, city, amount, device, hour=14, purpose="P0099", channel="UPI"):
    ts = BASE.replace(hour=hour) + timedelta(minutes=i % 60)
    return {
        "tx_id": f"C6TX{i:05d}",
        "sender_account_id": f"ACC{i % 500:04d}",
        "timestamp": ts.isoformat(),
        "amount_inr": amount,
        "channel": channel,
        "purpose_code": purpose,
        "device_id": device,
        "location": _loc(city),
    }


# --- scenario builders: (transaction, account_history, label, scenario) -----

def s_clean(i):
    h = _history(["Mumbai", "Pune"], "DOMESTIC_STATIC", "SAVINGS", ["DEV-A"], 200000, 8000, "Mumbai", 6)
    return _tx(i, "Mumbai", random.randint(2000, 15000), "DEV-A"), h, 0, "clean_routine"


def s_impossible(i):
    h = _history(["Mumbai"], "DOMESTIC_STATIC", "SAVINGS", ["DEV-A"], 300000, 9000, "Mumbai", 1)
    return _tx(i, "NewYork", random.randint(30000, 90000), "DEV-X"), h, 1, "impossible_travel_fraud"


def s_fatf(i):
    h = _history(["Delhi"], "DOMESTIC_STATIC", "SAVINGS", ["DEV-A"], 250000, 9000, "Delhi", 30)
    return _tx(i, "Yangon", random.randint(20000, 80000), "DEV-A"), h, 1, "fatf_jurisdiction_fraud"


def s_takeover_drain(i):
    h = _history(["Mumbai", "Pune"], "DOMESTIC_STATIC", "SAVINGS", ["DEV-A"], 100000, 8000, "Mumbai", 10)
    # known location, NEW device, drains ~95% of balance
    return _tx(i, "Mumbai", 95000, "DEV-EVIL", hour=15), h, 1, "takeover_newdevice_drain"


def s_newloc_newdev(i):
    h = _history(["Chennai"], "DOMESTIC_STATIC", "SAVINGS", ["DEV-A"], 200000, 9000, "Chennai", 8)
    return _tx(i, "Kolkata", random.randint(15000, 40000), "DEV-NEW"), h, 1, "newloc_newdevice_fraud"


def s_subtle_probe(i):
    # KNOWN location + NEW device + odd hour + small probe amount.
    # Deterministic: new_device(0.35)+odd_hour(0.15) = 0.45 < 0.50 -> MISS (FN).
    h = _history(["Delhi"], "DOMESTIC_STATIC", "SAVINGS", ["DEV-A"], 150000, 9000, "Delhi", 9)
    return _tx(i, "Delhi", random.randint(500, 3000), "DEV-PROBE", hour=3), h, 1, "subtle_device_probe"


def s_mimic_takeover(i):
    # KNOWN device + KNOWN location + drain at a normal hour. Feature-blind to
    # both detectors -> residual FN (kept to keep the SLM honest, not perfect).
    h = _history(["Mumbai"], "DOMESTIC_STATIC", "SAVINGS", ["DEV-A"], 120000, 8000, "Mumbai", 12)
    return _tx(i, "Mumbai", 110000, "DEV-A", hour=16), h, 1, "mimicked_profile_takeover"


def s_nre_foreign(i):
    # NRE account, first transfer from abroad -> det fires (FP), context = NORMAL.
    h = _history(["Mumbai"], "INTERNATIONAL_FREQUENT", "NRE", ["DEV-A"], 500000, 40000, "Mumbai", 20)
    return _tx(i, "Dubai", random.randint(40000, 120000), "DEV-A", purpose="P0014"), h, 0, "nre_foreign_legit"


def s_traveller_newcity(i):
    h = _history(["Bangalore"], "DOMESTIC_TRAVELLER", "SAVINGS", ["DEV-A"], 200000, 12000, "Bangalore", 10)
    return _tx(i, "Jaipur", random.randint(3000, 20000), "DEV-A"), h, 0, "frequent_traveller_newcity"


def s_static_relocation(i):
    h = _history(["Chennai"], "DOMESTIC_STATIC", "SAVINGS", ["DEV-A"], 180000, 9000, "Chennai", 14)
    return _tx(i, "Pune", random.randint(2000, 15000), "DEV-A"), h, 0, "static_relocation"


def s_big_purchase(i):
    # Drain from KNOWN device/location at a normal hour -> legitimate purchase.
    h = _history(["Mumbai"], "DOMESTIC_STATIC", "SAVINGS", ["DEV-A"], 130000, 8000, "Mumbai", 11)
    return _tx(i, "Mumbai", 115000, "DEV-A", hour=17, purpose="P0107"), h, 0, "big_purchase_legit"


def s_oddhour_known(i):
    # Night-shift user: odd hour but own device/location, normal amount.
    h = _history(["Delhi"], "DOMESTIC_STATIC", "SAVINGS", ["DEV-A"], 150000, 7000, "Delhi", 7)
    return _tx(i, "Delhi", random.randint(1000, 6000), "DEV-A", hour=3), h, 0, "oddhour_known_user"


def s_vacation_foreign(i):
    # Domestic-static holder genuinely abroad on holiday -> BOTH misclassify (FP).
    h = _history(["Kolkata"], "DOMESTIC_STATIC", "SAVINGS", ["DEV-A"], 220000, 10000, "Kolkata", 18)
    return _tx(i, "Singapore", random.randint(8000, 30000), "DEV-A", purpose="P0008"), h, 0, "vacation_foreign_legit"


# (builder, count)
PLAN = [
    (s_clean, 50), (s_impossible, 25), (s_fatf, 15), (s_takeover_drain, 25),
    (s_newloc_newdev, 25), (s_subtle_probe, 12), (s_mimic_takeover, 8),
    (s_nre_foreign, 12), (s_traveller_newcity, 12), (s_static_relocation, 12),
    (s_big_purchase, 25), (s_oddhour_known, 20), (s_vacation_foreign, 10),
]


def main():
    rows = []
    i = 0
    for builder, count in PLAN:
        for _ in range(count):
            tx, hist, label, scenario = builder(i)
            rows.append({"transaction": tx, "account_history": hist, "label": label, "scenario": scenario})
            i += 1
    random.shuffle(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    pos = sum(r["label"] for r in rows)
    print(f"Wrote {len(rows)} C6 records to {OUT}  ({pos} fraud / {len(rows) - pos} legit)")


if __name__ == "__main__":
    main()
