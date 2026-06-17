import asyncio
import csv
from L2_transaction_monitor.orchestrator import monitor
from L2_transaction_monitor.data_layer import DataLayer
from datetime import datetime

def parse_ts(ts):
    if not ts: return None
    try: return datetime.fromisoformat(ts)
    except: return None

async def main():
    dl = DataLayer()
    
    with open("L2_transaction_monitor/data/smurfing_transactions.csv", "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} rows.")
    count = 0
    max_score = 0.0
    for row in rows:
        payload = dict(row)
        payload["receiver_account_id"] = payload.get("receiver_account_external", "")
        payload["receiver_pan"] = payload.get("receiver_pan", "")
        payload["receiver_dob"] = payload.get("receiver_dob", "")
        payload["receiver_cin"] = ""
        try:
            payload["amount_inr"] = float(payload["amount_inr"])
        except ValueError:
            payload["amount_inr"] = 0.0
            
        try:
            res = await monitor(payload, dl)
            score = res.get("suspicion_score", 0.0)
            if score > max_score:
                max_score = score
            if score >= 0.5:
                print(f"Very Suspicious! {payload['tx_id']} - Score: {score}")
                
            # ADD TO HISTORY manually
            dl.add_to_history(payload)
                
        except Exception as e:
            print(f"Error for tx {payload['tx_id']}: {e}")
            pass # ignore errors

    print(f"Max score found: {max_score}")

if __name__ == "__main__":
    asyncio.run(main())
