"""FastAPI 应用入口。"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import agent, diagnostics, health, history, knowledge
from app.core.config import get_settings
from app.core.exceptions import NetOpsError, sanitize
from app.core.logging import setup_logging
from app.web.routes import mount_static
from app.web.routes import router as web_router

logger = logging.getLogger(__name__)


API_DESCRIPTION = """\
NetOps Agent：基于 Xiaomi MiMo + LangGraph + FastAPI 的智能网络运维与故障诊断 Agent。

## 功能

- 接收自然语言网络故障描述，执行完整诊断工作流：
  故障分类 → 诊断规划 → 多工具执行 → 知识检索 → 结果分析 → 故障报告。
- 诊断工具结果严格区分数据来源：
  `local_diagnostic`（本机真实检测）与 `simulation`（模拟设备虚构数据）。
- RAG 知识引用必须对应真实检索片段，编造引用会被剔除。
- 诊断状态：`preliminary` / `suspected` / `confirmed` / `failed`，按证据判定。

## 安全

- 网络诊断目标受白名单限制，默认只允许本机回环。
- 只读诊断策略，不执行任何配置变更操作。
- 诊断记录保存到本地 SQLite（不返回 API Key 等敏感配置）。
"""

TAGS_METADATA = [
    {
        "name": "health",
        "description": "服务健康检查",
    },
    {
        "name": "agent",
        "description": "Agent 故障诊断：对话诊断与模型配置状态查询",
    },
]


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=API_DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(health.router)
    app.include_router(agent.router)
    app.include_router(diagnostics.router)
    app.include_router(knowledge.router)
    app.include_router(history.router)
    app.include_router(web_router)
    mount_static(app)

    @app.exception_handler(NetOpsError)
    async def handle_netops_error(
        request: Request, exc: NetOpsError
    ) -> JSONResponse:
        """将领域异常转换为安全的错误响应，detail 只写日志。"""
        logger.error(
            "请求处理失败: code=%s detail=%s",
            exc.error_code,
            sanitize(exc.detail),
        )
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "success": False,
                "error_code": exc.error_code,
                "message": exc.safe_message,
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """兜底处理未预期异常，不向客户端泄露内部细节。"""
        logger.error("未预期的异常: %s", sanitize(str(exc)))
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error_code": "internal_error",
                "message": "服务器内部错误",
            },
        )

    return app


app = create_app()
