"""模拟网络设备适配器。

只读取 data/simulated_devices/ 与 data/sample_logs/ 下的虚构数据，
所有返回结果标记为 simulation，不得与真实设备状态混淆。
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.core.exceptions import InputValidationError
from app.network.base import (
    DataSource,
    DeviceInfo,
    DeviceLogEntry,
    InterfaceInfo,
    RouteEntry,
    ToolResult,
    VlanInfo,
)
from app.network.validation import validate_device_id

logger = logging.getLogger(__name__)

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class MockNetworkAdapter:
    """模拟设备适配器，提供只读设备状态分析。"""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or DEFAULT_DATA_DIR
        self._device_cache: dict[str, dict] = {}
        self._log_cache: dict[str, list[DeviceLogEntry]] = {}

    def _load_device(self, device_id: str) -> dict:
        """加载模拟设备数据（带缓存），设备不存在时抛出 FileNotFoundError。"""
        safe_id = validate_device_id(device_id)
        if safe_id in self._device_cache:
            return self._device_cache[safe_id]
        path = self._data_dir / "simulated_devices" / f"{safe_id}.json"
        if not path.is_file():
            raise FileNotFoundError(f"模拟设备 {safe_id} 不存在")
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        self._device_cache[safe_id] = data
        return data

    def _load_logs(self, device_id: str) -> list[DeviceLogEntry]:
        """加载模拟设备日志（带缓存），逐行解析为结构化条目。"""
        safe_id = validate_device_id(device_id)
        if safe_id in self._log_cache:
            return self._log_cache[safe_id]
        path = self._data_dir / "sample_logs" / f"{safe_id}.log"
        if not path.is_file():
            raise FileNotFoundError(f"模拟设备日志 {safe_id} 不存在")
        entries: list[DeviceLogEntry] = []
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                parts = line.strip().split(maxsplit=3)
                if len(parts) < 4:
                    continue
                timestamp, level, device, message = parts
                entries.append(
                    DeviceLogEntry(
                        timestamp=timestamp,
                        level=level,
                        device=device,
                        message=message,
                    )
                )
        self._log_cache[safe_id] = entries
        return entries

    def _analyze(
        self,
        tool: str,
        device_id: str,
        extract: Callable[[dict, str], tuple[str, dict[str, Any]]],
    ) -> ToolResult:
        """统一的设备分析外壳：加载 → 提取 → 成功/失败结果。

        Args:
            tool: 工具名。
            device_id: 模拟设备 ID。
            extract: (设备数据, 设备 ID) → (摘要, detail)。
        """
        try:
            data = self._load_device(device_id)
            summary, detail = extract(data, device_id)
            return ToolResult.ok(tool, DataSource.SIMULATION, summary, detail)
        except (FileNotFoundError, InputValidationError) as exc:
            return ToolResult.fail(tool, DataSource.SIMULATION, str(exc))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("读取模拟设备 %s 失败: %s", device_id, exc)
            return ToolResult.fail(
                tool, DataSource.SIMULATION, f"模拟设备数据解析失败: {exc}"
            )

    def list_devices(self) -> list[DeviceInfo]:
        """列出全部模拟设备（按文件名排序）。"""
        devices: list[DeviceInfo] = []
        device_dir = self._data_dir / "simulated_devices"
        if not device_dir.is_dir():
            return devices
        for path in sorted(device_dir.glob("*.json")):
            try:
                data = self._load_device(path.stem)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                logger.warning("跳过无效模拟设备文件 %s: %s", path.name, exc)
                continue
            devices.append(
                DeviceInfo(
                    device_id=data.get("device_id", path.stem),
                    device_type=data.get("device_type", "unknown"),
                    hostname=data.get("hostname", "unknown"),
                )
            )
        return devices

    def analyze_interface_status(self, device_id: str) -> ToolResult:
        """分析模拟设备接口状态。"""

        def extract(data: dict, target: str) -> tuple[str, dict[str, Any]]:
            interfaces = [
                InterfaceInfo(**item) for item in data.get("interfaces", [])
            ]
            up_count = sum(1 for i in interfaces if i.oper_status == "up")
            summary = (
                f"模拟设备 {data.get('hostname', target)} 共 "
                f"{len(interfaces)} 个接口，其中 {up_count} 个状态为 up"
            )
            return summary, {"interfaces": [i.model_dump() for i in interfaces]}

        return self._analyze("analyze_interface_status", device_id, extract)

    def analyze_routing_table(self, device_id: str) -> ToolResult:
        """分析模拟设备路由表。"""

        def extract(data: dict, target: str) -> tuple[str, dict[str, Any]]:
            routes = [RouteEntry(**item) for item in data.get("routes", [])]
            default_count = sum(
                1
                for r in routes
                if r.destination == "0.0.0.0" and r.mask == "0.0.0.0"
            )
            summary = (
                f"模拟设备 {data.get('hostname', target)} 共 "
                f"{len(routes)} 条路由，其中 {default_count} 条默认路由"
            )
            return summary, {"routes": [r.model_dump() for r in routes]}

        return self._analyze("analyze_routing_table", device_id, extract)

    def analyze_vlan_config(self, device_id: str) -> ToolResult:
        """分析模拟设备 VLAN 配置。"""

        def extract(data: dict, target: str) -> tuple[str, dict[str, Any]]:
            vlans = [VlanInfo(**item) for item in data.get("vlans", [])]
            summary = (
                f"模拟设备 {data.get('hostname', target)} 共配置 "
                f"{len(vlans)} 个 VLAN"
            )
            return summary, {"vlans": [v.model_dump() for v in vlans]}

        return self._analyze("analyze_vlan_config", device_id, extract)

    def analyze_network_logs(
        self, device_id: str, level: str | None = None
    ) -> ToolResult:
        """分析模拟设备网络日志，可按级别过滤。"""
        tool = "analyze_network_logs"
        try:
            entries = self._load_logs(device_id)
            if level:
                wanted = level.strip().upper()
                entries = [e for e in entries if e.level.upper() == wanted]
            level_count: dict[str, int] = {}
            for entry in entries:
                level_count[entry.level] = level_count.get(entry.level, 0) + 1
            suffix = f"（级别 {level.upper()}）" if level else ""
            summary = (
                f"模拟设备日志共 {len(entries)} 条{suffix}，级别分布: {level_count}"
            )
            return ToolResult.ok(
                tool,
                DataSource.SIMULATION,
                summary,
                {"logs": [e.model_dump() for e in entries]},
            )
        except (FileNotFoundError, InputValidationError) as exc:
            return ToolResult.fail(tool, DataSource.SIMULATION, str(exc))
        except OSError as exc:
            logger.warning("读取模拟设备 %s 日志失败: %s", device_id, exc)
            return ToolResult.fail(
                tool, DataSource.SIMULATION, f"模拟设备日志读取失败: {exc}"
            )
