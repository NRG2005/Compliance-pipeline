import os
from dotenv import load_dotenv
load_dotenv()
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

endpoint = os.environ.get("SEARCH_ENDPOINT")
key = os.environ.get("SEARCH_API_KEY")
index_name = "compliance-regulations"

credential = AzureKeyCredential(key)
search_client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)

results = search_client.search(search_text="Credit Derivatives", select=["chunk_id", "title"])
chunks = list(results)
print(f"Found {len(chunks)} chunks")
if chunks:
    search_client.delete_documents(documents=[{"chunk_id": c["chunk_id"]} for c in chunks])
    print("Deleted.")
