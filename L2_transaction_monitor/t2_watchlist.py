"""
T2: Watchlist Check
- FIU-IND sanctioned entities
- Fuzzy match (rapidfuzz)
"""
# Make sure to install the rapidfuzz library: pip install rapidfuzz
from rapidfuzz import process, fuzz

def check_watchlist(transaction, sanctioned_entities):
    """
    Checks if entities in the transaction match any sanctioned entities.
    """
    # TODO: Implement watchlist check logic using fuzzy matching
    pass
