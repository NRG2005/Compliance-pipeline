import os
from pathlib import Path


def load_project_env(env_path: str | None = None) -> None:
    """
    Lightweight .env loader so the project can run without python-dotenv.
    Existing environment variables win over .env values.
    """
    candidate = Path(env_path) if env_path else Path(__file__).resolve().parent / ".env"
    if not candidate.exists():
        return

    for raw_line in candidate.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


load_project_env()

class Config:
    """Base configuration."""
    # Azure Service Bus
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
    SEARCH_INDEX_NAME = "regulations"

    # Azure AI Document Intelligence
    DOC_INTELLIGENCE_ENDPOINT = os.environ.get("DOC_INTELLIGENCE_ENDPOINT")
    DOC_INTELLIGENCE_KEY = os.environ.get("DOC_INTELLIGENCE_KEY")

    # Local / model settings
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.1")
    LOCAL_REGULATION_CORPUS_PATH = os.environ.get("LOCAL_REGULATION_CORPUS_PATH")
    L3_TOP_K = os.environ.get("L3_TOP_K", "5")
    L3_CHUNK_WORDS = os.environ.get("L3_CHUNK_WORDS", "140")
    L3_CHUNK_OVERLAP = os.environ.get("L3_CHUNK_OVERLAP", "30")
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi4-mini:latest")

    # Other
    FIU_IND_DEADLINE_DAYS = 7

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False

# Select the configuration based on an environment variable
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}

def get_config():
    config_name = os.environ.get("FLASK_ENV", "default")
    return config[config_name]()
