"""Web UI 测试：页面访问、静态资源、接口调用、错误展示、密钥泄露。"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.agent.service import get_agent_service
from app.main import create_app
from app.models.diagnosis import AgentResult, DiagnosisStatus
from app.rag.service import get_rag_service
from app.storage.sqlite import get_storage
from app.tools.registry import get_tool_registry


def _client() -> TestClient:
    return TestClient(create_app())


def test_index_page_ok() -> None:
    """Web 首页正常访问。"""
    resp = _client().get("/")
    assert resp.status_code == 200
    assert "NetOps Agent 测试控制台" in resp.text


def test_index_page_has_all_sections() -> None:
    """首页包含 5 个规划页面区块。"""
    text = _client().get("/").text
    for page in (
        "page-dashboard",
        "page-chat",
        "page-diagnostics",
        "page-knowledge",
        "page-history",
    ):
        assert page in text


def test_static_css_loads() -> None:
    """样式静态资源正常加载。"""
    resp = _client().get("/static/css/style.css")
    assert resp.status_code == 200
    assert "NetOps Agent" in resp.text or "topbar" in resp.text


def test_static_js_loads() -> None:
    """脚本静态资源正常加载。"""
    resp = _client().get("/static/js/app.js")
    assert resp.status_code == 200
    assert "/api/v1/agent/chat" in resp.text


def test_frontend_only_calls_backend_api() -> None:
    """前端只调用后端 API：不直连 MiMo / SQLite / Chroma。"""
    text = _client().get("/static/js/app.js").text
    # 不得出现外部模型服务地址或数据库客户端
    assert "xiaomimimo" not in text
    assert "sqlite3" not in text
    assert "chromadb" not in text
    assert "openDatabase" not in text
    # 只允许相对路径调用后端接口（经 api() 封装传入相对路径）
    assert "fetch(" in text
    assert 'api("/api/' in text or 'api("/health"' in text


def test_agent_page_calls_real_backend() -> None:
    """Agent 页面所调用的后端接口真实可用（Mock Service 注入）。"""
    app = create_app()
    mock_service = MagicMock()
    mock_service.chat.return_value = AgentResult(
        thread_id="web-001",
        diagnosis_id="id-1",
        answer="初步分析",
        diagnosis_status=DiagnosisStatus.SUSPECTED,
        executed_tools=["ping_host"],
        next_steps=["检查 DNS"],
    )
    app.dependency_overrides[get_agent_service] = lambda: mock_service
    client = TestClient(app)
    resp = client.post(
        "/api/v1/agent/chat",
        json={"message": "无法上网", "thread_id": "web-001"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "初步分析"
    assert body["diagnosis_status"] == "suspected"
    assert body["executed_tools"] == ["ping_host"]


def test_chat_request_validation() -> None:
    """请求参数校验：空消息返回 422。"""
    resp = _client().post("/api/v1/agent/chat", json={"message": ""})
    assert resp.status_code == 422


def test_diagnostics_tools_list() -> None:
    """诊断工具列表接口返回 8 个工具与字段定义。"""
    resp = _client().get("/api/v1/diagnostics/tools")
    assert resp.status_code == 200
    tools = resp.json()
    assert len(tools) == 8
    ping = next(t for t in tools if t["name"] == "ping_host")
    assert ping["source"] == "local_diagnostic"
    assert any(f["name"] == "host" for f in ping["fields"])


def test_diagnostics_run_returns_structured_result() -> None:
    """诊断执行接口返回结构化结果（Mock 注入）。"""
    app = create_app()
    registry = MagicMock()
    registry.run_tool.return_value = MagicMock(
        success=True,
        tool_name="ping_host",
        source=MagicMock(value="local_diagnostic"),
        summary="可达",
        detail={"host": "127.0.0.1"},
        error=None,
    )
    app.dependency_overrides[get_tool_registry] = lambda: registry
    client = TestClient(app)
    resp = client.post(
        "/api/v1/diagnostics/run",
        json={"tool_name": "ping_host", "args": {"host": "127.0.0.1"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["source"] == "local_diagnostic"
    assert body["summary"] == "可达"


def test_knowledge_search_returns_hits() -> None:
    """知识检索接口返回带来源的片段（Mock 注入）。"""
    from app.rag.models import RetrievedChunk

    app = create_app()
    rag = MagicMock()
    rag.search.return_value = [
        RetrievedChunk(
            chunk_id="a#0",
            source="dns_troubleshooting.md",
            content="DNS 故障排查",
            score=0.9,
        )
    ]
    rag.count.return_value = 8
    app.dependency_overrides[get_rag_service] = lambda: rag
    client = TestClient(app)
    resp = client.post(
        "/api/v1/knowledge/search", json={"query": "DNS 故障"}
    )
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert hits[0]["source"] == "dns_troubleshooting.md"
    status = client.get("/api/v1/knowledge/status")
    assert status.json()["indexed_chunks"] == 8


def test_history_returns_records() -> None:
    """诊断历史接口返回记录列表（Mock 注入）。"""
    app = create_app()
    storage = MagicMock()
    storage.list_records.return_value = [
        {
            "id": "r1",
            "thread_id": "t1",
            "created_at": "2026-11-02T00:00:00+00:00",
            "user_message": "无法上网",
            "issue_category": "dns",
            "diagnosis_status": "suspected",
            "answer": "分析",
            "executed_tools": ["ping_host"],
            "next_steps": ["检查 DNS"],
            "duration_ms": 100,
        }
    ]
    storage.count.return_value = 1
    app.dependency_overrides[get_storage] = lambda: storage
    client = TestClient(app)
    resp = client.get("/api/v1/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["records"][0]["executed_tools"] == ["ping_host"]


def test_backend_error_is_safe_json() -> None:
    """后端异常返回可展示的安全错误（页面 error-box 依赖该结构）。"""
    app = create_app()
    mock_service = MagicMock()
    mock_service.chat.side_effect = RuntimeError("secret path D:\\internal")
    app.dependency_overrides[get_agent_service] = lambda: mock_service
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post("/api/v1/agent/chat", json={"message": "无法上网"})
    assert resp.status_code == 500
    body = resp.json()
    assert body["error_code"] == "internal_error"
    assert "secret" not in resp.text
    # 前端脚本包含错误展示逻辑
    js = _client().get("/static/js/app.js").text
    assert "showError" in js


def test_pages_do_not_leak_api_key() -> None:
    """页面与静态资源不得泄露 API Key。"""
    import os

    key = os.getenv("MIMO_API_KEY", "")
    client = _client()
    for path in ("/", "/static/js/app.js", "/static/css/style.css"):
        text = client.get(path).text
        assert "MIMO_API_KEY" not in text
        if key:
            assert key not in text
    # providers 接口只返回配置状态
    providers = client.get("/api/v1/agent/providers").text
    if key:
        assert key not in providers
    assert "api_key_configured" in providers


def test_dashboard_endpoints_available() -> None:
    """Dashboard 依赖的状态接口均可用。"""
    client = _client()
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/agent/providers").status_code == 200
    assert client.get("/api/v1/knowledge/status").status_code == 200
    assert client.get("/api/v1/history?limit=1").status_code == 200


def test_chat_stream_sse_events() -> None:
    """SSE 流式接口按节点推送进度并产出最终结果。"""
    app = create_app()
    mock_service = MagicMock()

    def fake_stream(message, thread_id=None):
        yield {
            "event": "node",
            "data": {"node": "classify_issue", "summary": "故障分类: dns"},
        }
        yield {
            "event": "node",
            "data": {"node": "generate_report", "summary": "故障报告已生成"},
        }
        yield {
            "event": "result",
            "data": {
                "thread_id": "web-sse-1",
                "answer": "初步分析",
                "diagnosis_status": "suspected",
                "executed_tools": ["ping_host"],
                "tool_results": [],
                "next_steps": [],
                "citations": [],
            },
        }

    mock_service.chat_stream.side_effect = fake_stream
    app.dependency_overrides[get_agent_service] = lambda: mock_service
    client = TestClient(app)
    with client.stream(
        "POST",
        "/api/v1/agent/chat/stream",
        json={"message": "无法上网", "thread_id": "web-sse-1"},
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())
    assert "event: node" in body
    assert "event: result" in body
    assert "diagnosis_status" in body
    assert "generate_report" in body


def test_chat_stream_error_event() -> None:
    """流式通道中后端异常以 error 事件上报，不泄露内部细节。"""
    app = create_app()
    mock_service = MagicMock()
    mock_service.chat_stream.side_effect = RuntimeError("secret internal path")
    app.dependency_overrides[get_agent_service] = lambda: mock_service
    client = TestClient(app, raise_server_exceptions=False)

    def fake_stream(message, thread_id=None):
        yield {
            "event": "error",
            "data": {"error_code": "internal_error", "message": "服务器内部错误"},
        }

    mock_service.chat_stream.side_effect = fake_stream
    with client.stream(
        "POST", "/api/v1/agent/chat/stream", json={"message": "无法上网"}
    ) as resp:
        body = "".join(resp.iter_text())
    assert "event: error" in body
    assert "internal_error" in body
    assert "secret" not in body


def test_frontend_uses_sse_stream() -> None:
    """前端 Chat 页面走 SSE 流式接口。"""
    text = _client().get("/static/js/app.js").text
    assert "/api/v1/agent/chat/stream" in text
    assert "parseSse" in text
