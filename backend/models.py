"""
SQLAlchemy models for Document Intelligence Workspace.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, JSON, ForeignKey, Float,
)
from sqlalchemy.orm import relationship

from backend.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow)

    documents = relationship("Document", back_populates="collection", cascade="all, delete-orphan")
    topic_clusters = relationship("TopicCluster", back_populates="collection", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="collection", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(512), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_path = Column(String(1024), nullable=False)
    status = Column(String(20), default="uploaded")  # uploaded|parsing|chunking|embedding|clustering|indexed|failed
    error_message = Column(Text, nullable=True)
    chunk_count = Column(Integer, default=0)
    metadata_ = Column("metadata", JSON, default=dict)  # page_count, file_size, etc.
    uploaded_at = Column(DateTime, default=_utcnow)

    collection = relationship("Collection", back_populates="documents")


class TopicCluster(Base):
    __tablename__ = "topic_clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    label = Column(String(255), nullable=False)
    centroid = Column(JSON, nullable=False)  # List[float] - mean embedding vector
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)

    collection = relationship("Collection", back_populates="topic_clusters")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collection_id = Column(Integer, ForeignKey("collections.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), default="New Chat")
    created_at = Column(DateTime, default=_utcnow)

    collection = relationship("Collection", back_populates="chat_sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)  # sources, trace, retries, confidence
    created_at = Column(DateTime, default=_utcnow)

    session = relationship("ChatSession", back_populates="messages")
