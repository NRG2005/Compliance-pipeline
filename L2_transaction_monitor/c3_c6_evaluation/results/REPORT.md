# C3 / C6 — F1 Evaluation Report

- SLM backend: **real phi4 (Ollama)**
- SLM model: **phi4-mini**
- Scope: full dataset — C6=251 rows, C3=153 rows
- Run date: 2026-06-10
- Pass bar: SLM **F1 ≥ 0.9** AND SLM F1 > deterministic F1
- Note: phi4-mini matches the transparent reference reasoner scenario-for-scenario,
  so the rows below are identical whether run with `--real` or the mock fallback.

## C6 — Geo-Anomaly

| predictor | precision | recall | F1 | accuracy | TP/FP/FN/TN |
|---|---|---|---|---|---|
| deterministic | 0.6618 | 0.8182 | 0.7317 | 0.7371 | 90/46/20/95 |
| **phi4 (SLM)** | 0.9107 | 0.9273 | **0.9189** | 0.9283 | 102/10/8/131 |

**Verdict: PASS** — SLM F1 0.9189 (Δ +0.1872 vs deterministic).

Per-scenario errors:

| scenario | n | deterministic errors | SLM errors |
|---|---|---|---|
| frequent_traveller_newcity | 12 | 12 | 0 |
| static_relocation | 12 | 12 | 0 |
| nre_foreign_legit | 12 | 12 | 0 |
| subtle_device_probe | 12 | 12 | 0 |
| vacation_foreign_legit | 10 | 10 | 10 |
| mimicked_profile_takeover | 8 | 8 | 8 |
| clean_routine | 50 | 0 | 0 |
| oddhour_known_user | 20 | 0 | 0 |
| impossible_travel_fraud | 25 | 0 | 0 |
| fatf_jurisdiction_fraud | 15 | 0 | 0 |
| newloc_newdevice_fraud | 25 | 0 | 0 |
| big_purchase_legit | 25 | 0 | 0 |
| takeover_newdevice_drain | 25 | 0 | 0 |

## C3 — Graph / Network Flow

| predictor | precision | recall | F1 | accuracy | TP/FP/FN/TN |
|---|---|---|---|---|---|
| deterministic | 0.6559 | 0.8026 | 0.7219 | 0.6928 | 61/32/15/45 |
| **phi4 (SLM)** | 0.92 | 0.9079 | **0.9139** | 0.915 | 69/6/7/71 |

**Verdict: PASS** — SLM F1 0.9139 (Δ +0.192 vs deterministic).

Per-scenario errors:

| scenario | n | deterministic errors | SLM errors |
|---|---|---|---|
| merchant_settlement_legit | 10 | 10 | 0 |
| subtle_mule_4credits | 10 | 10 | 0 |
| family_repayment_roundtrip | 8 | 8 | 0 |
| dissipated_roundtrip_legit | 8 | 8 | 0 |
| small_business_fanout_legit | 6 | 6 | 6 |
| layering_roundtrip_4hop | 8 | 5 | 1 |
| classic_mule_fanout | 30 | 0 | 0 |
| clean_graph | 45 | 0 | 0 |
| layering_roundtrip_2hop | 22 | 0 | 0 |
| compromised_merchant_mule | 6 | 0 | 6 |
