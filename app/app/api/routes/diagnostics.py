"""网络诊断只读接口（Web UI 用）。

复用 NetworkTools/ToolRegistry，不重复实现诊断逻辑。
"""

import logging

from fastapi import APIRouter, Depends

from app.api.schemas.request import ToolRunRequest
from app.api.schemas.response import ToolInfo, ToolRunResponse
from app.tools.network_tools import TOOL_SPECS
from app.tools.registry import ToolRegistry, get_tool_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/diagnostics", tags=["diagnostics"])


def _schema_fields(spec) -> list[dict]:
    """从 Pydantic Schema 提取表单字段描述。"""
    fields: list[dict] = []
    for name, field in spec.args_schema.model_fields.items():
        annotation = field.annotation
        kind = "string"
        if annotation is int:
            kind = "integer"
        elif annotation is float:
            kind = "number"
        elif annotation is bool:
            kind = "boolean"
        fields.append(
            {
                "name": name,
                "type": kind,
                "description": field.description or "",
                "required": field.is_required(),
                "default": (
                    None if field.is_required() else field.default
                ),
            }
        )
    return fields


@router.get("/tools", response_model=list[ToolInfo])
def list_tools() -> list[ToolInfo]:
    """列出可用诊断工具及其参数定义。"""
    return [
        ToolInfo(
            name=spec.name,
            description=spec.description,
            source=spec.source.value,
            fields=_schema_fields(spec),
        )
        for spec in TOOL_SPECS
    ]


@router.post("/run", response_model=ToolRunResponse)
def run_tool(
    payload: ToolRunRequest,
    registry: ToolRegistry = Depends(get_tool_registry),
) -> ToolRunResponse:
    """执行单个诊断工具，返回结构化结果。"""
    logger.info("Web 执行诊断工具: %s", payload.tool_name)
    result = registry.run_tool(payload.tool_name, payload.args)
    return ToolRunResponse(
        success=result.success,
        tool_name=result.tool_name,
        source=result.source.value
        if hasattr(result.source, "value")
        else str(result.source),
        summary=result.summary,
        detail=result.detail,
        error=result.error,
    )
