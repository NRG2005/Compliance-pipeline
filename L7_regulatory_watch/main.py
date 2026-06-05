"""
L7: Regulatory Watch

A scheduled job that monitors regulatory sources for changes.
"""
from .scraper import scrape_sources
from .ocr import extract_text_from_pdfs
from .classifier import classify_changes
from .indexer import update_search_index

async def regulatory_watch_job():
    """
    The main function for the 6-hour cron job.
    """
    print("L7: Starting regulatory watch job...")
    
    # 1. Scrape sources for new/updated documents
    new_documents = await scrape_sources()
    
    for doc in new_documents:
        # 2. If PDF, perform OCR
        if doc['type'] == 'pdf':
            doc['text'] = extract_text_from_pdfs(doc['url'])
        else:
            # Assumes scraper gets text from HTML pages
            pass
            
        # 3. Classify change and generate summary
        change_info = classify_changes(doc['text'])
        
        # 4. Chunk, embed, and update Azure AI Search index
        update_search_index(doc['text'], change_info)
        
        # TODO: Notify team via email or Teams
        
    print("L7: Regulatory watch job finished.")
