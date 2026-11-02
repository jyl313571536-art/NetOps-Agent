"""全栈链路集成测试：API → Service → Graph → Mock 工具/知识 → SQLite。"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.agent.service import AgentService, get_agent_service
from app.main import create_app
from app.models.diagnosis import DiagnosisStatus
from app.rag.models import RetrievedChunk
from app.storage.sqlite import DiagnosisStorage


def _mock_llm():
    llm = MagicMock()
    llm.bind_tools.return_value = llm
    llm.invoke.side_effect = [
        AIMessage(content="dns"),
        AIMessage(
            content=(
                '工具：ping_host 参数:{"host": "127.0.0.1"} 理由：测连通性\n'
                '工具：ghost 参数:{"x": 1} 理由：应剔除'
            )
        ),
        AIMessage(content="[分析] DNS 问题\n[证据充分] 是"),
        AIMessage(content="结论：DNS 故障 [引用1]\n步骤：flushdns\n状态：suspected"),
    ]
    return llm


def _mock_registry():
    registry = MagicMock()
    registry.names = ["ping_host"]
    registry.run_tool.return_value = MagicMock(
        model_dump=MagicMock(
            return_value={
                "tool_name": "ping_host",
                "source": "local_diagnostic",
                "success": True,
                "summary": "可达",
                "detail": {},
                "error": None,
            }
        )
    )
    return registry


def _mock_rag():
    rag = MagicMock()
    rag.search.return_value = [
        RetrievedChunk(
            chunk_id="dns#0",
            source="dns_troubleshooting.md",
            content="DNS 故障排查先确认本机 DNS 配置。",
            score=0.9,
            chunk_index=0,
        )
    ]
    return rag


def test_full_stack_end_to_end(tmp_path) -> None:
    """HTTP 请求贯穿完整技术栈并落库。"""
    storage = DiagnosisStorage(str(tmp_path / "stack.db"))
    service = AgentService(
        llm=_mock_llm(),
        registry=_mock_registry(),
        rag_service=_mock_rag(),
        storage=storage,
    )
    app = create_app()
    app.dependency_overrides[get_agent_service] = lambda: service
    client = TestClient(app)

    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "无法访问互联网", "thread_id": "stack-001"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["thread_id"] == "stack-001"
    assert body["diagnosis_status"] == DiagnosisStatus.SUSPECTED.value
    assert body["executed_tools"] == ["ping_host"]
    assert body["citations"][0]["source"] == "dns_troubleshooting.md"
    assert body["citations"][0]["verified"] is True
    assert body["report"]["issue_category"] == "dns"
    assert body["report"]["unverified_points"]
    assert body["diagnosis_id"]
    assert storage.count() == 1


def test_full_stack_rejects_empty_message(tmp_path) -> None:
    """全栈路径下空消息被参数校验拦截。"""
    storage = DiagnosisStorage(str(tmp_path / "stack.db"))
    service = AgentService(
        llm=_mock_llm(),
        registry=_mock_registry(),
        rag_service=_mock_rag(),
        storage=storage,
    )
    app = create_app()
    app.dependency_overrides[get_agent_service] = lambda: service
    client = TestClient(app)
    resp = client.post("/api/v1/agent/chat", json={"message": "   "})
    assert resp.status_code == 422
    assert storage.count() == 0


def test_unexpected_exception_returns_safe_error() -> None:
    """未预期异常返回安全错误响应，不泄露内部细节。"""
    app = create_app()
    mock_service = MagicMock()
    mock_service.chat.side_effect = RuntimeError("internal secret path D:\\secret")
    app.dependency_overrides[get_agent_service] = lambda: mock_service
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/agent/chat", json={"message": "无法上网"})
    assert resp.status_code == 500
    body = resp.json()
    assert body["error_code"] == "internal_error"
    assert "secret" not in resp.text
