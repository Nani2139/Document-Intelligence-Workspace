"""
Chat endpoints with SSE streaming for answer generation.
"""
import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import ChatSession, Message, Collection, TopicCluster
from backend.schemas import ChatRequest, ChatSessionResponse, MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("")
async def chat(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Main chat endpoint. Runs the corrective RAG pipeline and streams the answer via SSE.

    SSE event types:
    - "trace": pipeline decision log entries
    - "token": streaming answer tokens
    - "sources": source documents cited
    - "metadata": confidence, retries, etc.
    - "done": signals completion
    - "error": error message
    """
    # Validate collection
    result = await db.execute(select(Collection).where(Collection.id == body.collection_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Collection not found")

    # Get or create chat session
    if body.session_id:
        result = await db.execute(select(ChatSession).where(ChatSession.id == body.session_id))
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(404, "Session not found")
    else:
        session = ChatSession(
            collection_id=body.collection_id,
            title=body.message[:50] + ("..." if len(body.message) > 50 else ""),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    # Save user message
    user_msg = Message(
        session_id=session.id,
        role="user",
        content=body.message,
    )
    db.add(user_msg)
    await db.commit()

    # Load cluster centroids if available
    cluster_centroids = []
    if not body.cluster_ids:
        clusters_result = await db.execute(
            select(TopicCluster).where(TopicCluster.collection_id == body.collection_id)
        )
        for cluster in clusters_result.scalars().all():
            try:
                centroid = json.loads(cluster.centroid) if isinstance(cluster.centroid, str) else cluster.centroid
                cluster_centroids.append((cluster.id, centroid))
            except Exception:
                pass

    return StreamingResponse(
        _stream_rag_response(
            question=body.message,
            collection_id=body.collection_id,
            session_id=session.id,
            document_ids=body.document_ids or None,
            cluster_ids=body.cluster_ids or None,
            cluster_centroids=cluster_centroids,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-Id": str(session.id),
        },
    )


async def _stream_rag_response(
    question: str,
    collection_id: int,
    session_id: int,
    document_ids: Optional[list] = None,
    cluster_ids: Optional[list] = None,
    cluster_centroids: list = None,
):
    """Generator that runs the RAG pipeline with true token streaming via SSE."""
    import asyncio
    import queue
    import threading

    def _sse_event(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    try:
        yield _sse_event("trace", {"message": "Starting retrieval..."})

        loop = asyncio.get_event_loop()

        def _do_retrieval(q):
            from backend.services.retrieval import retrieve_chunks, retrieve_with_cluster_match
            if cluster_centroids and not cluster_ids:
                return retrieve_with_cluster_match(
                    q, collection_id, cluster_centroids, document_ids,
                )
            else:
                return retrieve_chunks(
                    q, collection_id, document_ids, cluster_ids,
                )

        chunks = await loop.run_in_executor(None, _do_retrieval, question)

        if not chunks:
            yield _sse_event("token", {"content": "I couldn't find any relevant information in your documents for this question."})
            yield _sse_event("metadata", {"confidence": "low", "retries": 0})
            yield _sse_event("done", {})
            await _save_assistant_message(
                session_id,
                "I couldn't find any relevant information in your documents for this question.",
                {"confidence": "low", "retries": 0, "sources": [], "trace": ["No relevant chunks found."]},
            )
            return

        # Run streaming pipeline in a thread, relay events via a queue
        from backend.services.rag_pipeline import run_pipeline_streaming

        event_queue = queue.Queue()
        _SENTINEL = object()

        def _run_streaming():
            try:
                for event in run_pipeline_streaming(question, chunks, _do_retrieval):
                    event_queue.put(event)
            except Exception as e:
                event_queue.put({"type": "error", "message": str(e)})
            finally:
                event_queue.put(_SENTINEL)

        thread = threading.Thread(target=_run_streaming, daemon=True)
        thread.start()

        full_answer = ""
        sources = []
        metadata = {}
        trace = []

        while True:
            try:
                event = await loop.run_in_executor(None, event_queue.get, True, 0.1)
            except queue.Empty:
                continue

            if event is _SENTINEL:
                break

            t = event["type"]
            if t == "trace":
                trace.append(event["message"])
                yield _sse_event("trace", {"message": event["message"]})
            elif t == "token":
                full_answer += event["content"]
                yield _sse_event("token", {"content": event["content"]})
            elif t == "sources":
                sources = event["sources"]
                yield _sse_event("sources", {"sources": sources})
            elif t == "metadata":
                metadata = event
                yield _sse_event("metadata", {
                    "confidence": event.get("confidence", "medium"),
                    "retries": event.get("retries", 0),
                })
            elif t == "error":
                yield _sse_event("error", {"message": event["message"]})
            elif t == "done":
                yield _sse_event("done", {})

        thread.join(timeout=2)

        await _save_assistant_message(
            session_id,
            full_answer,
            {
                "confidence": metadata.get("confidence", "medium"),
                "retries": metadata.get("retries", 0),
                "sources": sources,
                "trace": trace,
            },
        )

    except Exception as e:
        logger.error(f"Chat pipeline error: {e}", exc_info=True)
        yield _sse_event("error", {"message": str(e)})
        yield _sse_event("done", {})


async def _save_assistant_message(session_id: int, content: str, metadata: dict):
    """Save the assistant's response to the database."""
    from backend.database import async_session
    async with async_session() as db:
        msg = Message(
            session_id=session_id,
            role="assistant",
            content=content,
            metadata_=metadata,
        )
        db.add(msg)
        await db.commit()


@router.get("/sessions", response_model=List[ChatSessionResponse])
async def list_sessions(
    collection_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(ChatSession).order_by(ChatSession.created_at.desc())
    if collection_id is not None:
        query = query.where(ChatSession.collection_id == collection_id)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Session not found")

    messages = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    return messages.scalars().all()


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")

    await db.delete(session)
    await db.commit()
