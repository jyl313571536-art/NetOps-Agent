"""本机诊断适配器单元测试（只测本机回环，离线安全）。"""

import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.network.base import DataSource
from app.network.local_adapter import LocalNetworkAdapter

LOOPBACK = ["localhost", "127.0.0.1", "::1"]


@pytest.fixture
def adapter() -> LocalNetworkAdapter:
    return LocalNetworkAdapter(allowed_targets=LOOPBACK, timeout=5.0)


def test_ping_localhost(adapter: LocalNetworkAdapter) -> None:
    """Ping 本机回环应成功，来源标记为 local_diagnostic。"""
    result = adapter.ping("127.0.0.1", count=1)
    assert result.source == DataSource.LOCAL_DIAGNOSTIC
    assert result.success is True
    assert result.tool_name == "ping_host"


def test_ping_denies_external_target(adapter: LocalNetworkAdapter) -> None:
    """白名单外目标必须被拒绝，不得执行命令。"""
    result = adapter.ping("8.8.8.8", count=1)
    assert result.success is False
    assert result.error
    assert "白名单" in result.error or "允许" in result.error


def test_dns_lookup_localhost(adapter: LocalNetworkAdapter) -> None:
    """DNS 解析本机回环。"""
    result = adapter.dns_lookup("localhost")
    assert result.success is True
    assert result.detail["addresses"]


def test_dns_lookup_invalid_host(adapter: LocalNetworkAdapter) -> None:
    """非法主机名被拒绝。"""
    result = adapter.dns_lookup("bad host;rm")
    assert result.success is False
    assert result.error


def test_check_tcp_port_open(adapter: LocalNetworkAdapter) -> None:
    """对本机已监听端口检测应返回开放。"""
    server = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = adapter.check_tcp_port("127.0.0.1", port)
        assert result.success is True
        assert result.detail["is_open"] is True
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_check_tcp_port_closed(adapter: LocalNetworkAdapter) -> None:
    """对本机未监听端口检测应返回关闭（检测本身成功）。"""
    # 找一个当前未被监听的端口
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        free_port = probe.getsockname()[1]
    result = adapter.check_tcp_port("127.0.0.1", free_port)
    assert result.success is True
    assert result.detail["is_open"] is False


def test_traceroute_localhost(adapter: LocalNetworkAdapter) -> None:
    """Traceroute 本机回环（本机一跳可达）。"""
    result = adapter.traceroute("127.0.0.1", max_hops=3)
    assert result.source == DataSource.LOCAL_DIAGNOSTIC
    assert result.tool_name == "traceroute_host"
    # Windows tracert 对回环可能返回非 0，只要求执行完成有输出解析
    assert "hops" in result.detail


def test_traceroute_denied_target(adapter: LocalNetworkAdapter) -> None:
    """Traceroute 同样受白名单约束。"""
    result = adapter.traceroute("1.1.1.1", max_hops=3)
    assert result.success is False
    assert result.error
