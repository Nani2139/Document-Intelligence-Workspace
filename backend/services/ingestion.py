"""
Ingestion pipeline orchestrator.
Coordinates: parallel parsing -> cleaning -> chunking -> batch embedding -> storage -> clustering.
"""
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from backend.config import (
    CHROMA_PATH,
    CHROMA_COLLECTION,
    EMBEDDING_MODEL,
    INGESTION_BATCH_SIZE,
    MAX_PARALLEL_PARSE,
)
from backend.services.parsing import parse_file, ParsedDocument
from backend.services.chunking import chunk_document, Chunk

logger = logging.getLogger(__name__)

_embedding_fn = None
_chroma_client = None


def _get_embedding_fn():
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    return _embedding_fn


def _get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _chroma_client


def get_or_create_collection():
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        embedding_function=_get_embedding_fn(),
    )


def parse_files_parallel(file_paths: Dict[int, str]) -> Dict[int, ParsedDocument]:
    """Parse multiple files in parallel using thread pool.

    Args:
        file_paths: {document_id: file_path}

    Returns:
        {document_id: ParsedDocument}
    """
    results = {}
    errors = {}

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_PARSE) as executor:
        future_to_doc_id = {
            executor.submit(parse_file, path): doc_id
            for doc_id, path in file_paths.items()
        }

        for future in as_completed(future_to_doc_id):
            doc_id = future_to_doc_id[future]
            try:
                results[doc_id] = future.result()
            except Exception as e:
                logger.error(f"Failed to parse document {doc_id}: {e}")
                errors[doc_id] = str(e)

    if errors:
        logger.warning(f"Parse errors: {errors}")

    return results, errors


def chunk_documents(
    parsed_docs: Dict[int, ParsedDocument],
    collection_id: int,
) -> Dict[int, List[Chunk]]:
    """Chunk all parsed documents."""
    all_chunks = {}
    for doc_id, parsed in parsed_docs.items():
        chunks = chunk_document(parsed, doc_id, collection_id)
        all_chunks[doc_id] = chunks
    return all_chunks


def embed_and_store(all_chunks: Dict[int, List[Chunk]]) -> Dict[int, List[str]]:
    """Batch embed all chunks and store in ChromaDB.

    Returns:
        {document_id: [chroma_ids]}
    """
    collection = get_or_create_collection()

    flat_chunks = []
    flat_doc_ids = []
    for doc_id, chunks in all_chunks.items():
        for chunk in chunks:
            flat_chunks.append(chunk)
            flat_doc_ids.append(doc_id)

    if not flat_chunks:
        return {}

    texts = [c.text for c in flat_chunks]
    metadatas = [c.metadata for c in flat_chunks]
    ids = [str(uuid.uuid4()) for _ in flat_chunks]

    # Batch insert
    for i in range(0, len(flat_chunks), INGESTION_BATCH_SIZE):
        end = min(i + INGESTION_BATCH_SIZE, len(flat_chunks))
        collection.add(
            documents=texts[i:end],
            metadatas=metadatas[i:end],
            ids=ids[i:end],
        )
        logger.info(f"Embedded batch {i // INGESTION_BATCH_SIZE + 1} ({end}/{len(flat_chunks)} chunks)")

    # Group IDs by document
    doc_chunk_ids = {}
    for idx, doc_id in enumerate(flat_doc_ids):
        doc_chunk_ids.setdefault(doc_id, []).append(ids[idx])

    return doc_chunk_ids


def get_chunk_embeddings(chunk_ids: List[str]) -> Dict[str, List[float]]:
    """Retrieve embeddings for given chunk IDs from ChromaDB."""
    collection = get_or_create_collection()

    if not chunk_ids:
        return {}

    result = collection.get(ids=chunk_ids, include=["embeddings"])
    embeddings = {}
    for cid, emb in zip(result["ids"], result["embeddings"]):
        embeddings[cid] = emb

    return embeddings


def get_chunk_texts(chunk_ids: List[str]) -> Dict[str, str]:
    """Retrieve text content for given chunk IDs."""
    collection = get_or_create_collection()

    if not chunk_ids:
        return {}

    result = collection.get(ids=chunk_ids, include=["documents"])
    texts = {}
    for cid, doc in zip(result["ids"], result["documents"]):
        texts[cid] = doc

    return texts


def delete_document_chunks(document_id: int):
    """Remove all chunks belonging to a document from ChromaDB."""
    collection = get_or_create_collection()
    try:
        collection.delete(where={"document_id": document_id})
    except Exception as e:
        logger.warning(f"Failed to delete chunks for document {document_id}: {e}")
