# DEMO RUNBOOK — Compliance Pipeline

**The whole demo is two transactions:**

1. A fresh transaction with an **empty cache** → runs the **full pipeline** (L1 → L2 detectors + phi4).
2. The **same type** of transaction with that type **already in the cache** → L1 recognises it and **short-circuits straight to the audit layer (L6)**, skipping L2.

```
   you (CLI)              Azure                    your desktop
  demo.py publish-file ─► tx-events queue ─► demo.py run ─► L1 checks the cache:
                                                            ├─ not cached → FULL PIPELINE (L2 + phi4)
                                                            └─ cached     → SHORT-CIRCUIT to L6 audit
```

Run everything from the repo root:

    cd D:\Bank-Project\Compliance-pipeline

---

## 0. Pre-flight (once, before the demo)

```powershell
ollama serve                                              # Terminal A — leave running (phi4)
az account show -o table                                  # Terminal B — confirm Azure login
./infra/setup-env.ps1 -ResourceGroup rg-compliance-demo   # writes .env (storage connection)
```
> If `ollama serve` says *"Only one usage of each socket address"*, it's already running — fine.

---

## (Optional) Watch the queue in the Azure Portal

You can show the message physically arriving in the cloud queue:

1. Portal → your storage account (`comp st…`) → **Data storage ▸ Queues** → **`tx-events`**.
2. The view is a **snapshot — hit Refresh manually** each time (it doesn't auto-stream).

Because `demo.py run` **deletes** each message after processing it, split the steps to make it visible:
- after `publish-file` → **Refresh** → the message is **in the queue**.
- after `run` → **Refresh** → the message is **gone** (consumed).

This applies to both scenarios below — the inline `← Refresh portal` markers show where.

---

## SCENARIO 1 — transaction WITHOUT cache → full pipeline

```powershell
# 1. empty the queue AND the cache so nothing is remembered
python demo.py clear

# 2. give one transaction to the Azure queue
python demo.py publish-file demo_tx/cache_first.json    # ← Refresh portal: message appears

# 3. pull it back and process it
python demo.py run --count 1                            # ← Refresh portal: message gone
```

**What you'll see / narrate:**
- L1 log: `FULL PIPELINE: TXCACHE-001 (no memory match)`
- The verdict prints **`route   l2`** → it went through the full L2 detectors + phi4.
- This transaction is now **stored in the cache** (`data/case_memory.json`).

---

## SCENARIO 2 — same type WITH cache → short-circuit to audit

Do **not** clear the cache this time — Scenario 1 just populated it.

```powershell
# 1. give a NEW transaction of the SAME type to the queue
python demo.py publish-file demo_tx/cache_repeat.json   # ← Refresh portal: message appears

# 2. pull it back and process it
python demo.py run --count 1                            # ← Refresh portal: message gone
```

**What you'll see / narrate:**
- L1 log: `SHORT-CIRCUIT: TXCACHE-002 matched TXCACHE-001 (similarity=1.000, hash_unchanged=True)`
- The verdict prints **`route   l6_short_circuit`** → L2 was **skipped**; it went
  straight to the **audit layer (L6)** with `final_status = AUDIT_ONLY`.

> Why it matches: L1 fingerprints each transaction by sender + beneficiary +
> amount band + channel + purpose. `cache_first` and `cache_repeat` share all of
> these (only the `tx_id` differs), so the similarity is 1.00 — above the 0.80
> threshold — and the regulation hash is unchanged, so it short-circuits.

---

## The two together (copy-paste run)

```powershell
cd D:\Bank-Project\Compliance-pipeline

# Scenario 1 — no cache → full pipeline
python demo.py clear
python demo.py publish-file demo_tx/cache_first.json
python demo.py run --count 1

# Scenario 2 — cached → short-circuit to audit
python demo.py publish-file demo_tx/cache_repeat.json
python demo.py run --count 1
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Scenario 2 shows `route=l2` (didn't short-circuit) | The cache was empty — run Scenario 1 first, and don't `clear` between them |
| Scenario 1 shows `route=l6_short_circuit` (short-circuited too early) | The cache wasn't cleared — run `python demo.py clear` first |
| `predictor=phi4_fallback` in the verdict | Ollama isn't reachable — start `ollama serve` (Terminal A) |
| `CERTIFICATE_VERIFY_FAILED` on an Azure call (Avast) | Open `.env`, set `AZURE_SSL_VERIFY=0`, save, re-run |
| `Queue empty — nothing to process` | You ran `run` before `publish-file` — publish first |

---

## ADD-ON — extra transactions to test before the demo (not part of the main demo)

These exercise individual detectors. Same flow as the demo: `clear` → `publish-file`
→ `run --count 1`. Run `python demo.py clear` first so a stale cache doesn't
short-circuit them.

```powershell
python demo.py clear

# 🚩 C2 — receiver PAN matches a UNSC watchlist entity (Omar Al-Zarqawi, WL0003)
python demo.py publish-file demo_tx/flag_c2_watchlist.json
python demo.py run --count 1

# 🚩 C6 — 3 AM SWIFT from Tehran (IR = FATF high-risk), new device
python demo.py publish-file demo_tx/flag_c6_iran.json
python demo.py run --count 1

# ✅ clean — normal domestic payment (home city, usual device, average amount)
python demo.py publish-file demo_tx/clean_domestic.json
python demo.py run --count 1

# ✅ clean — small cross-border tuition, well under the LRS ceiling (cross-border ≠ flag)
python demo.py publish-file demo_tx/clean_crossborder_legit.json
python demo.py run --count 1
```

| File | Expect | Detector |
|------|--------|----------|
| `flag_c2_watchlist.json` | 🚩 | C2 — watchlist hit (`route=l2`) |
| `flag_c6_iran.json` | 🚩 | C6 — FATF jurisdiction (`route=l2`) |
| `clean_domestic.json` | ✅ clear | nothing fires |
| `clean_crossborder_legit.json` | ✅ clear | nothing fires |

> ⚠️ **C5 (`flag_c5_lrs.json`) does NOT flag through Azure** — by design, C5 sums a
> PAN's cross-border history from the dataset, and a brand-new leg isn't in it on
> the live path. To test C5, run it **locally** instead (this path registers the
> new leg first):
> ```powershell
> python -m L2_transaction_monitor.run_new --json demo_tx/flag_c5_lrs.json
> ```
