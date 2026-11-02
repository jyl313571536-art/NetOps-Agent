"""FastAPI 文档接口集成测试。"""

from fastapi.testclient import TestClient

from app.main import create_app


def test_openapi_schema_available() -> None:
    """OpenAPI schema 可生成，含全部业务路径。"""
    client = TestClient(create_app())
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema["paths"]
    assert "/health" in paths
    assert "/api/v1/agent/providers" in paths
    assert "/api/v1/agent/chat" in paths


def test_openapi_metadata() -> None:
    """OpenAPI 元信息完整（标题、版本、描述）。"""
    client = TestClient(create_app())
    schema = client.get("/openapi.json").json()
    info = schema["info"]
    assert info["title"] == "NetOps Agent"
    assert info["version"]
    assert info["description"]


def test_openapi_request_example() -> None:
    """ChatRequest 在 schema 中带示例。"""
    client = TestClient(create_app())
    schema = client.get("/openapi.json").json()
    chat_schema = schema["components"]["schemas"]["ChatRequest"]
    examples = chat_schema.get("examples")
    assert examples
    assert "message" in examples[0]


def test_openapi_tags_documented() -> None:
    """接口标签带描述，文档中分组清晰。"""
    client = TestClient(create_app())
    schema = client.get("/openapi.json").json()
    tags = {t["name"]: t.get("description", "") for t in schema.get("tags", [])}
    assert "health" in tags
    assert "agent" in tags
    assert tags["agent"]


def test_docs_ui_available() -> None:
    """Swagger UI 与 ReDoc 页面可访问。"""
    client = TestClient(create_app())
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
