import asyncio
import json
from pathlib import Path
from L1_orchestrator import orchestrator

async def run_presentation():
    print("==================================================")
    print("🚀 STARTING COMPLIANCE PIPELINE PRESENTATION 🚀")
    print("==================================================\n")
    
    # Load the fresh presentation transactions
    filepath = Path("Presentation_TestTransactions.json")
    transactions = json.loads(filepath.read_text())
    
    for tx in transactions:
        print(f"--------------------------------------------------")
        print(f"📥 [L0] INGESTING NEW TRANSACTION: {tx['tx_id']}")
        print(f"   Amount: ₹{tx['amount']} | Channel: {tx['channel']}")
        print(f"   Scenario: {tx['scenario_tag'].upper()}")
        print(f"--------------------------------------------------")
        
        # Pass the transaction into the main L1 orchestrator
        state = await orchestrator.handle_event(tx)
        
        print("\n📊 PIPELINE RESULTS FOR", tx['tx_id'])
        print(f"   Route Taken: {state['route']}")
        print(f"   L2 Suspicion Score: {state.get('suspicion_score', 'N/A')}")
        
        # If L3 was triggered, show its verdict
        if state.get('verdict'):
            print(f"   L3 Legal Verdict: {state['verdict'].upper()}")
            print(f"   L3 Confidence: {state['confidence']}")
        print("\n")

if __name__ == "__main__":
    asyncio.run(run_presentation())
