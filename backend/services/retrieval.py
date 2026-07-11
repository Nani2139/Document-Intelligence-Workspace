"""
Retrieval service with cluster-aware search, metadata filtering, and cross-encoder reranking.
"""
import logging
from typing import List, Optional, Dict, Tuple

import numpy as np
from sentence_transformers import CrossEncoder

from backend.config import (
    CHROMA_PATH,
    CHROMA_COLLECTION,
    EMBEDDING_MODEL,
    RERANKER_MODEL,
    TOP_K_INITIAL,
    TOP_K_RERANKED,
)
from backend.services.ingestion import get_or_create_collection, _get_embedding_fn

logger = logging.getLogger(__name__)

_reranker = None


def _get_reranker():
    global _reranker
    if _reranker is None:
        logger.info(f"Loading cross-encoder reranker: {RERANKER_MODEL}")
        _reranker = CrossEncoder(RERANKER_MODEL)
    return _reranker


def retrieve_chunks(
    query: str,
    collection_id: int,
    document_ids: Optional[List[int]] = None,
    cluster_ids: Optional[List[int]] = None,
    top_k_initial: int = TOP_K_INITIAL,
    top_k_reranked: int = TOP_K_RERANKED,
) -> List[Dict]:
    """
    Full retrieval pipeline:
    1. Build metadata filter (collection + optional doc/cluster filters)
    2. Semantic search in ChromaDB (top_k_initial)
    3. Cross-encoder rerank (top_k_reranked)

    Returns list of dicts with keys: id, text, metadata, rerank_score
    """
    collection = get_or_create_collection()

    # Build where filter
    where_filter = _build_where_filter(collection_id, document_ids, cluster_ids)

    # Semantic search - over-retrieve
    try:
        results = collection.query(
            query_texts=[query],
            n_results=top_k_initial,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.error(f"ChromaDB query failed: {e}")
        return []

    if not results["documents"] or not results["documents"][0]:
        return []

    candidates = []
    for i, (doc, meta, dist, cid) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
        results["ids"][0],
    )):
        candidates.append({
            "id": cid,
            "text": doc,
            "metadata": meta,
            "distance": dist,
        })

    if not candidates:
        return []

    # Cross-encoder reranking
    reranked = _rerank(query, candidates, top_k_reranked)
    return reranked


def retrieve_with_cluster_match(
    query: str,
    collection_id: int,
    cluster_centroids: List[Tuple[int, List[float]]],
    document_ids: Optional[List[int]] = None,
    top_k_initial: int = TOP_K_INITIAL,
    top_k_reranked: int = TOP_K_RERANKED,
    top_n_clusters: int = 2,
) -> List[Dict]:
    """
    Cluster-aware retrieval:
    1. Match query embedding to nearest cluster centroids
    2. Filter search to those clusters
    3. Semantic search + rerank
    """
    if not cluster_centroids:
        return retrieve_chunks(query, collection_id, document_ids, top_k_initial=top_k_initial, top_k_reranked=top_k_reranked)

    embedding_fn = _get_embedding_fn()
    query_embedding = embedding_fn([query])[0]
    query_vec = np.array(query_embedding)

    distances = []
    for cluster_id, centroid in cluster_centroids:
        centroid_vec = np.array(centroid)
        dist = np.linalg.norm(query_vec - centroid_vec)
        distances.append((cluster_id, dist))

    distances.sort(key=lambda x: x[1])
    matched_cluster_ids = [cid for cid, _ in distances[:top_n_clusters]]

    logger.info(f"Matched clusters: {matched_cluster_ids}")
    return retrieve_chunks(
        query, collection_id, document_ids, matched_cluster_ids,
        top_k_initial, top_k_reranked,
    )


def _build_where_filter(
    collection_id: int,
    document_ids: Optional[List[int]] = None,
    cluster_ids: Optional[List[int]] = None,
) -> dict:
    """Build ChromaDB where filter combining collection, document, and cluster constraints."""
    conditions = [{"collection_id": collection_id}]

    if document_ids:
        if len(document_ids) == 1:
            conditions.append({"document_id": document_ids[0]})
        else:
            conditions.append({"document_id": {"$in": document_ids}})

    if cluster_ids:
        if len(cluster_ids) == 1:
            conditions.append({"cluster_id": cluster_ids[0]})
        else:
            conditions.append({"cluster_id": {"$in": cluster_ids}})

    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _rerank(query: str, candidates: List[Dict], top_k: int) -> List[Dict]:
    """Rerank candidates using cross-encoder model."""
    if len(candidates) <= top_k:
        for c in candidates:
            c["rerank_score"] = 1.0 - c.get("distance", 0)
        return candidates

    reranker = _get_reranker()
    pairs = [(query, c["text"]) for c in candidates]

    try:
        scores = reranker.predict(pairs)
    except Exception as e:
        logger.warning(f"Reranking failed: {e}, returning top by distance")
        candidates.sort(key=lambda x: x.get("distance", float("inf")))
        for c in candidates[:top_k]:
            c["rerank_score"] = 1.0 - c.get("distance", 0)
        return candidates[:top_k]

    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = float(score)

    candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
    return candidates[:top_k]
