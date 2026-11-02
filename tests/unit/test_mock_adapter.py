"""模拟设备适配器单元测试。"""

from app.network.base import DataSource
from app.network.mock_adapter import MockNetworkAdapter


def test_analyze_interface_status() -> None:
    """读取模拟交换机接口状态，来源标记 simulation。"""
    adapter = MockNetworkAdapter()
    result = adapter.analyze_interface_status("switch-01")
    assert result.success is True
    assert result.source == DataSource.SIMULATION
    interfaces = result.detail["interfaces"]
    assert len(interfaces) == 4
    assert any(i["oper_status"] == "up" for i in interfaces)


def test_analyze_routing_table() -> None:
    """读取模拟路由器路由表。"""
    adapter = MockNetworkAdapter()
    result = adapter.analyze_routing_table("router-01")
    assert result.success is True
    assert result.source == DataSource.SIMULATION
    routes = result.detail["routes"]
    assert any(r["protocol"] == "static" for r in routes)
    assert any(r["protocol"] == "connected" for r in routes)


def test_analyze_vlan_config() -> None:
    """读取模拟交换机 VLAN 配置。"""
    adapter = MockNetworkAdapter()
    result = adapter.analyze_vlan_config("switch-01")
    assert result.success is True
    assert result.source == DataSource.SIMULATION
    vlans = result.detail["vlans"]
    assert any(v["name"] == "OFFICE" for v in vlans)


def test_analyze_network_logs() -> None:
    """读取模拟设备日志。"""
    adapter = MockNetworkAdapter()
    result = adapter.analyze_network_logs("switch-01")
    assert result.success is True
    assert result.source == DataSource.SIMULATION
    assert result.detail["logs"]


def test_analyze_network_logs_level_filter() -> None:
    """按级别过滤日志。"""
    adapter = MockNetworkAdapter()
    result = adapter.analyze_network_logs("router-01", level="ERROR")
    assert result.success is True
    assert result.detail["logs"]
    assert all(log["level"] == "ERROR" for log in result.detail["logs"])


def test_unknown_device_returns_failure() -> None:
    """不存在的设备返回失败结果，不抛异常。"""
    adapter = MockNetworkAdapter()
    result = adapter.analyze_interface_status("switch-999")
    assert result.success is False
    assert result.error


def test_device_id_path_traversal_blocked() -> None:
    """路径穿越设备 ID 被拒绝。"""
    adapter = MockNetworkAdapter()
    result = adapter.analyze_interface_status("../../etc/passwd")
    assert result.success is False
    assert result.error


def test_list_devices() -> None:
    """列出全部模拟设备。"""
    adapter = MockNetworkAdapter()
    devices = adapter.list_devices()
    ids = {d.device_id for d in devices}
    assert {"switch-01", "router-01", "firewall-01"} <= ids
