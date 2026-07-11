"""
Background ingestion worker.
Orchestrates the full pipeline: parse -> chunk -> embed -> cluster -> label.
Runs as a FastAPI BackgroundTask.
"""
import asyncio
import json
import logging
from typing import List

import sqlalchemy

from backend.config import SQLITE_DB_PATH

logger = logging.getLogger(__name__)


def _get_sync_engine():
    return sqlalchemy.create_engine(f"sqlite:///{SQLITE_DB_PATH}")


def _update_doc_status(engine, doc_id: int, status: str, error: str = None, chunk_count: int = None, metadata: dict = None):
    """Update document status using sync SQLAlchemy."""
    with engine.begin() as conn:
        updates = ["status = :status"]
        params = {"status": status, "doc_id": doc_id}

        if error is not None:
            updates.append("error_message = :error")
            params["error"] = error

        if chunk_count is not None:
            updates.append("chunk_count = :chunk_count")
            params["chunk_count"] = chunk_count

        if metadata:
            existing = conn.execute(
                sqlalchemy.text("SELECT metadata FROM documents WHERE id = :doc_id"),
                {"doc_id": doc_id},
            ).fetchone()
            current = {}
            if existing and existing[0]:
                try:
                    current = json.loads(existing[0]) if isinstance(existing[0], str) else existing[0]
                except Exception:
                    pass
            current.update(metadata)
            updates.append("metadata = :metadata")
            params["metadata"] = json.dumps(current)

        sql = f"UPDATE documents SET {', '.join(updates)} WHERE id = :doc_id"
        conn.execute(sqlalchemy.text(sql), params)


def _run_sync_pipeline(document_ids: List[int], collection_id: int):
    """
    Synchronous ingestion pipeline. Runs in a thread to avoid blocking the event loop.
    All DB access is sync SQLAlchemy -- no asyncio needed.
    """
    from backend.services.ingestion import (
        parse_files_parallel, chunk_documents, embed_and_store,
        get_chunk_embeddings, get_chunk_texts,
    )
    from backend.services.clustering import cluster_embeddings

    engine = _get_sync_engine()

    # Gather file paths
    with engine.connect() as conn:
        placeholders = ", ".join(f":id_{i}" for i in range(len(document_ids)))
        params = {f"id_{i}": did for i, did in enumerate(document_ids)}
        rows = conn.execute(
            sqlalchemy.text(f"SELECT id, file_path FROM documents WHERE id IN ({placeholders})"),
            params,
        ).fetchall()

    file_paths = {row[0]: row[1] for row in rows}
    if not file_paths:
        logger.error("No documents found for ingestion")
        engine.dispose()
        return

    # Step 1: Parse files in parallel
    logger.info(f"[ingestion] Parsing {len(file_paths)} files...")
    for doc_id in file_paths:
        _update_doc_status(engine, doc_id, "parsing")

    parsed_docs, parse_errors = parse_files_parallel(file_paths)

    for doc_id, error in parse_errors.items():
        _update_doc_status(engine, doc_id, "failed", error=error)

    if not parsed_docs:
        logger.error("[ingestion] All files failed to parse")
        engine.dispose()
        return

    for doc_id, parsed in parsed_docs.items():
        _update_doc_status(engine, doc_id, "chunking", metadata={"page_count": parsed.page_count})

    # Step 2: Chunk documents
    logger.info(f"[ingestion] Chunking {len(parsed_docs)} documents...")
    all_chunks = chunk_documents(parsed_docs, collection_id)

    for doc_id in all_chunks:
        _update_doc_status(engine, doc_id, "embedding")

    # Step 3: Batch embed and store
    total_chunks = sum(len(c) for c in all_chunks.values())
    logger.info(f"[ingestion] Embedding {total_chunks} chunks...")
    doc_chunk_ids = embed_and_store(all_chunks)

    for doc_id, chunk_ids in doc_chunk_ids.items():
        _update_doc_status(engine, doc_id, "clustering", chunk_count=len(chunk_ids))

    # Step 4: Topic clustering
    all_chunk_ids = []
    for ids in doc_chunk_ids.values():
        all_chunk_ids.extend(ids)

    if all_chunk_ids:
        logger.info(f"[ingestion] Clustering {len(all_chunk_ids)} chunks...")
        embeddings_map = get_chunk_embeddings(all_chunk_ids)

        ordered_ids = list(embeddings_map.keys())
        ordered_embeddings = [embeddings_map[cid] for cid in ordered_ids]

        clusters = cluster_embeddings(ordered_embeddings, ordered_ids)

        if clusters:
            texts_map = get_chunk_texts(all_chunk_ids)
            _save_clusters(engine, clusters, texts_map, collection_id)

    # Step 5: Mark all as indexed
    for doc_id in doc_chunk_ids:
        _update_doc_status(engine, doc_id, "indexed")

    engine.dispose()
    logger.info(f"[ingestion] Complete. {total_chunks} chunks indexed, collection {collection_id}")


def _save_clusters(engine, clusters, texts_map, collection_id):
    """Save cluster info to SQLite and batch-update ChromaDB metadata."""
    from backend.services.ingestion import get_or_create_collection
    from backend.services.clustering import generate_cluster_label

    chroma_collection = get_or_create_collection()

    # Collect all cluster texts for TF-IDF across clusters
    all_cluster_texts = []
    for _, member_ids, _ in clusters:
        all_cluster_texts.append([texts_map.get(cid, "") for cid in member_ids[:10]])

    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.text("DELETE FROM topic_clusters WHERE collection_id = :cid"),
            {"cid": collection_id},
        )

        for idx, (cluster_label_num, member_ids, centroid) in enumerate(clusters):
            sample_texts = all_cluster_texts[idx][:5]
            label = generate_cluster_label(sample_texts, all_texts=all_cluster_texts)

            result = conn.execute(
                sqlalchemy.text(
                    "INSERT INTO topic_clusters (collection_id, label, centroid, chunk_count, created_at) "
                    "VALUES (:cid, :label, :centroid, :count, datetime('now'))"
                ),
                {
                    "cid": collection_id,
                    "label": label,
                    "centroid": json.dumps(centroid),
                    "count": len(member_ids),
                },
            )
            cluster_db_id = result.lastrowid

            # Batch update ChromaDB metadata for all chunks in this cluster
            batch_size = 100
            for i in range(0, len(member_ids), batch_size):
                batch_ids = member_ids[i:i + batch_size]
                try:
                    existing = chroma_collection.get(ids=batch_ids, include=["metadatas"])
                    if existing["metadatas"]:
                        updated_metas = []
                        for meta in existing["metadatas"]:
                            meta["cluster_id"] = cluster_db_id
                            updated_metas.append(meta)
                        chroma_collection.update(ids=batch_ids, metadatas=updated_metas)
                except Exception as e:
                    logger.warning(f"Batch ChromaDB update failed for cluster {cluster_db_id}: {e}")

    logger.info(f"[ingestion] Saved {len(clusters)} topic clusters")


async def run_ingestion(document_ids: List[int], collection_id: int):
    """
    Entry point for background ingestion.
    Runs the sync pipeline in a thread pool to avoid blocking.
    """
    logger.info(f"[ingestion] Starting for documents {document_ids} in collection {collection_id}")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_sync_pipeline, document_ids, collection_id)
