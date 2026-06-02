"""
Main entry point for the Compliance Pipeline.
This script can be used to trigger the pipeline for a single transaction for testing purposes
or could be adapted to run as a continuous service.
"""
import asyncio
from L0_event_ingestion import event_receiver
from L1_orchestrator import orchestrator

async def main(event_payload):
    """
    Orchestrates the full pipeline flow.
    """
    print("Starting compliance pipeline...")
    
    # In a real scenario, L0 would be a separate, continuously running service.
    # Here we simulate receiving an event.
    print("L0: Event Ingestion - Simulating event reception.")
    
    # L1 Orchestrator decides the path.
    print("L1: Orchestrator - Routing event.")
    await orchestrator.handle_event(event_payload)
    
    print("Pipeline run finished.")

if __name__ == "__main__":
    # Example event payload
    mock_event = {
        "tx_id": "some_transaction_id",
        "amount": 50000,
        "sender_id": "sender_account",
        "receiver_id": "receiver_account",
        "channel": "UPI",
        "timestamp": "2026-06-02T10:00:00Z",
        "bank_metadata": {}
    }
    asyncio.run(main(mock_event))
