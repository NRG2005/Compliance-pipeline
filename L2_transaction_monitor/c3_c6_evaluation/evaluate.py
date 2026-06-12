"""
evaluate.py
-----------
F1 evaluation harness for C3 (Graph/Network Flow) and C6 (Geo-Anomaly).

For each detector it runs BOTH predictors on the SAME labelled synthetic data:
  * deterministic  — the rules-only baseline
  * phi4 (SLM)     — the prompt-based classifier (or its transparent reference
                     reasoner when Ollama isn't running / USE_MOCK is True)

and reports precision / recall / F1 / accuracy plus a per-scenario error
breakdown. Artifacts are written to c3_c6_evaluation/results/:
  * results.json          — machine-readable metrics
  * REPORT.md             — human-readable summary

All paths are relative to this file's location
(<repo>/L2_transaction_monitor/c3_c6_evaluation/), so it runs from anywhere.

Usage (from repo root):
  python L2_transaction_monitor/c3_c6_synthetic_data/generate_c3.py   # regen data
  python L2_transaction_monitor/c3_c6_synthetic_data/generate_c6.py
  python L2_transaction_monitor/c3_c6_evaluation/evaluate.py          # reference reasoner
  python L2_transaction_monitor/c3_c6_evaluation/evaluate.py --real   # real phi4 over Ollama
  python L2_transaction_monitor/c3_c6_evaluation/evaluate.py --real --sample 5

The pass bar: the SLM must reach F1 >= 0.90 AND beat the deterministic baseline.
"""

import argparse
import datetime
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

# This file lives at <repo>/L2_transaction_monitor/c3_c6_evaluation/evaluate.py
HERE = Path(__file__).resolve().parent          # .../c3_c6_evaluation
ROOT = HERE.parent.parent                        # repo root (for package imports)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))                    # so `import metrics` resolves

from metrics import scores
from L2_transaction_monitor.c3_graph_network_flow import run_c3
from L2_transaction_monitor.c3_graph_network_flow import slm_classifier as c3_slm
from L2_transaction_monitor.c6_geo_anomaly import run_c6
from L2_transaction_monitor.c6_geo_anomaly import slm_classifier as c6_slm

DATA = HERE.parent / "c3_c6_synthetic_data"      # sibling folder under L2
RESULTS = HERE / "results"
F1_BAR = 0.90


