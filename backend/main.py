"""
Document Intelligence Workspace - FastAPI Application.
Fully local, zero-cost RAG system with document upload, topic clustering,
and corrective retrieval-augmented generation.
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s:    %(name)s - %(message)s")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import UPLOAD_DIR
from backend.database import init_db


def _preload_models():
    """Preload embedding and reranker models in a background thread so first query is fast."""
    import threading

    def _load():
        try:
            from backend.services.ingestion import _get_embedding_fn
            from backend.services.retrieval import _get_reranker
            logger = logging.getLogger(__name__)
            logger.info("Preloading embedding model...")
            _get_embedding_fn()
            logger.info("Preloading cross-encoder reranker...")
            _get_reranker()
            logger.info("Models preloaded successfully.")
        except Exception as e:
            logging.getLogger(__name__).warning(f"Model preload failed (will load on first use): {e}")

    threading.Thread(target=_load, daemon=True).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    await init_db()
    _preload_models()
    yield


app = FastAPI(
    title="Document Intelligence Workspace",
    description="Fully local, zero-cost document Q&A with corrective RAG",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: Allow frontend origins (configurable via CORS_ORIGINS env var)
cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,https://document-intelligence-workspace-plum.vercel.app"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Document Intelligence Workspace"}


# Router imports deferred to avoid circular imports during startup
from backend.routers import collections, documents, chat  # noqa: E402

app.include_router(collections.router, prefix="/api/collections", tags=["Collections"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
