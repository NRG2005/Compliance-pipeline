"""
L7: Regulatory Watch

A scheduled job that monitors regulatory sources for changes.
"""
import os
import json
from .scraper import scrape_sources, STATE_FILE
from .classifier import classify_changes
from .indexer import update_search_index, check_document_exists
from .blob_storage import upload_to_blob

async def regulatory_watch_job():
    """
    The main function for the 6-hour cron job.
    """
    print("L7: Starting regulatory watch job...")
    
    # 1. Scrape sources for new/updated documents
    new_documents = scrape_sources()
    
    if not new_documents:
        print("L7: No new documents found. Exiting.")
        return
        
    for doc in reversed(new_documents): # Process oldest to newest
        print(f"\nL7: Processing document: {doc['title']}")
        
        # 2. Check if already ingested to avoid re-classifying and re-chunking
        if check_document_exists(doc['title']):
            print(f"L7: Document '{doc['title']}' is already in Azure. Skipping.")
            continue
            
        # 3. Classify change and generate summary
        change_info = classify_changes(doc['text'])
        
        # 4. Check Relevance Filter
        if not change_info.get("is_relevant", True):
            print(f"L7: Document '{doc['title']}' is marked IRRELEVANT (e.g. ATM maintenance). Skipping Azure ingestion.")
            continue
            
        print(f"L7: Document '{doc['title']}' is RELEVANT for KYC/AML. Proceeding.")
        
        # 4. Chunk, embed, and update Azure AI Search index
        update_search_index(doc, change_info)
        
        # 5. Save raw doc to Azure Blob Storage
        upload_to_blob(doc)
        
        # TODO: Notify team via email or Teams
        
    # 5. Update state tracker so we don't scrape these again
    newest_url = new_documents[0]['url']
    with open(STATE_FILE, 'w') as f:
        json.dump({"last_processed_url": newest_url}, f)
    print(f"\nL7: State updated. Last processed URL is now: {newest_url}")
        
    print("L7: Regulatory watch job finished.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(regulatory_watch_job())
