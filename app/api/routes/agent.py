"""Agent 对话与配置查询路由。"""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agent.service import AgentService, get_agent_service
from app.api.schemas.request import ChatRequest
from app.api.schemas.response import ChatResponse, ProviderInfo
from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.get("/providers", response_model=ProviderInfo)
def get_providers() -> ProviderInfo:
    """查询当前模型配置状态，不返回 API Key 或其他敏感配置。"""
    settings = get_settings()
    return ProviderInfo(
        provider="Xiaomi MiMo",
        model=settings.mimo_model,
        base_url=settings.mimo_base_url,
        api_key_configured=bool(settings.mimo_api_key.strip()),
        timeout=settings.mimo_timeout,
    )


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    service: AgentService = Depends(get_agent_service),
) -> ChatResponse:
    """与 Agent 对话，获取初步故障分析。

    Phase 1 不执行网络诊断工具，诊断状态恒为 preliminary。
    """
    result = service.chat(message=payload.message, thread_id=payload.thread_id)
    return ChatResponse(
        success=True,
        thread_id=result.thread_id,
        diagnosis_id=result.diagnosis_id,
        answer=result.answer,
        diagnosis_status=result.diagnosis_status,
        executed_tools=result.executed_tools,
        tool_results=result.tool_results,
        next_steps=result.next_steps,
        citations=result.citations,
        report=result.report,
    )


@router.post("/chat/stream")
def chat_stream(
    payload: ChatRequest,
    service: AgentService = Depends(get_agent_service),
) -> StreamingResponse:
    """与 Agent 对话（SSE 流式）。

    按工作流节点推送进度事件，最后推送完整结果；
    事件格式：event: node|result|error，data 为 JSON。
    总耗时与 /chat 相同，流式只改善过程可见性。
    """
    logger.info("流式诊断开始, thread_id=%s", payload.thread_id)

    def generate():
        for event in service.chat_stream(
            message=payload.message, thread_id=payload.thread_id
        ):
            yield (
                f"event: {event['event']}\n"
                f"data: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
