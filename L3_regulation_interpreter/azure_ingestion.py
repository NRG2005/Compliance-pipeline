"""
L3: Azure Vector Search Ingestion Pipeline

Pulls raw files from Azure Blob Storage, chunks them, embeds them locally
with Ollama (nomic-embed-text), and pushes them into Azure AI Search.
"""
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchAlgorithmMetric,
    VectorSearchProfile,
)
from azure.storage.blob import BlobServiceClient

# Add parent directory to path to import local modules
sys.path.append(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()
from L3_regulation_interpreter.hybrid_retrieval import chunk_regulation_document
from L3_regulation_interpreter.llm_client import generate_ollama_embedding

# Configuration
BLOB_CONN_STR = os.environ.get("BLOB_STORAGE_CONNECTION_STRING")
BLOB_CONTAINER = "core-regulations"
SEARCH_ENDPOINT = os.environ.get("SEARCH_ENDPOINT")
SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY")
INDEX_NAME = "compliance-regulations"
VECTOR_DIMENSIONS = 768  # nomic-embed-text generates 768 dimensions


def download_blob_corpus() -> List[Dict[str, Any]]:
    """Downloads all regulation PDF files from Blob Storage and converts them to document objects."""
    print(f"Connecting to Blob Storage container: {BLOB_CONTAINER}...")
    blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
    container_client = blob_service_client.get_container_client(BLOB_CONTAINER)
    
    from L3_regulation_interpreter.corpus_builder import pdf_to_document
    import tempfile
    
    all_documents = []
    
    # Load tracker
    tracker_file = Path("L3_regulation_interpreter/processed_blobs.json")
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
                
    if not all_documents:
        print("Error: No PDF documents found in the Blob container.")
        sys.exit(1)
        
    return all_documents


import time

def setup_search_index(index_client: SearchIndexClient):
    """Creates the Vector Index in Azure AI Search."""
    print(f"Ensuring index '{INDEX_NAME}' exists...")
    
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="myHnsw",
                parameters={"m": 4, "efConstruction": 400, "efSearch": 500, "metric": VectorSearchAlgorithmMetric.COSINE}
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="myHnswProfile",
                algorithm_configuration_name="myHnsw",
            )
        ]
    )

    fields = [
        SimpleField(name="chunk_id", type=SearchFieldDataType.String, key=True),
        SearchField(name="document_id", type=SearchFieldDataType.String, filterable=True),
        SearchField(name="title", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="searchable_text", type=SearchFieldDataType.String, searchable=True),
        SearchField(name="section_heading", type=SearchFieldDataType.String, searchable=True),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=VECTOR_DIMENSIONS,
            vector_search_profile_name="myHnswProfile"
        )
    ]

    index = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)
    index_client.create_or_update_index(index)
    print("Index configured successfully.")


def _embed_with_retry(text: str) -> List[float]:
    for attempt in range(5):
        vector = generate_ollama_embedding(text)
        if vector:
            return vector
        time.sleep(2 ** attempt)
    return []


def main():
    if not all([BLOB_CONN_STR, SEARCH_ENDPOINT, SEARCH_API_KEY]):
        print("Missing Azure credentials in .env file. Please configure them.")
        sys.exit(1)
        
    credential = AzureKeyCredential(SEARCH_API_KEY)
    index_client = SearchIndexClient(endpoint=SEARCH_ENDPOINT, credential=credential)
    setup_search_index(index_client)
    search_client = SearchClient(endpoint=SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=credential)
        
    documents = download_blob_corpus()
    
    print("Chunking documents...")
    all_chunks = []
    for doc in documents:
        all_chunks.extend(chunk_regulation_document(doc))
    print(f"Generated {len(all_chunks)} chunks for full ingestion.")
    
    print("Starting batch embedding and upload...")
    batch = []
    batch_size = 500
    total_uploaded = 0
    
    for i, chunk in enumerate(all_chunks):
        if i % 100 == 0:
            print(f"  Processing chunk {i}/{len(all_chunks)}...")
            
        vector = _embed_with_retry(chunk["searchable_text"])
        if not vector:
            print(f"  Warning: Failed to embed chunk {chunk['chunk_id']}, skipping.")
            continue
            
        chunk["content_vector"] = vector
        chunk["chunk_id"] = chunk["chunk_id"].replace(":", "-").replace("_", "-")
        
        # Strip fields not in the Azure Index schema
        allowed_keys = {"chunk_id", "document_id", "title", "content", "searchable_text", "section_heading", "content_vector"}
        clean_chunk = {k: v for k, v in chunk.items() if k in allowed_keys}
        
        batch.append(clean_chunk)
        
        if len(batch) >= batch_size:
            try:
                search_client.upload_documents(documents=batch)
                total_uploaded += len(batch)
                print(f"  Uploaded batch. Total uploaded: {total_uploaded}/{len(all_chunks)}")
            except Exception as e:
                print(f"  Warning: Azure upload failed for batch: {e}")
            batch = []
            
    if batch:
        try:
            search_client.upload_documents(documents=batch)
            total_uploaded += len(batch)
            print(f"  Uploaded final batch. Total uploaded: {total_uploaded}/{len(all_chunks)}")
        except Exception as e:
            print(f"  Warning: Azure upload failed for final batch: {e}")

    print("Ingestion complete!")

if __name__ == "__main__":
    main()
