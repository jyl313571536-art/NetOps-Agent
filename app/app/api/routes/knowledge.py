"""知识库只读接口（Web UI 用）。

复用 RagService，不重复实现检索逻辑。
"""

import logging

from fastapi import APIRouter, Depends

from app.api.schemas.request import KnowledgeSearchRequest
from app.api.schemas.response import (
    KnowledgeHit,
    KnowledgeSearchResponse,
    KnowledgeStatusResponse,
)
from app.core.config import get_settings
from app.rag.service import RagService, get_rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


@router.get("/status", response_model=KnowledgeStatusResponse)
def knowledge_status(
    rag: RagService = Depends(get_rag_service),
) -> KnowledgeStatusResponse:
    """查询知识库索引状态。"""
    settings = get_settings()
    return KnowledgeStatusResponse(
        indexed_chunks=rag.count(), persist_dir=settings.rag_persist_dir
    )


@router.post("/search", response_model=KnowledgeSearchResponse)
def knowledge_search(
    payload: KnowledgeSearchRequest,
    rag: RagService = Depends(get_rag_service),
) -> KnowledgeSearchResponse:
    """按查询检索知识库片段，返回来源与相似度分数。"""
    logger.info("Web 知识检索: %s", payload.query[:50])
    chunks = rag.search(payload.query, top_k=payload.top_k)
    return KnowledgeSearchResponse(
        query=payload.query,
        hits=[
            KnowledgeHit(
                chunk_id=c.chunk_id,
                source=c.source,
                content=c.content,
                score=c.score,
                chunk_index=c.chunk_index,
            )
            for c in chunks
        ],
    )
