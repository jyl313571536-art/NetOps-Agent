"""网络工具封装与注册表单元测试。"""

from app.network.mock_adapter import MockNetworkAdapter
from app.tools.network_tools import TOOL_SPECS, NetworkTools
from app.tools.registry import ToolRegistry


def test_registry_has_eight_tools() -> None:
    """注册表包含 8 个诊断工具。"""
    registry = ToolRegistry(NetworkTools(mock_adapter=MockNetworkAdapter()))
    assert len(registry.names) == 8
    expected = {
        "ping_host",
        "dns_lookup",
        "traceroute_host",
        "check_tcp_port",
        "analyze_interface_status",
        "analyze_routing_table",
        "analyze_vlan_config",
        "analyze_network_logs",
    }
    assert set(registry.names) == expected


def test_tool_specs_mark_source_in_description() -> None:
    """每个工具描述都声明数据来源，避免结果混淆。"""
    for spec in TOOL_SPECS:
        assert (
            "simulation" in spec.description
            or "local_diagnostic" in spec.description
        )


def test_tool_specs_single_source() -> None:
    """工具元数据只有一份登记，字段完整。"""
    names = [spec.name for spec in TOOL_SPECS]
    assert len(names) == len(set(names))
    for spec in TOOL_SPECS:
        assert spec.args_schema is not None
        assert spec.source


def test_run_tool_dispatches_mock_analysis() -> None:
    """按名称分发到模拟设备分析。"""
    registry = ToolRegistry(NetworkTools(mock_adapter=MockNetworkAdapter()))
    result = registry.run_tool(
        "analyze_interface_status", {"device_id": "switch-01"}
    )
    assert result.success is True
    assert result.source.value == "simulation"


def test_run_tool_unknown_name() -> None:
    """未知工具返回失败结果。"""
    registry = ToolRegistry(NetworkTools(mock_adapter=MockNetworkAdapter()))
    result = registry.run_tool("not_a_tool", {})
    assert result.success is False
    assert result.error


def test_run_tool_invalid_args() -> None:
    """入参不符合 Schema 时返回失败结果，不抛异常。"""
    registry = ToolRegistry(NetworkTools(mock_adapter=MockNetworkAdapter()))
    result = registry.run_tool(
        "check_tcp_port", {"host": "127.0.0.1", "port": 99999}
    )
    assert result.success is False
    assert result.error


def test_as_langchain_tools_shape() -> None:
    """LangChain 工具对象具备名称与 Schema，且只构建一次。"""
    registry = ToolRegistry(NetworkTools(mock_adapter=MockNetworkAdapter()))
    tools = registry.as_langchain_tools()
    assert len(tools) == 8
    names = {t.name for t in tools}
    assert "ping_host" in names
    assert all(t.args_schema is not None for t in tools)
    assert registry.as_langchain_tools() is tools
