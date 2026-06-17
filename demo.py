import argparse
import asyncio
import json
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from L0_event_ingestion.event_receiver import get_queue_client
from L1_orchestrator import orchestrator

async def run_pipeline(count=1):
    print(f"Reading up to {count} messages from Azure Queue...")
    client = get_queue_client()
    messages = client.receive_messages(max_messages=count, visibility_timeout=60)
    
    processed = 0
    for msg in messages:
        try:
            tx = json.loads(msg.content)
            print(f"\n==================================================")
            print(f"📥 [L0] PULLING FROM QUEUE: {tx.get('tx_id')}")
            print(f"==================================================")
            
            # Numeric conversions mirroring L0
            if 'amount_inr' in tx: tx['amount_inr'] = float(tx['amount_inr'])
            if 'usd_equiv' in tx and tx['usd_equiv']: tx['usd_equiv'] = float(tx['usd_equiv'])
            if 'fx_usd_inr' in tx and tx['fx_usd_inr']: tx['fx_usd_inr'] = float(tx['fx_usd_inr'])
            
            # Route to L1
            state = await orchestrator.handle_event(tx)
            
            print(f"\n📊 VERDICT FOR {tx.get('tx_id')}")
            print(f"   Route: {state['route']}")
            print(f"   L2 Score: {state.get('suspicion_score', 'N/A')}")
            
            # Delete from queue on success
            client.delete_message(msg)
            processed += 1
            
        except Exception as e:
            print(f"Error processing message: {e}")
            
    if processed == 0:
        print("Queue is empty — nothing to process.")

def publish_file(filepath):
    path = Path(filepath)
    if not path.exists():
        print(f"File not found: {filepath}")
        return
        
    try:
        tx = json.loads(path.read_text())
        client = get_queue_client()
        client.send_message(json.dumps(tx))
        print(f"✅ Published {tx.get('tx_id')} to Azure Queue!")
    except Exception as e:
        print(f"Failed to publish: {e}")

def clear_cache():
    cache_path = Path("data/case_memory.json")
    if cache_path.exists():
        cache_path.unlink()
        print("🗑️ Cleared data/case_memory.json cache!")
    else:
        print("Cache was already empty.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo Runbook CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    # run command
    run_parser = subparsers.add_parser("run", help="Pull from Azure Queue and run pipeline")
    run_parser.add_argument("--count", type=int, default=1)
    
    # publish-file command
    publish_parser = subparsers.add_parser("publish-file", help="Push JSON file to Azure Queue")
    publish_parser.add_argument("filepath", type=str)
    
    # clear command
    clear_parser = subparsers.add_parser("clear", help="Clear L1 case memory cache")
    
    args = parser.parse_args()
    
    if args.command == "run":
        asyncio.run(run_pipeline(args.count))
    elif args.command == "publish-file":
        publish_file(args.filepath)
    elif args.command == "clear":
        clear_cache()
    else:
        parser.print_help()
