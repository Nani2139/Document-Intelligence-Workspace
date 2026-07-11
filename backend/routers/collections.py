"""
Collection CRUD endpoints.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Collection, Document, TopicCluster
from backend.schemas import CollectionCreate, CollectionResponse, TopicClusterResponse

router = APIRouter()


@router.post("", response_model=CollectionResponse, status_code=201)
async def create_collection(body: CollectionCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Collection).where(Collection.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Collection '{body.name}' already exists")

    collection = Collection(name=body.name, description=body.description)
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        created_at=collection.created_at,
        document_count=0,
        cluster_count=0,
    )


@router.get("", response_model=List[CollectionResponse])
async def list_collections(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Collection).order_by(Collection.created_at.desc()))
    collections = result.scalars().all()

    responses = []
    for c in collections:
        doc_count = await db.execute(
            select(func.count(Document.id)).where(Document.collection_id == c.id)
        )
        cluster_count = await db.execute(
            select(func.count(TopicCluster.id)).where(TopicCluster.collection_id == c.id)
        )
        responses.append(CollectionResponse(
            id=c.id,
            name=c.name,
            description=c.description,
            created_at=c.created_at,
            document_count=doc_count.scalar() or 0,
            cluster_count=cluster_count.scalar() or 0,
        ))
    return responses


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(collection_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(404, "Collection not found")

    doc_count = await db.execute(
        select(func.count(Document.id)).where(Document.collection_id == collection_id)
    )
    cluster_count = await db.execute(
        select(func.count(TopicCluster.id)).where(TopicCluster.collection_id == collection_id)
    )
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        created_at=collection.created_at,
        document_count=doc_count.scalar() or 0,
        cluster_count=cluster_count.scalar() or 0,
    )


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(collection_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Collection).where(Collection.id == collection_id))
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(404, "Collection not found")

    await db.delete(collection)
    await db.commit()


@router.get("/{collection_id}/clusters", response_model=List[TopicClusterResponse])
async def list_clusters(collection_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TopicCluster)
        .where(TopicCluster.collection_id == collection_id)
        .order_by(TopicCluster.chunk_count.desc())
    )
    return result.scalars().all()
