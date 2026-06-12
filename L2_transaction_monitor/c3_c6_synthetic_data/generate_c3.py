"""
generate_c3.py  —  synthetic labelled dataset for C3 (Graph / Network Flow)
---------------------------------------------------------------------------
Emits c3_dataset.jsonl (written next to this file), one JSON object per line:

    {"case": {...}, "label": 0|1, "scenario": "..."}

Each `case` is a 72h transaction sub-graph centred on a trigger account (the
shape graph_builder.TxGraph.from_case consumes).

label 1 = genuine mule fan-in/out or PMLA s.3 layering round-trip
label 0 = legitimate aggregation (registered merchant / payroll) or family transfer

HARD cases included on purpose: sub-threshold (4-credit) mules, 4-hop layering
loops (one hop past the deterministic fire depth), merchant settlements that look
like fan-out, family round-trips sharing only a surname, and dissipated loops.
A rules-only detector both over- and under-fires on these; the context-aware
classifier resolves most.
Run:  python L2_transaction_monitor/c3_c6_synthetic_data/generate_c3.py
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(20260610)

OUT = Path(__file__).parent / "c3_dataset.jsonl"
BASE = datetime(2026, 6, 1, 9, 0, 0)

SURNAMES = ["Sharma", "Patel", "Reddy", "Khan", "Nair", "Gupta", "Iyer", "Bose"]
IFSC = ["HDFC", "ICIC", "SBIN", "AXIS", "KKBK", "PUNB", "UTIB", "YESB"]


def _acct(aid, ifsc, device, holder, age, merchant=False, atype="SAVINGS"):
    return {
        "account_id": aid, "ifsc": ifsc + "0" + str(random.randint(100, 999)),
        "device_id": device, "holder_name": holder, "account_age_days": age,
        "is_registered_merchant": merchant, "account_type": atype, "kyc_level": "FULL",
    }


def _edge(src, dst, amount, minute, src_vpa=None, dst_vpa=None):
    return {
        "src": src, "dst": dst, "amount_inr": round(amount, 2),
        "timestamp": (BASE + timedelta(minutes=minute)).isoformat(),
        "src_vpa": src_vpa or f"{src}@upi", "dst_vpa": dst_vpa or f"{dst}@upi",
    }


def _case(cid, trigger, edges, accounts, label, scenario):
    return {
        "case": {
            "case_id": cid, "trigger_account": trigger, "window_hours": 72,
            "edges": edges, "accounts": {a["account_id"]: a for a in accounts},
        },
        "label": label, "scenario": scenario,
    }


def _fan_case(cid, scenario, label, n_inbound, merchant, age, atype="SAVINGS"):
    """Fan-in of n_inbound tiny distinct credits, then a single >80% sweep out."""
    trig = f"MULE{cid}"
    edges, accounts = [], [_acct(trig, random.choice(IFSC), f"DEV-{trig}",
                                 random.choice(SURNAMES), age, merchant, atype)]
    cumulative = 0.0
    for k in range(n_inbound):
        amt = random.randint(2500, 4800)
        cumulative += amt
        payer = f"PAYER{cid}_{k}"
        accounts.append(_acct(payer, random.choice(IFSC), f"DEV-{payer}", random.choice(SURNAMES), 800))
        edges.append(_edge(payer, trig, amt, minute=k * 10, src_vpa=f"vpa{cid}_{k}@bank"))
    # single outbound sweeping ~90% of received, shortly after the burst
    sink = f"SINK{cid}"
    accounts.append(_acct(sink, random.choice(IFSC), f"DEV-{sink}", random.choice(SURNAMES), 1200))
    edges.append(_edge(trig, sink, cumulative * 0.9, minute=n_inbound * 10 + 5))
    return _case(cid, trig, edges, accounts, label, scenario)


def _roundtrip_case(cid, scenario, label, hops, shared, preservation):
    """A→...→back-to-a-same-identity account over `hops`, preserving `preservation`."""
    trig = f"RT{cid}"
    base_amt = random.randint(150000, 400000)
    chain = [trig] + [f"INT{cid}_{h}" for h in range(1, hops)]
    return_acct = f"RET{cid}"

    # identity of the returning account: matches trigger on `shared`
    trig_ifsc, trig_dev, trig_holder = random.choice(IFSC), f"DEV-{trig}", random.choice(SURNAMES)
    accounts = [_acct(trig, trig_ifsc, trig_dev, trig_holder, 400)]
    for h in range(1, hops):
        accounts.append(_acct(chain[h], random.choice(IFSC), f"DEV-INT{cid}_{h}", random.choice(SURNAMES), 600))

    if shared == "device_id":
        ret = _acct(return_acct, random.choice(IFSC), trig_dev, random.choice(SURNAMES), 500)
    elif shared == "ifsc_prefix":
        ret = _acct(return_acct, trig_ifsc[:4], f"DEV-{return_acct}", random.choice(SURNAMES), 500)
    else:  # holder_suffix
        ret = _acct(return_acct, random.choice(IFSC), f"DEV-{return_acct}", trig_holder, 500)
    accounts.append(ret)

    edges = []
    full_chain = chain + [return_acct]
    amt = base_amt
    final_amt = base_amt * preservation
    step_ratio = preservation ** (1.0 / hops)
    for h in range(hops):
        nxt = amt * step_ratio
        edges.append(_edge(full_chain[h], full_chain[h + 1], nxt, minute=h * 30))
        amt = nxt
    return _case(cid, trig, edges, accounts, label, scenario)


def _clean_case(cid):
    """A small, ordinary graph: a few unrelated payments, no sweep, no loop."""
    trig = f"OK{cid}"
    accounts = [_acct(trig, random.choice(IFSC), f"DEV-{trig}", random.choice(SURNAMES), 900)]
    edges = []
    for k in range(random.randint(1, 3)):
        peer = f"PEER{cid}_{k}"
        accounts.append(_acct(peer, random.choice(IFSC), f"DEV-{peer}", random.choice(SURNAMES), 700))
        if random.random() < 0.5:
            edges.append(_edge(peer, trig, random.randint(8000, 60000), minute=k * 40))
        else:
            edges.append(_edge(trig, peer, random.randint(8000, 60000), minute=k * 40))
    return _case(cid, trig, edges, accounts, 0, "clean_graph")


# (builder lambda, count)
PLAN = [
    # --- fraud (label 1) ---
    (lambda i: _fan_case(i, "classic_mule_fanout", 1, n_inbound=6, merchant=False, age=60), 30),
    (lambda i: _fan_case(i, "subtle_mule_4credits", 1, n_inbound=4, merchant=False, age=30), 10),
    (lambda i: _roundtrip_case(i, "layering_roundtrip_2hop", 1, hops=2, shared="device_id", preservation=0.92), 22),
    (lambda i: _roundtrip_case(i, "layering_roundtrip_4hop", 1, hops=4, shared="ifsc_prefix", preservation=0.90), 8),
    (lambda i: _fan_case(i, "compromised_merchant_mule", 1, n_inbound=6, merchant=True, age=900, atype="CURRENT"), 6),
    # --- legitimate (label 0) ---
    (lambda i: _clean_case(i), 45),
    (lambda i: _fan_case(i, "merchant_settlement_legit", 0, n_inbound=7, merchant=True, age=1500, atype="MERCHANT"), 10),
    (lambda i: _roundtrip_case(i, "family_repayment_roundtrip", 0, hops=2, shared="holder_suffix", preservation=0.72), 8),
    (lambda i: _roundtrip_case(i, "dissipated_roundtrip_legit", 0, hops=2, shared="device_id", preservation=0.55), 8),
    (lambda i: _fan_case(i, "small_business_fanout_legit", 0, n_inbound=6, merchant=False, age=1200, atype="CURRENT"), 6),
]


def main():
    rows, i = [], 0
    for builder, count in PLAN:
        for _ in range(count):
            rows.append(builder(i))
            i += 1
    random.shuffle(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    pos = sum(r["label"] for r in rows)
    print(f"Wrote {len(rows)} C3 records to {OUT}  ({pos} fraud / {len(rows) - pos} legit)")


if __name__ == "__main__":
    main()
