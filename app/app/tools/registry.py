"""工具注册表：向 Agent 层暴露工具定义与执行入口。

工具元数据的唯一来源是 app.tools.network_tools.TOOL_SPECS，
本模块只做派生（LangChain 工具绑定、名称列表、执行委托）。
"""

from typing import Any

from langchain_core.tools import StructuredTool

from app.network.base import ToolResult
from app.tools.network_tools import TOOL_SPECS, NetworkTools


class ToolRegistry:
    """工具注册表：统一执行入口 + LangChain 工具绑定。"""

    def __init__(self, tools: NetworkTools | None = None) -> None:
        self._tools = tools or NetworkTools()
        self._langchain_tools: list[StructuredTool] | None = None

    @property
    def names(self) -> list[str]:
        return [spec.name for spec in TOOL_SPECS]

    def run_tool(self, name: str, args: dict[str, Any]) -> ToolResult:
        """执行工具并返回结构化结果（未知工具由 NetworkTools 统一兜底）。"""
        return self._tools.run_tool(name, args)

    def as_langchain_tools(self) -> list[StructuredTool]:
        """构建供 LangGraph 绑定的 StructuredTool 列表（只构建一次）。"""
        if self._langchain_tools is None:
            self._langchain_tools = [
                StructuredTool.from_function(
                    func=self._make_handler(spec.name),
                    name=spec.name,
                    description=spec.description,
                    args_schema=spec.args_schema,
                )
                for spec in TOOL_SPECS
            ]
        return self._langchain_tools

    def _make_handler(self, name: str):
        """构造工具处理函数，把结构化结果序列化为 JSON 字符串。"""

        def handler(**kwargs: Any) -> dict[str, Any]:
            return self._tools.run_tool(name, kwargs).model_dump(mode="json")

        return handler


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """获取工具注册表单例（FastAPI 依赖注入入口）。"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