def _load(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run the generators in c3_c6_synthetic_data first.")
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _stratified_sample(rows: list[dict], per_scenario: int) -> list[dict]:
    """Take up to `per_scenario` rows from each scenario (keeps class balance)."""
    by = defaultdict(list)
    for r in rows:
        by[r["scenario"]].append(r)
    out = []
    rng = random.Random(20260610)
    for sc, group in by.items():
        rng.shuffle(group)
        out.extend(group[:per_scenario])
    rng.shuffle(out)
    return out


def _eval_c6(rows):
    y_true = [r["label"] for r in rows]
    det = [run_c6(r["transaction"], r["account_history"], mode="deterministic")["label"] for r in rows]
    slm = [run_c6(r["transaction"], r["account_history"], mode="slm")["label"] for r in rows]
    return y_true, det, slm


def _eval_c3(rows):
    y_true = [r["label"] for r in rows]
    det = [run_c3(r["case"], mode="deterministic")["label"] for r in rows]
    slm = [run_c3(r["case"], mode="slm")["label"] for r in rows]
    return y_true, det, slm


def _scenario_breakdown(rows, y_true, det, slm):
    by = defaultdict(lambda: {"n": 0, "det_err": 0, "slm_err": 0})
    for r, t, d, s in zip(rows, y_true, det, slm):
        b = by[r["scenario"]]
        b["n"] += 1
        b["det_err"] += int(d != t)
        b["slm_err"] += int(s != t)
    return dict(by)


def _print_block(name, y_true, det, slm, breakdown):
    ds, ss = scores(y_true, det), scores(y_true, slm)
    print(f"\n=== {name} ===")
    print(f"  samples: {ds['n']}  (fraud={sum(y_true)}, legit={ds['n'] - sum(y_true)})")
    print(f"  {'predictor':<16}{'precision':>11}{'recall':>9}{'f1':>9}{'acc':>8}  (TP/FP/FN/TN)")
    print(f"  {'deterministic':<16}{ds['precision']:>11}{ds['recall']:>9}{ds['f1']:>9}{ds['accuracy']:>8}"
          f"  ({ds['tp']}/{ds['fp']}/{ds['fn']}/{ds['tn']})")
    print(f"  {'phi4 (SLM)':<16}{ss['precision']:>11}{ss['recall']:>9}{ss['f1']:>9}{ss['accuracy']:>8}"
          f"  ({ss['tp']}/{ss['fp']}/{ss['fn']}/{ss['tn']})")
    delta = round(ss["f1"] - ds["f1"], 4)
    bar = "PASS" if (ss["f1"] >= F1_BAR and ss["f1"] > ds["f1"]) else "FAIL"
    print(f"  SLM F1 {ss['f1']:.4f} vs bar {F1_BAR:.2f}  |  +{delta} over deterministic  ->  [{bar}]")
    print(f"  per-scenario errors (det -> slm):")
    for sc, b in sorted(breakdown.items(), key=lambda kv: -kv[1]["det_err"]):
        print(f"    {sc:<32} n={b['n']:>3}  det_err={b['det_err']:>3}  slm_err={b['slm_err']:>3}")
    return {"deterministic": ds, "slm": ss, "scenarios": breakdown, "verdict": bar}


def _write_report(out: dict):
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = ["# C3 / C6 — F1 Evaluation Report", ""]
    lines.append(f"- SLM backend: **{out['slm_backend']}**")
    if out.get("slm_model"):
        lines.append(f"- SLM model: **{out['slm_model']}**")
    if out.get("scope"):
        lines.append(f"- Scope: {out['scope']}")
    if out.get("run_date"):
        lines.append(f"- Run date: {out['run_date']}")
    lines.append(f"- Pass bar: SLM **F1 ≥ {F1_BAR}** AND SLM F1 > deterministic F1")
    lines.append("")
    for key, title in (("C6_GEO_ANOMALY", "C6 — Geo-Anomaly"), ("C3_GRAPH_FLOW", "C3 — Graph / Network Flow")):
        b = out[key]
        d, s = b["deterministic"], b["slm"]
        lines += [
            f"## {title}", "",
            "| predictor | precision | recall | F1 | accuracy | TP/FP/FN/TN |",
            "|---|---|---|---|---|---|",
            f"| deterministic | {d['precision']} | {d['recall']} | {d['f1']} | {d['accuracy']} | {d['tp']}/{d['fp']}/{d['fn']}/{d['tn']} |",
            f"| **phi4 (SLM)** | {s['precision']} | {s['recall']} | **{s['f1']}** | {s['accuracy']} | {s['tp']}/{s['fp']}/{s['fn']}/{s['tn']} |",
            "", f"**Verdict: {b['verdict']}** — SLM F1 {s['f1']} (Δ +{round(s['f1'] - d['f1'], 4)} vs deterministic).", "",
            "Per-scenario errors:", "",
            "| scenario | n | deterministic errors | SLM errors |", "|---|---|---|---|",
        ]
        for sc, sb in sorted(b["scenarios"].items(), key=lambda kv: -kv[1]["det_err"]):
            lines.append(f"| {sc} | {sb['n']} | {sb['det_err']} | {sb['slm_err']} |")
        lines.append("")
    (RESULTS / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nArtifacts written: {RESULTS / 'results.json'}  and  {RESULTS / 'REPORT.md'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", action="store_true", help="use real phi4 over Ollama (USE_MOCK=False)")
    ap.add_argument("--sample", type=int, default=0,
                    help="cap rows per scenario (stratified) — useful for slow real-phi4 runs; 0 = full dataset")
    args = ap.parse_args()

    # --real -> real phi4 over Ollama; default -> fast reference reasoner.
    # Authoritative either way, regardless of the module-level USE_MOCK default.
    c3_slm.USE_MOCK = not args.real
    c6_slm.USE_MOCK = not args.real
    backend = "real phi4 (Ollama)" if args.real else "reference reasoner (mock)"
    print(f"SLM backend: {backend}")

    c6_rows = _load(DATA / "c6_dataset.jsonl")
    c3_rows = _load(DATA / "c3_dataset.jsonl")
    if args.sample > 0:
        c6_rows = _stratified_sample(c6_rows, args.sample)
        c3_rows = _stratified_sample(c3_rows, args.sample)
        print(f"Stratified sample: {args.sample}/scenario -> C6={len(c6_rows)} rows, C3={len(c3_rows)} rows")

    c6_t, c6_d, c6_s = _eval_c6(c6_rows)
    c3_t, c3_d, c3_s = _eval_c3(c3_rows)

    scope = f"stratified sample ({args.sample}/scenario)" if args.sample > 0 else "full dataset"
    out = {
        "slm_backend": backend,
        "slm_model": (c6_slm.OLLAMA_MODEL if args.real else "reference reasoner (rule-based)"),
        "scope": f"{scope} — C6={len(c6_rows)} rows, C3={len(c3_rows)} rows",
        "run_date": datetime.date.today().isoformat(),
    }
    out["C6_GEO_ANOMALY"] = _print_block(
        "C6 — Geo-Anomaly", c6_t, c6_d, c6_s, _scenario_breakdown(c6_rows, c6_t, c6_d, c6_s))
    out["C3_GRAPH_FLOW"] = _print_block(
        "C3 — Graph / Network Flow", c3_t, c3_d, c3_s, _scenario_breakdown(c3_rows, c3_t, c3_d, c3_s))

    _write_report(out)

    ok = all(out[k]["verdict"] == "PASS" for k in ("C3_GRAPH_FLOW", "C6_GEO_ANOMALY"))
    print(f"\nOVERALL: {'PASS — both detectors meet F1 >= 0.90 and beat deterministic' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
