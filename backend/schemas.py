"""
Pydantic schemas for request/response validation.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


# ── Collections ────────────────────────────────────────────────

class CollectionCreate(BaseModel):
    name: str
    description: str = ""


class CollectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    created_at: datetime
    document_count: int = 0
    cluster_count: int = 0


# ── Documents ──────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    collection_id: int
    filename: str
    file_type: str
    status: str
    error_message: Optional[str] = None
    chunk_count: int
    metadata_: dict = {}
    uploaded_at: datetime


class DocumentStatusResponse(BaseModel):
    id: int
    filename: str
    status: str
    error_message: Optional[str] = None
    chunk_count: int


# ── Topic Clusters ─────────────────────────────────────────────

class TopicClusterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    collection_id: int
    label: str
    chunk_count: int
    created_at: datetime


# ── Chat ───────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: Optional[int] = None
    collection_id: int
    message: str
    document_ids: List[int] = []
    cluster_ids: List[int] = []


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    collection_id: int
    title: str
    created_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: str
    content: str
    metadata_: dict = {}
    created_at: datetime
