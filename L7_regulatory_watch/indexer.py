"""
L7: Search Indexer
Updates the Azure AI Search index with new regulation text.
For local development, this updates our local JSON regulation corpus.
"""
import json
import uuid
from pathlib import Path
from config import get_config

config = get_config()

def update_search_index(document_text: str, change_info: dict) -> bool:
    """
    Mock search indexer.
    Appends the new regulation to the local json corpus for immediate retrieval.
    """
    print(f"L7: Updating local search index (mocking Azure AI Search indexing)...")
    corpus_path = config.LOCAL_REGULATION_CORPUS_PATH or "L3_regulation_interpreter/regulation_corpus.json"
    
    path = Path(corpus_path)
    if not path.exists():
        print(f"L7: Warning - local corpus path {corpus_path} not found.")
        return False
        
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        
        # Build document shape
        new_doc = {
            "document_id": str(uuid.uuid4())[:8],
            "title": f"Regulatory Update: {change_info.get('change_type', 'Circular')}",
            "regulator": "RBI",
            "document_type": change_info.get("change_type", "circular"),
            "effective_date": "2026-06-04",
            "url": "https://example.org/rbi-update",
            "tags": change_info.get("tags", ["KYC", "AML"]),
            "sections": [
                {
                    "section_id": "sec-1",
                    "heading": "Regulation Text",
                    "text": document_text,
                    "clauses": [document_text]
                }
            ]
        }
        
        # Append document
        if "documents" in data:
            data["documents"].append(new_doc)
        else:
            data.append(new_doc)
            
        # For safety in local environment, we can choose not to overwrite the master corpus
        # directly in the base repository, or write it back.
        # Let's write it back so the RAG database is live!
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"L7: Successfully indexed 1 new regulation chunk.")
        return True
    except Exception as e:
        print(f"L7: Failed to update search index: {e}")
        return False
