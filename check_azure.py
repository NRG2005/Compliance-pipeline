import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from dotenv import load_dotenv

def check_db():
    load_dotenv()
    endpoint = os.environ.get("SEARCH_ENDPOINT")
    key = os.environ.get("SEARCH_API_KEY")
    index_name = "compliance-regulations"
    
    credential = AzureKeyCredential(key)
    search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)
    
    results = search_client.search(search_text="*", select=["chunk_id", "document_id", "title"], top=1000)
    count = 0
    doc_ids = set()
    for doc in results:
        count += 1
        doc_ids.add(doc.get("document_id"))
        
    print(f"Total chunks in Azure: {count}")
    print(f"Unique document IDs: {len(doc_ids)}")

check_db()
