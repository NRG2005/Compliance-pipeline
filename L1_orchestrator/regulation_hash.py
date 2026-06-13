import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

REGULATION_META_FILE = Path(__file__).parent.parent / "data" / "regulation_meta.json"
INITIAL_HASH         = "INITIAL_HASH_PLACEHOLDER"


def get_current_hash() -> str:
    """
    Reads the current regulation composite hash from local file.
    Returns INITIAL_HASH_PLACEHOLDER if file doesn't exist yet.
    Production: reads from Cosmos DB regulations-meta container.
    """
    if not REGULATION_META_FILE.exists():
        _seed_regulation_meta()
    with open(REGULATION_META_FILE, encoding="utf-8") as f:
        meta = json.load(f)
    return meta.get("composite_hash", INITIAL_HASH)


def is_stale(cached_hash: str | None, current_hash: str | None) -> bool:
    """
    Returns True if the cached verdict should NOT be reused.

    Decision table:
      cached=None       → True  (no hash stored, conservative)
      current=None      → True  (can't read file, conservative)
      cached != current → True  (regulation changed since verdict)
      cached == current → False (safe to short-circuit)
    """
    if not cached_hash or not current_hash:
        return True
    stale = cached_hash != current_hash
    if stale:
        log.info("Regulation hash changed — full pipeline required")
    return stale


def _seed_regulation_meta() -> None:
    """Creates initial regulation_meta.json if it doesn't exist."""
    REGULATION_META_FILE.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "composite_hash": INITIAL_HASH,
        "sources": {
            "rbi-master-directions": {"hash": "", "last_scraped": None},
            "fiuindia-home":         {"hash": "", "last_scraped": None},
            "npci-upi-circulars":    {"hash": "", "last_scraped": None},
        },
        "updated_at": "2026-05-20T00:00:00Z",
        "_note": "Updated by L7 Regulatory Watch every 6 hours."
    }
    with open(REGULATION_META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    log.info(f"Seeded regulation_meta.json")


def update_hash(new_hash: str) -> None:
    """
    Updates the regulation hash — called by L7 when regulations change.
    Invalidates all cached verdicts, forcing full pipeline re-reasoning.
    """
    import datetime
    meta = {
        "composite_hash": new_hash,
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
    with open(REGULATION_META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    log.info(f"Regulation hash updated to {new_hash[:16]}...")