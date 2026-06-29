"""
Batch runner for local L3 testing.

Usage:
python3 L3_regulation_interpreter/run_l3_cases.py \
  --transactions /path/to/L3_TestTransactions.json \
  --corpus L3_regulation_interpreter/regulation_corpus.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from .hybrid_retrieval import search_regulations
    from .legal_reasoning import generate_legal_analysis
except ImportError:
    from L3_regulation_interpreter.hybrid_retrieval import search_regulations
    from L3_regulation_interpreter.legal_reasoning import generate_legal_analysis


def run_cases(transactions_path: str, corpus_path: str) -> Dict[str, Any]:
    payload = json.loads(Path(transactions_path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Transactions JSON must be a list of case objects.")

    results: List[Dict[str, Any]] = []
    for case in payload:
        retrieval = search_regulations(case, corpus_path=corpus_path)
        analysis = generate_legal_analysis(case, retrieval)
        results.append(
            {
                "tx_id": case.get("tx_id"),
                "scenario_tag": case.get("scenario_tag"),
                "retrieval_match": retrieval["retrieval_match"],
                "top_chunks": retrieval["chunks"][:3],
                "analysis": analysis,
            }
        )

    return {
        "case_count": len(results),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local L3 pipeline on a transactions JSON file.")
    parser.add_argument("--transactions", required=True, help="Path to test transactions JSON")
    parser.add_argument("--corpus", required=True, help="Path to regulation corpus JSON")
    parser.add_argument("--output", help="Optional output JSON path")
    args = parser.parse_args()

    results = run_cases(args.transactions, args.corpus)
    output = json.dumps(results, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Wrote L3 results to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
