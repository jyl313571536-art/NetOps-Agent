"""API 请求模型。"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Agent 对话请求。"""

    message: str = Field(
        ..., min_length=1, max_length=4000, description="网络故障描述"
    )
    thread_id: str | None = Field(
        default=None, max_length=64, description="请求关联标识"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "message": "我的电脑可以 Ping 通网关，但是无法访问互联网",
                    "thread_id": "demo-001",
                }
            ]
        }
    }

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        """消息去除首尾空白后不能为空。"""
        stripped = value.strip()
        if not stripped:
            raise ValueError("message 不能为空")
        return stripped


class ToolRunRequest(BaseModel):
    """诊断工具执行请求（Web UI 用）。"""

    tool_name: str = Field(min_length=1, max_length=64, description="工具名")
    args: dict[str, Any] = Field(default_factory=dict, description="工具参数")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"tool_name": "ping_host", "args": {"host": "127.0.0.1", "count": 2}}
            ]
        }
    }


class KnowledgeSearchRequest(BaseModel):
    """知识库检索请求（Web UI 用）。"""

    query: str = Field(min_length=1, max_length=500, description="检索内容")
    top_k: int | None = Field(
        default=None, ge=1, le=20, description="返回条数，不填用配置默认值"
    )
