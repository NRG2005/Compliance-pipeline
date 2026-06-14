import os
import sys
import tempfile
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()

BLOB_CONN_STR = os.environ.get("BLOB_STORAGE_CONNECTION_STRING")
SOURCE_CONTAINER = "regulations"
TARGET_CONTAINER = "core-regulations"

EXCLUDE_TERMS = ["press", "speech", "faq", "frequently asked", "annual report", "penalty", "order", "governance", "board", "committee", "statistics", "bulletin"]
INCLUDE_TERMS = ["master direction", "master circular", "pmla", "fema", "kyc", "aml", "npci", "upi", "payment aggregator", "prepaid", "ppi", "lrs", "fiu"]

def should_keep(blob_name, blob_client):
    lower_name = blob_name.lower()
    
    # 1. Quick Exclusion by name
    if any(term in lower_name for term in EXCLUDE_TERMS):
        return False, "Excluded by filename"
        
    # 2. Quick Inclusion by name
    if any(term in lower_name for term in INCLUDE_TERMS):
        return True, "Included by filename"
        
    # 3. Deep check (Download first 2 pages)
    print(f"  Ambiguous name '{blob_name}', inspecting content...")
    try:
        data = blob_client.download_blob().readall()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(data)
            tmp_path = tmp.name
            
        reader = PdfReader(tmp_path)
        text = ""
        for i in range(min(2, len(reader.pages))):
            text += (reader.pages[i].extract_text() or "") + " "
        os.remove(tmp_path)
        
        lower_text = text.lower()
        if any(term in lower_text for term in EXCLUDE_TERMS):
            return False, "Excluded by content"
        if any(term in lower_text for term in INCLUDE_TERMS):
            return True, "Included by content"
            
    except Exception as e:
        print(f"  Failed to read PDF '{blob_name}': {e}")
        return False, "Error reading PDF"
        
    return False, "No inclusion criteria met"

def main():
    if not BLOB_CONN_STR:
        print("Missing BLOB_STORAGE_CONNECTION_STRING")
        sys.exit(1)
        
    blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONN_STR)
    source_client = blob_service_client.get_container_client(SOURCE_CONTAINER)
    target_client = blob_service_client.get_container_client(TARGET_CONTAINER)
    
    if not target_client.exists():
        target_client.create_container()
        print(f"Created target container: {TARGET_CONTAINER}")
        
    blobs = source_client.list_blobs()
    kept = 0
    discarded = 0
    
    for blob in blobs:
        if not blob.name.lower().endswith(".pdf"):
            continue
            
        print(f"Analyzing: {blob.name}")
        blob_client = source_client.get_blob_client(blob)
        
        keep, reason = should_keep(blob.name, blob_client)
        
        if keep:
            print(f"  [KEEP] {reason}")
            # Copy blob
            target_blob = target_client.get_blob_client(blob.name)
            if not target_blob.exists():
                source_blob_url = blob_client.url
                target_blob.start_copy_from_url(source_blob_url)
            kept += 1
        else:
            print(f"  [DISCARD] {reason}")
            discarded += 1
            
    print(f"\nFiltering Complete! Kept: {kept}, Discarded: {discarded}")
    print(f"Core regulations copied to container: '{TARGET_CONTAINER}'")

if __name__ == "__main__":
    main()
