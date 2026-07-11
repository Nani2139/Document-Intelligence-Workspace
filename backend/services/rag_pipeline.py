"""
Corrective RAG pipeline using LangGraph.
Fully local: no web search, uses LM Studio for LLM.

Optimized flow (single LLM call for happy path):
  retrieve -> rerank -> score-based filter -> generate (streaming) -> END
  
Corrective path (if reranker scores are low):
  retrieve -> rerank -> scores too low -> rewrite_query -> re-retrieve -> generate -> END

The cross-encoder reranker handles relevance scoring, eliminating the need
for a separate LLM grading step. Hallucination checking uses a lightweight
score heuristic instead of an additional LLM call.
"""
import logging
from typing import List, TypedDict, Optional, Generator

from langchain_openai import ChatOpenAI

from backend.config import (
    LM_STUDIO_BASE_URL,
    LM_STUDIO_MODEL,
    ANSWER_TEMPERATURE,
    MIN_RELEVANT_CHUNKS,
    MAX_RETRIES,
)

logger = logging.getLogger(__name__)

# Reranker score threshold: chunks scoring above this are considered relevant.
# ms-marco-MiniLM-L-6-v2 scores range roughly from -10 to +10.
RERANKER_SCORE_THRESHOLD = 0.0

_answer_llm = None


def _get_answer_llm(streaming: bool = False):
    global _answer_llm
    if _answer_llm is None or _answer_llm.streaming != streaming:
        _answer_llm = ChatOpenAI(
            base_url=LM_STUDIO_BASE_URL,
            api_key="lm-studio",
            model=LM_STUDIO_MODEL,
            temperature=ANSWER_TEMPERATURE,
            request_timeout=180,
            max_retries=1,
            streaming=streaming,
        )
    return _answer_llm


class PipelineState(TypedDict):
    question: str
    original_question: str
    documents: List[dict]
    generation: str
    retry_count: int
    is_retry: bool
    decision_log: List[str]
    confidence: str
    sources: List[dict]


def _extract_sources(documents: List[dict]) -> List[dict]:
    sources = []
    for doc in documents:
        meta = doc.get("metadata", {})
        source = {
            "filename": meta.get("filename", "Unknown"),
            "page_number": meta.get("page_number", 0),
        }
        if source not in sources:
            sources.append(source)
    return sources


def _build_context(documents: List[dict], max_chars: int = 6000) -> str:
    parts = []
    total = 0
    for doc in documents:
        text = doc["text"]
        if total + len(text) > max_chars:
            remaining = max_chars - total
            if remaining > 200:
                parts.append(text[:remaining] + "...")
            break
        parts.append(text)
        total += len(text)
    return "\n\n---\n\n".join(parts)


def _build_prompt(question: str, context: str) -> str:
    return f"""Answer the question using ONLY the provided context. Be concise and direct.
If the context doesn't contain enough information, say so honestly.

Context:
{context}

Question: {question}

Answer:"""


# ── Score-based filtering (replaces LLM grading) ──────────────

def filter_by_reranker_score(chunks: List[dict]) -> List[dict]:
    """Keep chunks with reranker scores above threshold. No LLM call needed."""
    if not chunks:
        return []
    kept = [c for c in chunks if c.get("rerank_score", 0) > RERANKER_SCORE_THRESHOLD]
    if not kept:
        kept = chunks[:MIN_RELEVANT_CHUNKS]
        logger.info(f"[filter] All scores below threshold; keeping top {len(kept)} by rank")
    else:
        logger.info(f"[filter] Kept {len(kept)}/{len(chunks)} chunks by reranker score")
    return kept


def compute_confidence(chunks: List[dict]) -> str:
    """Derive confidence from reranker scores instead of an LLM hallucination check."""
    if not chunks:
        return "low"
    scores = [c.get("rerank_score", 0) for c in chunks]
    avg_score = sum(scores) / len(scores)
    top_score = max(scores)
    if top_score > 3.0 and avg_score > 1.0:
        return "high"
    if top_score > 1.0 or avg_score > 0.0:
        return "medium"
    return "low"


# ── Streaming pipeline (main path) ────────────────────────────

