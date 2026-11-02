"""API Schema 单元测试。"""

import pytest
from pydantic import ValidationError

from app.api.schemas.request import ChatRequest
from app.api.schemas.response import ChatResponse, ErrorResponse
from app.models.diagnosis import DiagnosisStatus


def test_chat_request_valid() -> None:
    """正常请求通过校验。"""
    req = ChatRequest(message="无法上网", thread_id="t1")
    assert req.thread_id == "t1"
    req_auto = ChatRequest(message="无法上网")
    assert req_auto.thread_id is None


def test_chat_request_rejects_empty_message() -> None:
    """空消息与纯空白消息被拒绝。"""
    with pytest.raises(ValidationError):
        ChatRequest(message="")
    with pytest.raises(ValidationError):
        ChatRequest(message="   ")


def test_chat_response_serializes_status() -> None:
    """诊断状态序列化为字符串。"""
    resp = ChatResponse(
        thread_id="t1",
        answer="初步分析",
        diagnosis_status=DiagnosisStatus.PRELIMINARY,
    )
    assert resp.model_dump()["diagnosis_status"] == "preliminary"


def test_error_response_shape() -> None:
    """错误响应默认 success 为 False。"""
    resp = ErrorResponse(error_code="llm_timeout", message="超时")
    assert resp.success is False
