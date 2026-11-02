"""FastAPI 接口集成测试（Phase 4）。"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.agent.service import get_agent_service
from app.core.exceptions import LLMConfigError
from app.main import create_app
from app.models.diagnosis import (
    AgentResult,
    DiagnosisReport,
    DiagnosisStatus,
    ToolRecord,
)


def _client_with_mock_service(mock_service: MagicMock) -> TestClient:
    """构造注入 Mock 服务的测试客户端。"""
    app = create_app()
    app.dependency_overrides[get_agent_service] = lambda: mock_service
    return TestClient(app)


def test_health() -> None:
    """健康检查正常。"""
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "NetOps Agent"


def test_providers_no_secret() -> None:
    """providers 接口不泄露 API Key。"""
    client = TestClient(create_app())
    resp = client.get("/api/v1/agent/providers")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "Xiaomi MiMo"
    assert body["api_key_configured"] in (True, False)
    assert "api_key" not in body
    assert "MIMO_API_KEY" not in resp.text


def test_chat_endpoint_full_report() -> None:
    """对话接口返回完整诊断结果（含报告与引用）。"""
    mock_service = MagicMock()
    mock_service.chat.return_value = AgentResult(
        thread_id="demo-001",
        diagnosis_id="abc123",
        answer="依据工具结果分析",
        diagnosis_status=DiagnosisStatus.SUSPECTED,
        executed_tools=["ping_host"],
        tool_results=[
            ToolRecord(
                tool_name="ping_host",
                args={"host": "127.0.0.1"},
                source="local_diagnostic",
                success=True,
                summary="可达",
            )
        ],
        next_steps=["检查 DNS 配置"],
        report=DiagnosisReport(
            issue_category="dns",
            summary="DNS 问题",
            unverified_points=["结论尚未被工具检测充分验证，标记为推测"],
        ),
    )
    client = _client_with_mock_service(mock_service)
    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "无法上网", "thread_id": "demo-001"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["diagnosis_id"] == "abc123"
    assert body["diagnosis_status"] == "suspected"
    assert body["executed_tools"] == ["ping_host"]
    assert body["report"]["issue_category"] == "dns"
    assert body["report"]["unverified_points"]


def test_chat_validation_error() -> None:
    """空消息返回 422。"""
    mock_service = MagicMock()
    client = _client_with_mock_service(mock_service)
    resp = client.post("/api/v1/agent/chat", json={"message": ""})
    assert resp.status_code == 422


def test_chat_llm_config_error() -> None:
    """模型配置错误返回安全的错误响应。"""
    mock_service = MagicMock()
    mock_service.chat.side_effect = LLMConfigError("sk-abcdef123456 未配置")
    client = _client_with_mock_service(mock_service)
    resp = client.post("/api/v1/agent/chat", json={"message": "无法上网"})
    assert resp.status_code == 503
    body = resp.json()
    assert body["success"] is False
    assert body["error_code"] == "llm_config_error"
    assert "sk-abcdef123456" not in resp.text
