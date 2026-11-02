"""网络诊断工具封装。

工具独立于大模型，输入输出使用 Pydantic 明确定义，
所有结果带数据来源标记（simulation / local_diagnostic）。

TOOL_SPECS 是工具元数据的唯一来源：名称、描述、参数模型、处理方法名。
新增工具只需在此登记一次，注册表与执行分发表自动派生。
"""

from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings
from app.core.exceptions import InputValidationError
from app.network.base import DataSource, ToolResult
from app.network.local_adapter import LocalNetworkAdapter
from app.network.mock_adapter import MockNetworkAdapter
from app.network.validation import parse_allowed_targets


class PingArgs(BaseModel):
    """ping_host 入参。"""

    host: str = Field(description="目标主机 IP 或域名，仅允许白名单内目标")
    count: int = Field(default=4, ge=1, le=10, description="Ping 次数，1-10")


class DnsArgs(BaseModel):
    """dns_lookup 入参。"""

    hostname: str = Field(description="要解析的主机名或域名")


class TracerouteArgs(BaseModel):
    """traceroute_host 入参。"""

    host: str = Field(description="目标主机 IP 或域名，仅允许白名单内目标")
    max_hops: int = Field(default=15, ge=1, le=30, description="最大跳数，1-30")


class TcpPortArgs(BaseModel):
    """check_tcp_port 入参。"""

    host: str = Field(description="目标主机 IP 或域名，仅允许白名单内目标")
    port: int = Field(ge=1, le=65535, description="TCP 端口号，1-65535")


class DeviceArgs(BaseModel):
    """设备分析工具入参。"""

    device_id: str = Field(
        description="模拟设备 ID，如 switch-01 / router-01 / firewall-01"
    )


class DeviceLogArgs(DeviceArgs):
    """analyze_network_logs 入参。"""

    level: str | None = Field(
        default=None,
        description="日志级别过滤：INFO / WARNING / ERROR，可选",
    )


class ToolSpec(BaseModel):
    """单个工具的元数据登记项。"""

    name: str
    description: str
    args_schema: type[BaseModel]
    source: DataSource


# 工具元数据唯一来源；处理方法名与工具名一致（NetworkTools 的同名方法）
TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="ping_host",
        description=(
            "对目标主机执行 Ping，检测连通性与丢包情况。"
            "这是本机真实检测（local_diagnostic），仅允许白名单内目标。"
        ),
        args_schema=PingArgs,
        source=DataSource.LOCAL_DIAGNOSTIC,
    ),
    ToolSpec(
        name="dns_lookup",
        description=(
            "查询主机名的 DNS 解析结果。"
            "这是本机真实检测（local_diagnostic）。"
        ),
        args_schema=DnsArgs,
        source=DataSource.LOCAL_DIAGNOSTIC,
    ),
    ToolSpec(
        name="traceroute_host",
        description=(
            "追踪到目标主机的路由路径。"
            "这是本机真实检测（local_diagnostic），仅允许白名单内目标。"
        ),
        args_schema=TracerouteArgs,
        source=DataSource.LOCAL_DIAGNOSTIC,
    ),
    ToolSpec(
        name="check_tcp_port",
        description=(
            "检测目标主机 TCP 端口是否开放。"
            "这是本机真实检测（local_diagnostic），仅允许白名单内目标。"
        ),
        args_schema=TcpPortArgs,
        source=DataSource.LOCAL_DIAGNOSTIC,
    ),
    ToolSpec(
        name="analyze_interface_status",
        description=(
            "分析模拟网络设备的接口状态。"
            "这是模拟数据（simulation），不是真实设备状态。"
        ),
        args_schema=DeviceArgs,
        source=DataSource.SIMULATION,
    ),
    ToolSpec(
        name="analyze_routing_table",
        description=(
            "分析模拟网络设备的路由表。"
            "这是模拟数据（simulation），不是真实设备状态。"
        ),
        args_schema=DeviceArgs,
        source=DataSource.SIMULATION,
    ),
    ToolSpec(
        name="analyze_vlan_config",
        description=(
            "分析模拟交换机的 VLAN 配置。"
            "这是模拟数据（simulation），不是真实设备状态。"
        ),
        args_schema=DeviceArgs,
        source=DataSource.SIMULATION,
    ),
    ToolSpec(
        name="analyze_network_logs",
        description=(
            "分析模拟网络设备的运行日志，可按级别过滤。"
            "这是模拟数据（simulation），不是真实设备日志。"
        ),
        args_schema=DeviceLogArgs,
        source=DataSource.SIMULATION,
    ),
]

