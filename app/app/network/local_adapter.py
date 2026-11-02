"""本机网络诊断适配器。

安全要求：
1. 不使用 shell=True，命令为固定程序 + 参数列表。
2. 目标主机必须通过格式校验；白名单限制可通过 allow_all_targets 显式放开。
3. 所有检测带超时，结果标记为 local_diagnostic。

注意：当 allow_all_targets=True 时，适配器可对任意 IP 执行诊断，
仅限受控测试环境使用；请勿对未授权网络、主机或设备执行扫描。
"""

import logging
import os
import re
import socket
import subprocess
from typing import Any

from app.core.exceptions import (
    InputValidationError,
    TargetDeniedError,
)
from app.network.base import DataSource, ToolResult
from app.network.validation import (
    ensure_allowed_target,
    validate_count,
    validate_host,
    validate_max_hops,
    validate_port,
)

logger = logging.getLogger(__name__)

_IS_WINDOWS = os.name == "nt"


def _build_ping_cmd(host: str, count: int) -> list[str]:
    """构建 Ping 命令参数列表（Windows/Unix），禁止 shell 拼接。"""
    if _IS_WINDOWS:
        return ["ping", "-n", str(count), "-w", "3000", host]
    return ["ping", "-c", str(count), "-W", "3", host]


def _build_tracert_cmd(host: str, max_hops: int) -> list[str]:
    """构建 Traceroute 命令参数列表（Windows/Unix），禁止 shell 拼接。"""
    if _IS_WINDOWS:
        return ["tracert", "-d", "-h", str(max_hops), "-w", "2000", host]
    return ["traceroute", "-n", "-m", str(max_hops), "-w", "2", host]

# Windows 中文环境 Ping 输出中含 "TTL=" 或 "字节=" 等，按行解析统计
_WIN_LOSS_RE = re.compile(r"丢失\s*=\s*(\d+)")
_WIN_RTT_RE = re.compile(r"平均\s*=\s*(\d+)\s*ms")
_UNIX_LOSS_RE = re.compile(r"(\d+(?:\.\d+)?)% packet loss")
_UNIX_RTT_RE = re.compile(r"= (?:[\d.]+/){3}([\d.]+)")
_TRACERT_LINE_RE = re.compile(r"^\s*(\d+)\s+(.*)$")


