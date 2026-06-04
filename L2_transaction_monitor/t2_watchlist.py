"""
T2: Watchlist Check
- FIU-IND sanctioned entities
- Fuzzy match (rapidfuzz)
"""
# Make sure to install the rapidfuzz library: pip install rapidfuzz
try:
    from rapidfuzz import process, fuzz
except ImportError:  # pragma: no cover - optional until T2 is implemented
    process = None
    fuzz = None


async def check_watchlist(transaction, sanctioned_entities=None):
    """
    Checks if entities in the transaction match any sanctioned entities.
    """
    # Placeholder for the first runnable version of L2.
    return 0.0
