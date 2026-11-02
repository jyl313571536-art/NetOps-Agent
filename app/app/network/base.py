"""Network Adapter Layer 基础数据模型。

所有诊断结果必须标记数据来源：simulation（模拟）或 local_diagnostic（本机检测）。
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DataSource(StrEnum):
    """诊断数据来源标记。"""

    SIMULATION = "simulation"
    LOCAL_DIAGNOSTIC = "local_diagnostic"


class ToolResult(BaseModel):
    """所有诊断工具的统一返回结构。"""

    tool_name: str
    source: DataSource
    success: bool
    summary: str
    detail: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    @classmethod
    def ok(
        cls,
        tool_name: str,
        source: DataSource,
        summary: str,
        detail: dict[str, Any] | None = None,
    ) -> "ToolResult":
        """成功结果工厂。"""
        return cls(
            tool_name=tool_name,
            source=source,
            success=True,
            summary=summary,
            detail=detail or {},
        )

    @classmethod
    def fail(
        cls,
        tool_name: str,
        source: DataSource,
        error: str,
    ) -> "ToolResult":
        """失败结果工厂：不伪造 summary，错误信息如实填写。"""
        return cls(
            tool_name=tool_name,
            source=source,
            success=False,
            summary="",
            error=error,
        )


class InterfaceInfo(BaseModel):
    """设备接口状态。"""

    name: str
    admin_status: str
    oper_status: str
    speed: str | None = None
    description: str | None = None
    vlan: str | None = None


class RouteEntry(BaseModel):
    """路由表条目。"""

    destination: str
    mask: str
    next_hop: str
    interface: str | None = None
    protocol: str = "static"
    metric: int | None = None


class VlanInfo(BaseModel):
    """VLAN 配置。"""

    vlan_id: int
    name: str
    ports: list[str] = Field(default_factory=list)


class DeviceLogEntry(BaseModel):
    """设备日志条目。"""

    timestamp: str
    level: str
    device: str
    message: str


class DeviceInfo(BaseModel):
    """模拟设备基础信息。"""

    device_id: str
    device_type: str
    hostname: str
