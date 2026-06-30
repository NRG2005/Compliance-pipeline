import os
import re
import uuid
from typing import Dict, Any

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from L3_regulation_interpreter.hybrid_retrieval import chunk_regulation_document
from L3_regulation_interpreter.azure_ingestion import _extract_key_phrases

def check_document_exists(title: str) -> bool:
    endpoint = os.environ.get("SEARCH_ENDPOINT")
    key = os.environ.get("SEARCH_API_KEY")
    index_name = "compliance-regulations"
    
    if not endpoint or not key:
        return False
        
    credential = AzureKeyCredential(key)
    search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)
    
    try:
        # Search for exact title match (using quotes). We fetch top 1 to minimize payload.
        results = list(search_client.search(search_text=f'"{title}"', select=["title"], top=5))
        for r in results:
            if r.get("title") and title.lower().strip() in r["title"].lower().strip():
                return True
        return False
    except Exception as e:
        print(f"L7: Failed to check existence for '{title}': {e}")
        return False

def update_search_index(document: Dict[str, Any], change_info: dict):
    """
    Deletes old regulation chunks if applicable, and uploads new chunks to Azure AI Search.
    """
    print(f"L7: Updating search index. Action: {change_info.get('action')}")
    
    endpoint = os.environ.get("SEARCH_ENDPOINT")
    key = os.environ.get("SEARCH_API_KEY")
    index_name = "compliance-regulations"
    
    if not endpoint or not key:
        print("L7: Warning: Missing SEARCH_ENDPOINT or SEARCH_API_KEY. Skipping index update.")
        return
        
    credential = AzureKeyCredential(key)
    search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)
    
    # 1. DELETE OLD DOCUMENT (RAG-Hunter)
    action = change_info.get("action")
    target_id = change_info.get("target_circular_id")
    
    if action in ["update", "replacement"] and target_id:
        print(f"L7: RAG-Hunter is hunting for old circular: {target_id}")
        try:
            # Search for the old document
            results = search_client.search(
                search_text=target_id,
                select=["document_id"],
                top=1
            )
            
            top_result = next(results, None)
            if top_result and top_result.get("document_id"):
                doc_to_delete = top_result["document_id"]
                print(f"L7: Found target document_id: {doc_to_delete}. Executing wipe...")
                
                # Find all chunks for that document
                chunk_results = search_client.search(
                    search_text="*",
                    filter=f"document_id eq '{doc_to_delete}'",
                    select=["chunk_id"]
                )
                
                chunks_to_delete = [{"chunk_id": chunk["chunk_id"]} for chunk in chunk_results]
                
                if chunks_to_delete:
                    search_client.delete_documents(documents=chunks_to_delete)
                    print(f"L7: Successfully deleted {len(chunks_to_delete)} old chunks.")
            else:
                print(f"L7: Could not find old circular {target_id} in Azure.")
        except Exception as e:
            print(f"L7: Failed to delete old document: {e}")
            
    # 2. UPLOAD NEW DOCUMENT
    print("L7: Chunking and uploading new document...")
    # Assign a new UUID for this document if it doesn't have one
    if "document_id" not in document:
        document["document_id"] = str(uuid.uuid4())
        
    # Chunk the text using the existing pipeline algorithm
    raw_chunks = chunk_regulation_document(document)
    
    batch = []
    for chunk in raw_chunks:
        # We don't embed because Azure Free Tier limit is reached.
        # Use simple key phrases extraction as a cognitive skill emulation
        chunk["key_phrases"] = _extract_key_phrases(chunk["searchable_text"])
        chunk["chunk_id"] = re.sub(r'[^a-zA-Z0-9_\-=]', '-', chunk["chunk_id"])
        
        # Keep only fields valid for the Azure index schema
        allowed_keys = {"chunk_id", "document_id", "title", "content", "searchable_text", "section_heading", "key_phrases"}
        clean_chunk = {k: v for k, v in chunk.items() if k in allowed_keys}
        batch.append(clean_chunk)
        
    if batch:
        try:
            search_client.upload_documents(documents=batch)
            print(f"L7: Successfully uploaded {len(batch)} new chunks to Azure AI Search.")
        except Exception as e:
            print(f"L7: Failed to upload new chunks: {e}")
