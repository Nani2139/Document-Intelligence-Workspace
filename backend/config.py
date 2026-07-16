"""
Configuration for Document Intelligence Workspace.

Supports both local (LM Studio) and cloud (Groq, OpenAI) LLM providers.

Environment variables:
- LLM_BASE_URL: LLM API endpoint (default: http://127.0.0.1:1234/v1 for LM Studio)
- LLM_API_KEY: API key for cloud providers (default: "lm-studio" for local)
- LLM_MODEL: Model identifier (default: llama-3.1-8b-instant for Groq)
- CHROMA_PATH: Path to ChromaDB persistent storage
- UPLOAD_DIR: Path to store uploaded files
"""
import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))
CHROMA_PATH = os.getenv("CHROMA_PATH", str(BASE_DIR / "chroma_db"))
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "workspace.db"))

# ── LLM Configuration ─────────────────────────────────────────
# Supports: LM Studio (local), Groq (free cloud), OpenAI, etc.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://127.0.0.1:1234/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "lm-studio")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

# Legacy aliases for backward compatibility
LM_STUDIO_BASE_URL = LLM_BASE_URL
LM_STUDIO_MODEL = LLM_MODEL

GRADE_TEMPERATURE = 0.0
ANSWER_TEMPERATURE = 0.5

# ── Embedding model (local, free) ─────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ── Cross-encoder reranker (local, free) ───────────────────────
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# ── Chunking ───────────────────────────────────────────────────
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# ── Retrieval ──────────────────────────────────────────────────
TOP_K_INITIAL = 20      # Over-retrieve from ChromaDB
TOP_K_RERANKED = 5      # Keep after cross-encoder reranking
MIN_RELEVANT_CHUNKS = 2 # Minimum chunks to proceed to generation

# ── Corrective RAG ─────────────────────────────────────────────
MAX_RETRIES = 1         # Max retries before returning best-effort answer

# ── Ingestion ──────────────────────────────────────────────────
CHROMA_COLLECTION = "documents"
INGESTION_BATCH_SIZE = 50
MAX_PARALLEL_PARSE = 8  # Max concurrent file parsing threads

# ── Clustering ─────────────────────────────────────────────────
MIN_CHUNKS_FOR_CLUSTERING = 10  # Don't cluster if fewer chunks
MIN_CLUSTER_SIZE = 3            # HDBSCAN min_cluster_size
