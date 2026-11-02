"""诊断参数与目标校验（安全门禁）。

模型生成的参数不能直接视为可信输入，所有工具入参必须先过本模块。
"""

import ipaddress
import re

from app.core.exceptions import InputValidationError, TargetDeniedError

MAX_HOST_LEN = 253
MAX_DEVICE_ID_LEN = 32

# 只允许字母、数字、点、连字符、冒号（IPv6）、方括号（IPv6 字面量）
SAFE_CHARS_RE = re.compile(r"^[A-Za-z0-9\.\-:\[\]]+$")
HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)"
    r"[A-Za-z0-9]([A-Za-z0-9\-]{0,61}[A-Za-z0-9])?"
    r"(\.[A-Za-z0-9]([A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)*$"
)
DEVICE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,30}$")


def parse_allowed_targets(raw: str) -> list[str]:
    """解析逗号分隔的白名单配置。"""
    return [item.strip() for item in raw.split(",") if item.strip()]


def validate_host(host: str) -> str:
    """校验并规范化主机名或 IP 地址。

    Args:
        host: 待校验的主机名或 IP 字面量。

    Returns:
        规范化后的主机名（小写）或 IP 字符串。

    Raises:
        InputValidationError: 格式非法时抛出。
    """
    if not isinstance(host, str) or not host.strip():
        raise InputValidationError("host 不能为空")
    candidate = host.strip()
    if len(candidate) > MAX_HOST_LEN:
        raise InputValidationError("host 超出最大长度")
    if not SAFE_CHARS_RE.match(candidate):
        raise InputValidationError("host 含非法字符")
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        pass
    if not HOSTNAME_RE.match(candidate):
        raise InputValidationError("host 不是合法主机名")
    return candidate.lower()


def validate_port(port: int) -> int:
    """校验 TCP 端口范围 1-65535。"""
    if not isinstance(port, int) or isinstance(port, bool):
        raise InputValidationError("port 必须是整数")
    if port < 1 or port > 65535:
        raise InputValidationError("port 超出范围 1-65535")
    return port


def validate_count(count: int) -> int:
    """校验 Ping 次数范围 1-10。"""
    if not isinstance(count, int) or isinstance(count, bool):
        raise InputValidationError("count 必须是整数")
    if count < 1 or count > 10:
        raise InputValidationError("count 超出范围 1-10")
    return count


def validate_max_hops(max_hops: int) -> int:
    """校验 Traceroute 最大跳数 1-30。"""
    if not isinstance(max_hops, int) or isinstance(max_hops, bool):
        raise InputValidationError("max_hops 必须是整数")
    if max_hops < 1 or max_hops > 30:
        raise InputValidationError("max_hops 超出范围 1-30")
    return max_hops


def validate_device_id(device_id: str) -> str:
    """校验模拟设备 ID，防止路径穿越等注入。"""
    if not isinstance(device_id, str) or not device_id.strip():
        raise InputValidationError("device_id 不能为空")
    candidate = device_id.strip().lower()
    if len(candidate) > MAX_DEVICE_ID_LEN:
        raise InputValidationError("device_id 超出最大长度")
    if not DEVICE_ID_RE.match(candidate):
        raise InputValidationError("device_id 格式非法")
    return candidate


def ensure_allowed_target(
    host: str, allowed: list[str], allow_all: bool = False
) -> str:
    """校验主机并确认在白名单内（规范化后精确匹配）。

    Args:
        host: 目标主机。
        allowed: 允许诊断的目标列表。
        allow_all: 为 True 时跳过白名单校验，仅做输入格式校验。
            仅在显式配置 `DIAG_ALLOW_ALL_TARGETS=true` 时启用，
            用于受控测试环境放开目标限制。

    Returns:
        通过校验的主机名。

    Raises:
        InputValidationError: 主机格式非法。
        TargetDeniedError: 不在白名单内（allow_all=False 时）。
    """
    normalized = validate_host(host)
    if allow_all:
        return normalized
    allowed_set = {validate_host(item) for item in allowed}
    if normalized not in allowed_set:
        raise TargetDeniedError(f"目标 {normalized} 不在白名单内")
    return normalized
