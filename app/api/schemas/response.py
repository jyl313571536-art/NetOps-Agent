"""API 响应模型。"""

from pydantic import BaseModel, Field

from app.models.diagnosis import (
    Citation,
    DiagnosisReport,
    DiagnosisStatus,
    ToolRecord,
)


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str = "ok"
    app: str
    version: str


class ProviderInfo(BaseModel):
    """模型配置状态，不包含任何密钥。"""

    provider: str = "Xiaomi MiMo"
    model: str
    base_url: str
    api_key_configured: bool
    timeout: int


class ChatResponse(BaseModel):
    """Agent 对话响应。"""

    success: bool = True
    thread_id: str
    diagnosis_id: str = ""
    answer: str
    diagnosis_status: DiagnosisStatus
    executed_tools: list[str] = Field(default_factory=list)
    tool_results: list[ToolRecord] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    report: DiagnosisReport | None = None


class ErrorResponse(BaseModel):
    """统一错误响应。"""

    success: bool = False
    error_code: str
    message: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": False,
                    "error_code": "llm_timeout",
                    "message": "模型服务请求超时，请稍后重试",
                }
            ]
        }
    }


class ToolInfo(BaseModel):
    """诊断工具定义（Web UI 动态表单用）。"""

    name: str
    description: str
    source: str
    fields: list[dict] = Field(default_factory=list)


class ToolRunResponse(BaseModel):
    """诊断工具执行结果。"""

    success: bool
    tool_name: str
    source: str
    summary: str
    detail: dict = Field(default_factory=dict)
    error: str | None = None


class KnowledgeStatusResponse(BaseModel):
    """知识库状态。"""

    indexed_chunks: int
    persist_dir: str


class KnowledgeHit(BaseModel):
    """知识检索命中片段。"""

    chunk_id: str
    source: str
    content: str
    score: float
    chunk_index: int = 0


class KnowledgeSearchResponse(BaseModel):
    """知识检索结果。"""

    query: str
    hits: list[KnowledgeHit] = Field(default_factory=list)


class HistoryRecord(BaseModel):
    """诊断历史记录摘要。"""

    id: str
    thread_id: str
    created_at: str
    user_message: str
    issue_category: str
    diagnosis_status: str
    answer: str
    executed_tools: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    duration_ms: int = 0


class HistoryResponse(BaseModel):
    """诊断历史列表。"""

    total: int
    records: list[HistoryRecord] = Field(default_factory=list)


class DashboardStatus(BaseModel):
    """Dashboard 状态汇总。"""

    api_status: str
    app_name: str
    app_version: str
    model: str
    api_key_configured: bool
    rag_chunks: int
    history_total: int
