import asyncio
import csv
import random
import os
from pathlib import Path
from L1_orchestrator import orchestrator
from L2_transaction_monitor.data_layer import DataLayer

async def run():
    print("================================================================")
    print(" 🚀  STARTING RANDOMIZED COMPLIANCE PIPELINE TEST  🚀 ")
    print("================================================================\n")
    
    # 0. Clear case memory to prevent short-circuiting during presentation
    memory_file = Path("data/case_memory.json")
    if memory_file.exists():
        os.remove(memory_file)
        print("🧹 Cleared case memory cache for fresh testing.\n")

    # 1. Load Ground Truth
    gt_path = Path("L2_transaction_monitor/data/ground_truth.csv")
    clean_txs = []
    suspicious_txs = []
    
    with open(gt_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["is_suspicious"] == "YES":
                suspicious_txs.append(row)
            else:
                clean_txs.append(row)
                
    # 2. Pick 1 Random Clean and 2 Random Suspicious
    selected_gt = random.sample(clean_txs, 1) + random.sample(suspicious_txs, 2)
    selected_ids = {row["tx_id"]: row for row in selected_gt}
    
    # 3. Load full transaction payloads
    csv_path = Path("L2_transaction_monitor/data/transactions.csv")
    transactions = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["tx_id"] in selected_ids:
                # Attach ground truth to the row so we can print it
                row["_ground_truth"] = selected_ids[row["tx_id"]]
                transactions.append(row)
                
    # 4. Run through the pipeline
    for i, tx in enumerate(transactions, 1):
        gt = tx["_ground_truth"]
        
        tx_adapted = dict(tx)
        if "amount" not in tx_adapted and "amount_inr" in tx_adapted:
            tx_adapted["amount"] = tx_adapted["amount_inr"]
        
        print(f"================================================================")
        print(f" 📦 TEST CASE {i}/3: {tx_adapted['tx_id']}")
        print(f"================================================================")
        print(f"   👤 Sender: {tx_adapted.get('sender_account_id')}   ➔   👤 Receiver: {tx_adapted.get('receiver_account_id')}")
        print(f"   💰 Amount: ₹{tx_adapted.get('amount_inr')}      |   🏦 Channel: {tx_adapted.get('channel')}")
        print(f"")
        print(f"   🎯 GROUND TRUTH EXPECTATION:")
        print(f"      - Is Suspicious?  {gt['is_suspicious']}")
        print(f"      - True Scenario:  {gt['scenario_label']}")
        print(f"      - Notes:          {gt['ground_truth_notes']}")
        print(f"----------------------------------------------------------------")
        print(f"   ⏳ Running Pipeline...\n")
        
        # Disable logging to make output cleaner
        import logging
        logging.getLogger().setLevel(logging.CRITICAL)
        
        state = await orchestrator.handle_event(tx_adapted)
        
        print(f"   ✅ PIPELINE RESULTS:")
        print(f"      - Route Taken:   {state.get('route')}")
        print(f"      - L2 Score:      {state.get('suspicion_score', 'N/A')}")
        if state.get('triggers_fired'):
            print(f"      - L2 Triggers:   {state.get('triggers_fired')}")
            
        if state.get('verdict'):
            verdict = state.get('verdict').upper()
            icon = "🔴" if verdict == "SUSPICIOUS" else "🟡" if verdict == "REVIEW" else "🟢"
            print(f"      - L3 Verdict:    {icon} {verdict}")
            print(f"      - L3 Confidence: {state.get('confidence')}")
            
            # Print citation if suspicious
            citations = state.get('citation_trail')
            if citations and isinstance(citations, list) and len(citations) > 0:
                print(f"      - L3 Citation:   {citations[0].get('why_it_matters', '')}")
            elif citations and isinstance(citations, str):
                print(f"      - L3 Fallback:   {citations}")
                
        print("\n\n")

if __name__ == "__main__":
    asyncio.run(run())