# 派生的查表（构建一次，不再在调用路径上重建）
SPEC_BY_NAME: dict[str, ToolSpec] = {spec.name: spec for spec in TOOL_SPECS}


class NetworkTools:
    """网络诊断工具集合，聚合本机诊断与模拟设备分析。"""

    def __init__(
        self,
        local_adapter: LocalNetworkAdapter | None = None,
        mock_adapter: MockNetworkAdapter | None = None,
    ) -> None:
        cfg = get_settings()
        self._local = local_adapter or LocalNetworkAdapter(
            allowed_targets=parse_allowed_targets(cfg.diag_allowed_targets),
            timeout=cfg.diag_timeout,
            allow_all_targets=cfg.diag_allow_all_targets,
        )
        self._mock = mock_adapter or MockNetworkAdapter()
        self._handlers: dict[str, Any] = {
            spec.name: getattr(self, spec.name) for spec in TOOL_SPECS
        }

    def ping_host(self, host: str, count: int = 4) -> ToolResult:
        """对目标主机执行 Ping，检测连通性与丢包情况（本机真实检测）。"""
        return self._local.ping(host=host, count=count)

    def dns_lookup(self, hostname: str) -> ToolResult:
        """查询主机名的 DNS 解析结果（本机真实检测）。"""
        return self._local.dns_lookup(hostname=hostname)

    def traceroute_host(self, host: str, max_hops: int = 15) -> ToolResult:
        """追踪到目标主机的路由路径（本机真实检测）。"""
        return self._local.traceroute(host=host, max_hops=max_hops)

    def check_tcp_port(self, host: str, port: int) -> ToolResult:
        """检测目标主机 TCP 端口是否开放（本机真实检测）。"""
        return self._local.check_tcp_port(host=host, port=port)

    def analyze_interface_status(self, device_id: str) -> ToolResult:
        """分析模拟网络设备的接口状态（simulation 数据）。"""
        return self._mock.analyze_interface_status(device_id)

    def analyze_routing_table(self, device_id: str) -> ToolResult:
        """分析模拟网络设备的路由表（simulation 数据）。"""
        return self._mock.analyze_routing_table(device_id)

    def analyze_vlan_config(self, device_id: str) -> ToolResult:
        """分析模拟交换机的 VLAN 配置（simulation 数据）。"""
        return self._mock.analyze_vlan_config(device_id)

    def analyze_network_logs(
        self, device_id: str, level: str | None = None
    ) -> ToolResult:
        """分析模拟网络设备的运行日志（simulation 数据）。"""
        return self._mock.analyze_network_logs(device_id, level=level)

    def run_tool(self, name: str, args: dict[str, Any]) -> ToolResult:
        """按名称执行工具，返回结构化结果；工具不存在时返回失败结果。"""
        spec = SPEC_BY_NAME.get(name)
        if spec is None:
            return ToolResult.fail(
                name, DataSource.LOCAL_DIAGNOSTIC, f"未知工具: {name}"
            )
        try:
            model = spec.args_schema.model_validate(args)
            return self._handlers[name](**model.model_dump())
        except InputValidationError as exc:
            return ToolResult.fail(name, spec.source, str(exc))
        except ValidationError as exc:
            return ToolResult.fail(name, spec.source, f"工具参数校验失败: {exc}")
        except TypeError as exc:
            return ToolResult.fail(name, spec.source, f"工具参数不匹配: {exc}")
