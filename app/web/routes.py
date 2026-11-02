"""Web 页面路由。

只负责页面与静态资源路由，业务数据一律通过 /api/v1 接口获取。
前端不直接调用 MiMo、SQLite、Chroma。
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

router = APIRouter(tags=["web"])


@router.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Web 测试控制台首页（单页应用，无模板渲染依赖）。"""
    return FileResponse(TEMPLATES_DIR / "index.html")


def mount_static(app) -> None:
    """挂载静态资源目录到 /static。"""
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
