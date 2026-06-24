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
    """Loads regulations from the local parsed JSON corpus instead of Blob Storage."""
    print("Loading regulations from local corpus.json...")
    corpus_path = Path("L3_regulation_interpreter/regulation_corpus.json")
    if not corpus_path.exists():
        print("Error: regulation_corpus.json not found.")
        sys.exit(1)
        
    try:
        with open(corpus_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("documents", [])
    except Exception as e:
        print(f"Error loading local corpus: {e}")
        sys.exit(1)


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
            name="key_phrases",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            filterable=True,
            facetable=True
        )
    ]

    try:
        index_client.delete_index(INDEX_NAME)
        print(f"Deleted existing index '{INDEX_NAME}' to clear quota.")
    except Exception:
        pass

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

import re

def _extract_key_phrases(text: str) -> List[str]:
    # Simplified local cognitive skill emulation
    stopwords = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "as", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "can", "could", "shall", "should", "will", "would", "may", "might", "must", "it", "this", "that", "these", "those", "from", "which", "who", "whom", "whose", "what", "how", "why", "when", "where", "under", "over", "between", "through", "into", "onto", "upon", "about", "against", "among", "after", "before", "during", "while", "since", "until", "any", "all", "such", "other", "some", "no", "not", "only", "same", "so", "than", "too", "very"}
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    freq = {}
    for w in words:
        if w not in stopwords:
            freq[w] = freq.get(w, 0) + 1
    sorted_words = sorted(freq.keys(), key=lambda w: freq[w], reverse=True)
    return sorted_words[:15]

def main():
    if not all([SEARCH_ENDPOINT, SEARCH_API_KEY]):
        print("Missing Azure Search credentials in .env file.")
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
        chunk["key_phrases"] = _extract_key_phrases(chunk["searchable_text"])
        chunk["chunk_id"] = re.sub(r'[^a-zA-Z0-9_\-=]', '-', chunk["chunk_id"])
        
        # Strip fields not in the Azure Index schema
        allowed_keys = {"chunk_id", "document_id", "title", "content", "searchable_text", "section_heading", "key_phrases"}
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
