"""
Document upload, listing, status, and deletion endpoints.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import UPLOAD_DIR
from backend.database import get_db
from backend.models import Document, Collection
from backend.schemas import DocumentResponse, DocumentStatusResponse

router = APIRouter()

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx"}


@router.post("/upload", response_model=list[DocumentStatusResponse])
async def upload_documents(
    background_tasks: BackgroundTasks,
    collection_id: int = Form(...),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Collection not found")

    collection_dir = Path(UPLOAD_DIR) / str(collection_id)
    collection_dir.mkdir(parents=True, exist_ok=True)

    documents = []
    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(400, f"Unsupported file type: {ext}. Supported: {SUPPORTED_EXTENSIONS}")

        unique_name = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = collection_dir / unique_name

        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        doc = Document(
            collection_id=collection_id,
            filename=file.filename,
            file_type=ext.lstrip("."),
            file_path=str(file_path),
            status="uploaded",
            metadata_={"file_size": len(content)},
        )
        db.add(doc)
        documents.append(doc)

    await db.commit()
    for doc in documents:
        await db.refresh(doc)

    # Kick off background ingestion
    from backend.workers.ingestion_worker import run_ingestion
    background_tasks.add_task(run_ingestion, [doc.id for doc in documents], collection_id)

    return [
        DocumentStatusResponse(
            id=doc.id,
            filename=doc.filename,
            status=doc.status,
            error_message=doc.error_message,
            chunk_count=doc.chunk_count,
        )
        for doc in documents
    ]


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    collection_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Document).order_by(Document.uploaded_at.desc())
    if collection_id is not None:
        query = query.where(Document.collection_id == collection_id)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(document_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    return DocumentStatusResponse(
        id=doc.id,
        filename=doc.filename,
        status=doc.status,
        error_message=doc.error_message,
        chunk_count=doc.chunk_count,
    )


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document not found")

    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    try:
        from backend.services.ingestion import delete_document_chunks
        delete_document_chunks(document_id)
    except Exception:
        pass

    await db.delete(doc)
    await db.commit()
