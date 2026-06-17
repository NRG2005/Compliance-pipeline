import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration."""
    # Azure Queue Storage (L0 transport)
    AZURE_STORAGE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", os.environ.get("BLOB_STORAGE_CONNECTION_STRING"))
    AZURE_STORAGE_QUEUE_NAME = os.environ.get("AZURE_STORAGE_QUEUE_NAME", "tx-events")
    AZURE_STORAGE_ACCOUNT_NAME = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")

    # Azure Service Bus (kept for production upgrade path)
    SERVICE_BUS_CONNECTION_STRING = os.environ.get("SERVICE_BUS_CONNECTION_STRING")
    SERVICE_BUS_TOPIC_NAME = "tx-events"
    SERVICE_BUS_PIPELINE_SUB_NAME = "pipeline-sub"
    SERVICE_BUS_AUDIT_SUB_NAME = "audit-sub"

    # Azure Cosmos DB
    COSMOS_DB_ENDPOINT = os.environ.get("COSMOS_DB_ENDPOINT")
    COSMOS_DB_KEY = os.environ.get("COSMOS_DB_KEY")
    COSMOS_DB_DATABASE_NAME = "ComplianceDB"
    COSMOS_DB_CASES_CONTAINER = "Cases"
    COSMOS_DB_AUDIT_CONTAINER = "Audit"

    # Azure Blob Storage
    BLOB_STORAGE_CONNECTION_STRING = os.environ.get("BLOB_STORAGE_CONNECTION_STRING")
    BLOB_REPORTS_CONTAINER = "reports"
    BLOB_SCHEMAS_CONTAINER = "schemas"
    BLOB_AUDIT_LOG_CONTAINER = "audit-logs"

    # Azure AI Search
    SEARCH_ENDPOINT = os.environ.get("SEARCH_ENDPOINT")
    SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY")
    SEARCH_INDEX_NAME = "compliance-regulations"

    # Azure AI Document Intelligence
    DOC_INTELLIGENCE_ENDPOINT = os.environ.get("DOC_INTELLIGENCE_ENDPOINT")
    DOC_INTELLIGENCE_KEY = os.environ.get("DOC_INTELLIGENCE_KEY")

    # Ollama / local model gateway
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi4-mini:latest")

    # Pipeline settings
    FIU_IND_DEADLINE_DAYS = 7
    L2_ENDPOINT = os.environ.get("L2_ENDPOINT", "http://localhost:8002/process")
    L6_ENDPOINT = os.environ.get("L6_ENDPOINT", "http://localhost:8006/log")

    #Dataset file paths
    TRANSACTIONS_CSV   = "data/transactions.csv"
    ACCOUNTS_CSV       = "data/accounts.csv"        
    WATCHLIST_CSV      = "data/watchlist.csv"
    CASE_HISTORY_CSV   = "data/case_history.csv"    
    GROUND_TRUTH_CSV   = "data/ground_truth.csv"

    # New channel added in dataset
    VALID_CHANNELS = {"UPI", "NEFT", "RTGS", "IMPS", "SWIFT"} 


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}


def get_config():
    config_name = os.environ.get("FLASK_ENV", "default")
    return config[config_name]()