class LocalNetworkAdapter:
    """本机网络诊断适配器（只读检测）。"""

    def __init__(
        self,
        allowed_targets: list[str] | None = None,
        timeout: float = 10.0,
        allow_all_targets: bool = False,
    ) -> None:
        self._allowed = allowed_targets or ["localhost", "127.0.0.1", "::1"]
        self._timeout = timeout
        self._allow_all = allow_all_targets

    def _check_target(self, host: str) -> str:
        return ensure_allowed_target(
            host, self._allowed, allow_all=self._allow_all
        )

    def ping(self, host: str, count: int = 4) -> ToolResult:
        """执行 Ping 检测连通性。"""
        tool = "ping_host"
        try:
            safe_host = self._check_target(host)
            safe_count = validate_count(count)
        except (InputValidationError, TargetDeniedError) as exc:
            return self._denied_result(tool, exc)

        return self._run_cmd(
            tool=tool,
            cmd=_build_ping_cmd(safe_host, safe_count),
            host=safe_host,
            parse_fn=self._parse_ping,
            extra={"count": safe_count},
        )

    def dns_lookup(self, hostname: str) -> ToolResult:
        """执行 DNS 解析（A/AAAA 记录）。"""
        tool = "dns_lookup"
        try:
            safe_host = validate_host(hostname)
        except InputValidationError as exc:
            return self._denied_result(tool, exc)

        try:
            infos = socket.getaddrinfo(safe_host, None)
        except socket.gaierror as exc:
            return ToolResult(
                tool_name=tool,
                source=DataSource.LOCAL_DIAGNOSTIC,
                success=False,
                summary="",
                error=f"DNS 解析失败: {exc}",
            )
        addresses = sorted({item[4][0] for item in infos})
        return ToolResult(
            tool_name=tool,
            source=DataSource.LOCAL_DIAGNOSTIC,
            success=True,
            summary=f"主机 {safe_host} 解析到 {len(addresses)} 个地址",
            detail={"hostname": safe_host, "addresses": addresses},
        )

    def traceroute(self, host: str, max_hops: int = 15) -> ToolResult:
        """执行 Traceroute 路径追踪。"""
        tool = "traceroute_host"
        try:
            safe_host = self._check_target(host)
            safe_hops = validate_max_hops(max_hops)
        except (InputValidationError, TargetDeniedError) as exc:
            return self._denied_result(tool, exc)

        return self._run_cmd(
            tool=tool,
            cmd=_build_tracert_cmd(safe_host, safe_hops),
            host=safe_host,
            parse_fn=self._parse_tracert,
            extra={"max_hops": safe_hops},
        )

    def check_tcp_port(self, host: str, port: int) -> ToolResult:
        """检测目标 TCP 端口是否开放。"""
        tool = "check_tcp_port"
        try:
            safe_host = self._check_target(host)
            safe_port = validate_port(port)
        except (InputValidationError, TargetDeniedError) as exc:
            return self._denied_result(tool, exc)

        try:
            with socket.create_connection(
                (safe_host, safe_port), timeout=self._timeout
            ):
                return ToolResult(
                    tool_name=tool,
                    source=DataSource.LOCAL_DIAGNOSTIC,
                    success=True,
                    summary=f"端口 {safe_host}:{safe_port} 开放",
                    detail={"host": safe_host, "port": safe_port, "is_open": True},
                )
        except TimeoutError:
            return ToolResult(
                tool_name=tool,
                source=DataSource.LOCAL_DIAGNOSTIC,
                success=True,
                summary=f"端口 {safe_host}:{safe_port} 连接超时",
                detail={
                    "host": safe_host,
                    "port": safe_port,
                    "is_open": False,
                    "reason": "timeout",
                },
            )
        except OSError as exc:
            return ToolResult(
                tool_name=tool,
                source=DataSource.LOCAL_DIAGNOSTIC,
                success=True,
                summary=f"端口 {safe_host}:{safe_port} 关闭或拒绝连接",
                detail={
                    "host": safe_host,
                    "port": safe_port,
                    "is_open": False,
                    "reason": str(exc),
                },
            )

    def _denied_result(self, tool: str, exc: Exception) -> ToolResult:
        """入参校验或白名单拒绝结果。"""
        return ToolResult.fail(tool, DataSource.LOCAL_DIAGNOSTIC, str(exc))

    def _run_cmd(
        self,
        tool: str,
        cmd: list[str],
        host: str,
        parse_fn: Any,
        extra: dict[str, Any],
    ) -> ToolResult:
        """执行固定命令并解析输出，禁止 shell 拼接。"""
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ToolResult.fail(
                tool,
                DataSource.LOCAL_DIAGNOSTIC,
                f"命令执行超时（{self._timeout}s）: {' '.join(cmd)}",
            )
        except OSError as exc:
            return ToolResult.fail(
                tool, DataSource.LOCAL_DIAGNOSTIC, f"命令执行失败: {exc}"
            )

        output = (proc.stdout or "") + (proc.stderr or "")
        parsed = parse_fn(output)
        success = proc.returncode == 0
        summary = f"{tool} 目标 {host} 完成（returncode={proc.returncode}）"
        return ToolResult(
            tool_name=tool,
            source=DataSource.LOCAL_DIAGNOSTIC,
            success=success,
            summary=summary,
            detail={
                "host": host,
                "returncode": proc.returncode,
                "output_tail": output[-500:],
                **extra,
                **parsed,
            },
            error=None if success else f"命令返回码 {proc.returncode}",
        )

    @staticmethod
    def _parse_ping(output: str) -> dict[str, Any]:
        """解析 Ping 输出统计（兼容 Windows 中文与 Unix）。"""
        result: dict[str, Any] = {}
        loss = _WIN_LOSS_RE.search(output)
        if loss:
            result["packet_loss"] = int(loss.group(1))
        else:
            loss_unix = _UNIX_LOSS_RE.search(output)
            if loss_unix:
                result["packet_loss"] = float(loss_unix.group(1))
        rtt = _WIN_RTT_RE.search(output)
        if rtt:
            result["avg_rtt_ms"] = int(rtt.group(1))
        else:
            rtt_unix = _UNIX_RTT_RE.search(output)
            if rtt_unix:
                result["avg_rtt_ms"] = float(rtt_unix.group(1))
        return result

    @staticmethod
    def _parse_tracert(output: str) -> dict[str, Any]:
        """解析 Traceroute/Tracert 跳点列表。"""
        hops: list[dict[str, Any]] = []
        for line in output.splitlines():
            match = _TRACERT_LINE_RE.match(line)
            if not match:
                continue
            hop_no = int(match.group(1))
            rest = match.group(2).strip()
            # 提取 RTT（可能含 * 超时）
            rtts = re.findall(r"(\d+)\s*ms", rest)
            target = rest.split()[-1] if rest else ""
            hops.append(
                {
                    "hop": hop_no,
                    "rtts_ms": [int(v) for v in rtts],
                    "target": target,
                }
            )
        return {"hops": hops}
