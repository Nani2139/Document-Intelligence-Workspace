"""
Topic clustering service.
Clusters document chunks by embedding similarity, then generates labels
using TF-IDF keyword extraction (fast, no LLM needed).
"""
import logging
import re
from collections import Counter
from typing import List, Tuple, Optional

import numpy as np

from backend.config import MIN_CHUNKS_FOR_CLUSTERING, MIN_CLUSTER_SIZE

logger = logging.getLogger(__name__)

# Common English stop words for keyword extraction
_STOP_WORDS = frozenset(
    "a an the and or but in on at to for of is it this that with from by as are was were be been "
    "being have has had do does did will would shall should can could may might must not no nor "
    "so if then than too very also just about above after again all am any because before between "
    "both but during each few further get got had has he her here hers herself him himself his how "
    "i its itself let me more most my myself now only other our ours ourselves out over own same "
    "she some such their theirs them themselves these they those through under until up we what "
    "when where which while who whom why you your yours yourself yourselves into".split()
)


def cluster_embeddings(
    embeddings: List[List[float]],
    chunk_ids: List[str],
) -> List[Tuple[int, List[str], List[float]]]:
    """
    Cluster embeddings using HDBSCAN (or KMeans fallback).

    Returns list of (cluster_label, [chunk_ids], centroid_vector) tuples.
    Noise points (label=-1) are assigned to nearest cluster.
    """
    if len(embeddings) < MIN_CHUNKS_FOR_CLUSTERING:
        logger.info(f"Too few chunks ({len(embeddings)}) for clustering, skipping")
        return []

    embeddings_array = np.array(embeddings)

    try:
        clusters = _hdbscan_cluster(embeddings_array)
    except Exception as e:
        logger.warning(f"HDBSCAN failed: {e}, falling back to KMeans")
        clusters = _kmeans_cluster(embeddings_array)

    # Group chunk_ids by cluster
    cluster_groups = {}
    for idx, label in enumerate(clusters):
        cluster_groups.setdefault(label, []).append(idx)

    # Assign noise points (-1) to nearest cluster
    if -1 in cluster_groups and len(cluster_groups) > 1:
        valid_labels = [l for l in cluster_groups if l != -1]
        centroids = {}
        for label in valid_labels:
            member_indices = cluster_groups[label]
            centroids[label] = np.mean(embeddings_array[member_indices], axis=0)

        for idx in cluster_groups[-1]:
            point = embeddings_array[idx]
            nearest = min(valid_labels, key=lambda l: np.linalg.norm(point - centroids[l]))
            cluster_groups[nearest].append(idx)

        del cluster_groups[-1]

    results = []
    for label, indices in sorted(cluster_groups.items()):
        member_ids = [chunk_ids[i] for i in indices]
        centroid = np.mean(embeddings_array[indices], axis=0).tolist()
        results.append((label, member_ids, centroid))

    return results


def _hdbscan_cluster(embeddings: np.ndarray) -> np.ndarray:
    """Cluster using HDBSCAN (auto-determines number of clusters)."""
    from sklearn.cluster import HDBSCAN

    clusterer = HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=2,
        metric="euclidean",
    )
    return clusterer.fit_predict(embeddings)


def _kmeans_cluster(embeddings: np.ndarray) -> np.ndarray:
    """Fallback: KMeans with heuristic K."""
    from sklearn.cluster import KMeans

    n_samples = len(embeddings)
    k = max(2, min(n_samples // 5, 10))

    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    return kmeans.fit_predict(embeddings)


def generate_cluster_label(sample_texts: List[str], all_texts: Optional[List[List[str]]] = None) -> str:
    """
    Generate a topic label from sample chunk texts using TF-IDF keyword extraction.
    No LLM call needed -- runs in <1ms.

    Args:
        sample_texts: Texts from the target cluster
        all_texts: Optional list of text lists from ALL clusters (for IDF weighting)
    """
    if not sample_texts:
        return "Unlabeled Topic"

    try:
        cluster_words = _extract_words(" ".join(t[:500] for t in sample_texts))
        if not cluster_words:
            return "Unlabeled Topic"

        cluster_tf = Counter(cluster_words)

        # If we have other clusters' texts, use TF-IDF to find distinctive words
        if all_texts and len(all_texts) > 1:
            doc_freq = Counter()
            for texts in all_texts:
                words_in_cluster = set(_extract_words(" ".join(t[:500] for t in texts)))
                for w in words_in_cluster:
                    doc_freq[w] += 1

            n_clusters = len(all_texts)
            scored = {}
            for word, tf in cluster_tf.items():
                df = doc_freq.get(word, 1)
                idf = np.log(n_clusters / df) + 1.0
                scored[word] = tf * idf

            top_words = sorted(scored, key=scored.get, reverse=True)[:4]
        else:
            top_words = [w for w, _ in cluster_tf.most_common(4)]

        label = " ".join(w.title() for w in top_words)
        return label[:60] if label else "Unlabeled Topic"

    except Exception as e:
        logger.warning(f"Keyword extraction failed: {e}")
        return "Unlabeled Topic"


def _extract_words(text: str) -> List[str]:
    """Extract meaningful words from text, filtering stop words and short tokens."""
    words = re.findall(r'[a-zA-Z]{3,}', text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) >= 3]
