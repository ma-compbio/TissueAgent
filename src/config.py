from pathlib import Path

ROOT             = Path(__file__).parent.parent
DATA_DIR         = ROOT / "data"
CHROMADB_DIR     = ROOT / ".chromadb"
RAG_DOCUMENT_DIR = ROOT / "src/agents/data_analysis_agent/rag_impl/documentation/"
CACHED_DOCS_DIR  = ROOT / "cache"

SEED             = 623 ## note that the seed is only supported for OpenAI models
RECURSION_LIMIT  = 50
LOG_TO_TERMINAL  = True
LOG_TO_FILE      = None
