import os
from azure.storage.blob import BlobServiceClient

def upload_to_blob(document: dict):
    """
    Uploads the raw scraped document text to Azure Blob Storage for archival/reference.
    """
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    container_name = "compliance-regulations-raw"
    
    if not connection_string:
        print("L7: Warning: Missing AZURE_STORAGE_CONNECTION_STRING. Skipping blob upload.")
        return
        
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        
        if not container_client.exists():
            container_client.create_container()
            
        doc_id = document.get("document_id", "unknown_doc")
        blob_name = f"{doc_id}.txt"
        
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(document.get("text", ""), overwrite=True)
        print(f"L7: Successfully uploaded raw text to Blob Storage: {blob_name}")
    except Exception as e:
        print(f"L7: Failed to upload to Blob Storage: {e}")
