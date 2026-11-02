"""诊断历史只读接口（Web UI 用）。

复用 DiagnosisStorage，不重复实现存储逻辑。
"""

import logging

from fastapi import APIRouter, Depends, Query

from app.api.schemas.response import HistoryRecord, HistoryResponse
from app.storage.sqlite import DiagnosisStorage, get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("", response_model=HistoryResponse)
def list_history(
    limit: int = Query(default=20, ge=1, le=200, description="返回条数"),
    storage: DiagnosisStorage = Depends(get_storage),
) -> HistoryResponse:
    """按时间倒序返回诊断历史记录摘要。"""
    logger.info("Web 查询诊断历史, limit=%s", limit)
    rows = storage.list_records(limit=limit)
    return HistoryResponse(
        total=storage.count(),
        records=[HistoryRecord(**row) for row in rows],
    )
