"""
L0: Event Ingestion
Reads transactions.csv and publishes each row as a JSON message
to Azure Queue Storage (tx-events queue).
Also provides a receiver function for L1 to consume messages.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

import csv
import json
import base64
import logging
from pathlib import Path
from azure.storage.queue import QueueClient, QueueMessage
from config import get_config

VALID_CHANNELS = {"UPI", "NEFT", "RTGS", "IMPS", "SWIFT"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [L0] %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)
config = get_config()


def get_queue_client() -> QueueClient:
    """Returns an authenticated Queue client — no encode policy, plain JSON."""
    return QueueClient.from_connection_string(
        config.AZURE_STORAGE_CONNECTION_STRING,
        config.AZURE_STORAGE_QUEUE_NAME,
    )

def publish_transactions(csv_path: str = "data/transactions.csv") -> dict:
    """
    Reads transactions.csv and publishes each row as a JSON message
    to the Azure Queue Storage tx-events queue.

    Returns a summary dict: {total, published, errors}
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    client = get_queue_client()
    stats = {"total": 0, "published": 0, "errors": 0}

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k: v.strip() for k, v in row.items()}
            stats["total"] += 1
            try:
                message = json.dumps(row)
                client.send_message(message)
                stats["published"] += 1
                log.info(f"Published {row['tx_id']} | {row['channel']} | ₹{row['amount_inr']}")
            except Exception as e:
                log.error(f"Failed to publish {row.get('tx_id', '?')}: {e}")
                stats["errors"] += 1

    log.info(f"Done. published={stats['published']} errors={stats['errors']}")
    return stats

def receive_message():
    client   = get_queue_client()
    messages = client.receive_messages(max_messages=1, visibility_timeout=60)
    for msg in messages:
        try:
            tx = json.loads(msg.content)
            # Numeric conversions
            tx['amount_inr']    = float(tx.get('amount_inr', 0))
            tx['is_cross_border'] = tx.get('is_cross_border', '0') == '1'
            tx['usd_equiv']     = float(tx['usd_equiv']) if tx.get('usd_equiv') else None
            tx['fx_usd_inr']    = float(tx['fx_usd_inr']) if tx.get('fx_usd_inr') else None
            return msg, tx
        except Exception as e:
            log.error(f'Parse error: {e}')
            client.delete_message(msg)
            return None
    return None

def delete_message(msg: QueueMessage) -> None:
    """Deletes (acks) a message after successful processing."""
    client = get_queue_client()
    client.delete_message(msg)


def get_queue_length() -> int:
    """Returns the approximate number of messages in the queue."""
    client = get_queue_client()
    props = client.get_queue_properties()
    return props.approximate_message_count


if __name__ == "__main__":
    stats = publish_transactions()
    print(f"\nPublished {stats['published']}/{stats['total']} transactions")
    print(f"Queue length: {get_queue_length()}")