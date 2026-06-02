"""
L6: SHA-256 Hash Chain

Manages the creation and verification of the tamper-proof audit log.
"""
import hashlib
import json

def calculate_hash(data):
    """Calculates the SHA-256 hash of a dictionary."""
    encoded_data = json.dumps(data, sort_keys=True).encode('utf-8')
    return hashlib.sha256(encoded_data).hexdigest()

def get_previous_hash():
    """Retrieves the hash of the last block in the chain from blob storage."""
    # TODO: Implement logic to get the last hash from blob storage
    return "genesis_hash_placeholder" # Placeholder for the first run

def append_to_chain(event, verdict):
    """
    Appends a new block to the hash chain.
    """
    prev_hash = get_previous_hash()
    layer_data = {
        "event": event,
        "verdict": verdict
    }
    
    block_to_hash = {
        "prev_hash": prev_hash,
        "layer_data": layer_data
    }
    
    new_hash = calculate_hash(block_to_hash)
    
    new_block = {
        "hash": new_hash,
        "data": block_to_hash
    }
    
    # TODO: Write the new_block to immutable blob storage
    print(f"L6: Appending new block with hash: {new_hash}")
