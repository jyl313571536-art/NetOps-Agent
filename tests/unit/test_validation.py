"""参数校验模块单元测试。"""

import pytest

from app.core.exceptions import InputValidationError, TargetDeniedError
from app.network.validation import (
    ensure_allowed_target,
    parse_allowed_targets,
    validate_count,
    validate_device_id,
    validate_host,
    validate_max_hops,
    validate_port,
)

LOOPBACK = ["localhost", "127.0.0.1", "::1"]


def test_validate_host_accepts_ip_and_hostname() -> None:
    """合法 IP 与主机名通过校验并规范化。"""
    assert validate_host("127.0.0.1") == "127.0.0.1"
    assert validate_host("LOCALHOST") == "localhost"
    assert validate_host(" Example.COM ") == "example.com"


def test_validate_host_rejects_injection() -> None:
    """拒绝命令注入、空值与非法字符。"""
    for bad in ["", "  ", "host;rm -rf", "host && echo", "$(whoami)", "a" * 300]:
        with pytest.raises(InputValidationError):
            validate_host(bad)


def test_validate_port_range() -> None:
    """端口范围 1-65535。"""
    assert validate_port(22) == 22
    for bad in [0, 65536, -1, "80", True]:
        with pytest.raises(InputValidationError):
            validate_port(bad)


def test_validate_count_range() -> None:
    """Ping 次数范围 1-10。"""
    assert validate_count(4) == 4
    for bad in [0, 11, -1, "2"]:
        with pytest.raises(InputValidationError):
            validate_count(bad)


def test_validate_max_hops_range() -> None:
    """Traceroute 跳数范围 1-30。"""
    assert validate_max_hops(15) == 15
    for bad in [0, 31, "10"]:
        with pytest.raises(InputValidationError):
            validate_max_hops(bad)


def test_validate_device_id_blocks_path_traversal() -> None:
    """设备 ID 拒绝路径穿越。"""
    assert validate_device_id("switch-01") == "switch-01"
    for bad in ["../etc/passwd", "a/b", "", "SWITCH_01!", "x" * 40]:
        with pytest.raises(InputValidationError):
            validate_device_id(bad)


def test_ensure_allowed_target_loopback_only() -> None:
    """默认白名单只放行本机回环。"""
    assert ensure_allowed_target("127.0.0.1", LOOPBACK) == "127.0.0.1"
    assert ensure_allowed_target("localhost", LOOPBACK) == "localhost"
    with pytest.raises(TargetDeniedError):
        ensure_allowed_target("8.8.8.8", LOOPBACK)
    with pytest.raises(TargetDeniedError):
        ensure_allowed_target("example.com", LOOPBACK)


def test_ensure_allowed_target_allow_all_bypasses_whitelist() -> None:
    """allow_all=True 跳过白名单，仅做输入格式校验。"""
    assert ensure_allowed_target("8.8.8.8", LOOPBACK, allow_all=True) == "8.8.8.8"
    assert (
        ensure_allowed_target("example.com", LOOPBACK, allow_all=True) == "example.com"
    )
    # 输入格式校验仍然生效
    with pytest.raises(InputValidationError):
        ensure_allowed_target("host;rm -rf", LOOPBACK, allow_all=True)
    with pytest.raises(InputValidationError):
        ensure_allowed_target("", LOOPBACK, allow_all=True)


def test_parse_allowed_targets() -> None:
    """逗号分隔配置解析。"""
    assert parse_allowed_targets("a, b ,c,") == ["a", "b", "c"]
    assert parse_allowed_targets("") == []
