"""
End-to-End Compliance Pipeline Runner
Loads test transactions and executes the pipeline (L1 -> L2 -> L3 -> L4/L5 -> L6) for each.
"""
import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from L1_orchestrator import orchestrator


async def run_all_cases(transactions_path: str):
    path = Path(transactions_path)
    if not path.exists():
        print(f"Error: transactions file not found at {transactions_path}")
        return

    try:
        transactions = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        return

    if not isinstance(transactions, list):
        transactions = [transactions]

    print(f"==================================================")
    print(f"Loaded {len(transactions)} test transactions.")
    print(f"Starting end-to-end execution of Compliance Pipeline...")
    print(f"==================================================\n")

    for index, tx in enumerate(transactions, start=1):
        tx_id = tx.get("tx_id", f"UNKNOWN-{index}")
        scenario = tx.get("scenario_tag", "general")
        print(f"\n--- [{index}/{len(transactions)}] Processing TX: {tx_id} ({scenario}) ---")
        try:
            await orchestrator.handle_event(tx)
        except Exception as e:
            print(f"ERROR processing transaction {tx_id}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        print(f"--------------------------------------------------")

    print(f"\n==================================================")
    print(f"Compliance Pipeline E2E Run Complete.")
    print(f"==================================================")


if __name__ == "__main__":
    tx_file = "L3_TestTransactions.json"
    if len(sys.argv) > 1:
        tx_file = sys.argv[1]
        
    asyncio.run(run_all_cases(tx_file))