def run_pipeline_streaming(
    question: str,
    retrieved_chunks: List[dict],
    retrieve_fn=None,
) -> Generator:
    """
    Optimized pipeline that streams tokens directly.
    Yields dicts: {"type": "trace"|"token"|"sources"|"metadata"|"done", ...}

    Happy path (1 LLM call): filter -> stream generate -> done
    Corrective path (1 LLM call + rewrite): filter -> rewrite -> re-retrieve -> stream generate -> done
    """
    log = [f"Retrieved {len(retrieved_chunks)} chunks after reranking."]
    yield {"type": "trace", "message": log[-1]}

    # Score-based filtering instead of LLM grading
    filtered = filter_by_reranker_score(retrieved_chunks)
    scores_summary = ", ".join(f"{c.get('rerank_score', 0):.2f}" for c in retrieved_chunks[:5])
    log.append(f"Reranker scores: [{scores_summary}]. Kept {len(filtered)} chunks.")
    yield {"type": "trace", "message": log[-1]}

    # If too few relevant chunks, try rewriting (single attempt)
    if len(filtered) < MIN_RELEVANT_CHUNKS and retrieve_fn:
        yield {"type": "trace", "message": "Low relevance scores, rewriting query..."}
        try:
            llm = _get_answer_llm(streaming=False)
            response = llm.invoke(
                f"Rewrite this search query using different keywords:\n{question}\n\nRewritten query:"
            )
            new_q = response.content.strip().strip('"\'')
            if new_q and len(new_q) > 5:
                new_chunks = retrieve_fn(new_q)
                new_filtered = filter_by_reranker_score(new_chunks)
                if len(new_filtered) >= len(filtered):
                    filtered = new_filtered
                    question = new_q
                    log.append(f"Rewrote query: {new_q[:80]}")
                    log.append(f"Re-retrieved {len(new_filtered)} chunks.")
                    yield {"type": "trace", "message": log[-1]}
        except Exception as e:
            logger.warning(f"Rewrite failed: {e}, proceeding with original results")

    if not filtered:
        yield {"type": "token", "content": "I couldn't find relevant information in your documents for this question."}
        yield {"type": "sources", "sources": []}
        yield {"type": "metadata", "confidence": "low", "retries": 0}
        yield {"type": "done"}
        return

    sources = _extract_sources(filtered)
    confidence = compute_confidence(filtered)
    context = _build_context(filtered)
    prompt = _build_prompt(question, context)

    log.append("Generating answer...")
    yield {"type": "trace", "message": log[-1]}

    # Stream tokens from LLM
    full_answer = ""
    try:
        llm = _get_answer_llm(streaming=True)
        for chunk in llm.stream(prompt):
            token = chunk.content
            if token:
                full_answer += token
                yield {"type": "token", "content": token}
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        error_msg = "I encountered an error generating the answer. Please try again."
        yield {"type": "token", "content": error_msg}
        full_answer = error_msg

    log.append(f"Answer generated ({len(full_answer)} chars). Confidence: {confidence}.")
    yield {"type": "trace", "message": log[-1]}
    yield {"type": "sources", "sources": sources}
    yield {"type": "metadata", "confidence": confidence, "retries": 0, "trace": log}
    yield {"type": "done"}


# ── Non-streaming fallback (for testing / programmatic use) ───

def run_pipeline(
    question: str,
    retrieved_chunks: List[dict],
    retrieve_fn=None,
) -> dict:
    """Non-streaming wrapper: collects all events and returns a result dict."""
    result = {
        "generation": "",
        "sources": [],
        "confidence": "medium",
        "retry_count": 0,
        "decision_log": [],
    }

    for event in run_pipeline_streaming(question, retrieved_chunks, retrieve_fn):
        t = event["type"]
        if t == "trace":
            result["decision_log"].append(event["message"])
        elif t == "token":
            result["generation"] += event["content"]
        elif t == "sources":
            result["sources"] = event["sources"]
        elif t == "metadata":
            result["confidence"] = event.get("confidence", "medium")
            result["retry_count"] = event.get("retries", 0)

    return result
