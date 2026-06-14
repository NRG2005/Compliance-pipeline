import os
import sys
import json
import time
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

import chromadb

# Add parent directory to path to import local modules
sys.path.append(str(Path(__file__).parent.parent))

from L3_regulation_interpreter.hybrid_retrieval import chunk_regulation_document
from L3_regulation_interpreter.llm_client import generate_ollama_embedding
from L3_regulation_interpreter.corpus_builder import pdf_to_document

load_dotenv()

BLOB_CONN_STR = os.environ.get("BLOB_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER = "core-regulations"
CHROMA_DB_PATH = "chroma_db"
COLLECTION_NAME = "compliance_regulations"


def download_blob_corpus() -> List[Dict[str, Any]]:
    """Downloads all regulation PDF files from Blob Storage and converts them to document objects."""
    print(f"Connecting to Blob Storage container: {BLOB_CONTAINER}...")
    blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
    container_client = blob_service_client.get_container_client(BLOB_CONTAINER)
    
    all_documents = []
    
    # Load tracker
    tracker_file = Path("L3_regulation_interpreter/processed_blobs_chroma.json")
    processed_blobs = set()
    if tracker_file.exists():
        processed_blobs = set(json.loads(tracker_file.read_text(encoding="utf-8")))
    
    blob_list = container_client.list_blobs()
    for blob in blob_list:
        if blob.name.lower().endswith('.pdf'):
            if blob.name in processed_blobs:
                print(f"Skipping '{blob.name}' (already processed)")
                continue
                
            print(f"Downloading '{blob.name}'...")
            blob_client = container_client.get_blob_client(blob)
            blob_data = blob_client.download_blob().readall()
            
            # Save to temporary file to parse with PyPDF
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(blob_data)
                    tmp_path = Path(tmp.name)
                
                doc = pdf_to_document(tmp_path)
                doc["document_id"] = blob.name.replace(".pdf", "").replace(".PDF", "")
                doc["title"] = doc["document_id"]
                all_documents.append(doc)
                
                processed_blobs.add(blob.name)
                os.remove(tmp_path)
            except Exception as e:
                print(f"Skipping {blob.name} due to PDF parse error: {e}")
                
    # Save tracker
    tracker_file.write_text(json.dumps(list(processed_blobs)), encoding="utf-8")
                
    if not all_documents and not processed_blobs:
        print("Error: No PDF documents found in the Blob container.")
        sys.exit(1)
        
    return all_documents


def _embed_with_retry(text: str) -> List[float]:
    for attempt in range(5):
        vector = generate_ollama_embedding(text)
        if vector:
            return vector
        time.sleep(2 ** attempt)
    return []


def main():
    if not BLOB_CONN_STR:
        print("Missing Azure Blob Storage credentials in .env file.")
        sys.exit(1)
        
    print(f"Initializing ChromaDB at {CHROMA_DB_PATH}...")
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
    
    documents = download_blob_corpus()
    
    if not documents:
        print("No new documents to process! All PDFs are already ingested in ChromaDB.")
        sys.exit(0)
    
    print("Chunking documents...")
    all_chunks = []
    for doc in documents:
        all_chunks.extend(chunk_regulation_document(doc))
    print(f"Generated {len(all_chunks)} chunks for full ingestion.")
    
    print("Starting batch embedding and Chroma upload...")
    
    batch_ids = []
    batch_embeddings = []
    batch_metadatas = []
    batch_documents = []
    
    batch_size = 500
    total_uploaded = 0
    
    for i, chunk in enumerate(all_chunks):
        if i % 100 == 0:
            print(f"  Processing chunk {i}/{len(all_chunks)}...")
            
        vector = _embed_with_retry(chunk["searchable_text"])
        if not vector:
            print(f"  Warning: Failed to embed chunk {chunk['chunk_id']}, skipping.")
            continue
            
        chunk_id = chunk["chunk_id"].replace(":", "-").replace("_", "-")
        
        batch_ids.append(chunk_id)
        batch_embeddings.append(vector)
        batch_documents.append(chunk["content"])
        
        # Chroma metadata must be dict[str, str | int | float | bool]
        metadata = {
            "document_id": str(chunk.get("document_id", "")),
            "title": str(chunk.get("title", "")),
            "section_heading": str(chunk.get("section_heading", "")),
            "searchable_text": str(chunk.get("searchable_text", ""))
        }
        batch_metadatas.append(metadata)
        
        if len(batch_ids) >= batch_size:
            collection.upsert(
                ids=batch_ids,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
                documents=batch_documents
            )
            total_uploaded += len(batch_ids)
            print(f"  Uploaded batch to Chroma. Total uploaded: {total_uploaded}/{len(all_chunks)}")
            
            # Reset batches
            batch_ids, batch_embeddings, batch_metadatas, batch_documents = [], [], [], []

    if batch_ids:
        collection.upsert(
            ids=batch_ids,
            embeddings=batch_embeddings,
            metadatas=batch_metadatas,
            documents=batch_documents
        )
        total_uploaded += len(batch_ids)
        print(f"  Uploaded final batch to Chroma. Total uploaded: {total_uploaded}/{len(all_chunks)}")

    print("Ingestion complete! All chunks are stored securely in local ChromaDB.")

if __name__ == "__main__":
    main()
