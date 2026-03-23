"""游戏性能配置模块 — 数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class GamePerfDocumentOrigin(str, Enum):
    """当前配置缓冲区的文档来源（手动打开 / 自动从设备载入）。"""

    NONE = "none"
    LOCAL_FILE = "local_file"
    DEVICE = "device"


@dataclass
class AutoDevicePullResult:
    """从设备自动拉取 `gameperfconfig.xml` 的结果摘要（GUI 状态栏 / 日志）。

    failure_kind：失败粗分类，如 missing、permission、transport、parse；成功时为 None。
    """

    ok: bool
    user_message: str = ""
    origin: GamePerfDocumentOrigin = GamePerfDocumentOrigin.NONE
    failure_kind: str | None = None


@dataclass
class ClusterInfo:
    """CPU/GPU 频率 cluster"""

    name: str
    frequencies: list[int] = field(default_factory=list)


@dataclass
class GameScene:
    """游戏场景"""

    scene_id: str
    note: str = ""


@dataclass
class FreqRow:
    """频率配置表的一行数据"""

    game_alias: str
    package_name: str
    mode_name: str
    thermal_scene_code: str = ""
    perf_hint: str = ""
    temp_level: str = ""
    trigger_temp: str = ""
    gold_min: int = 0
    gold_max: int = 0
    gold_index: str = ""
    prime_min: int = 0
    prime_max: int = 0
    prime_index: str = ""
    gpu_min: int = 0
    gpu_max: int = 0
    gpu_index: str = ""
    # XML DOM 引用（lxml 节点），不序列化
    xml_node: Any = field(default=None, repr=False)
    mode_xml_node: Any = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """返回可序列化的字典（排除 XML 节点引用）"""
        return {
            "game_alias": self.game_alias,
            "package_name": self.package_name,
            "mode_name": self.mode_name,
            "thermal_scene_code": self.thermal_scene_code,
            "perf_hint": self.perf_hint,
            "temp_level": self.temp_level,
            "trigger_temp": self.trigger_temp,
            "gold_min": self.gold_min,
            "gold_max": self.gold_max,
            "gold_index": self.gold_index,
            "prime_min": self.prime_min,
            "prime_max": self.prime_max,
            "prime_index": self.prime_index,
            "gpu_min": self.gpu_min,
            "gpu_max": self.gpu_max,
            "gpu_index": self.gpu_index,
        }


@dataclass
class StrategyItem:
    """策略面板中的一个节点块"""

    tag: str
    pairs: list[dict[str, Any]] = field(default_factory=list)
    element: Any = field(default=None, repr=False)


@dataclass
class XmlErrorContext:
    """XML 解析错误及其上下文行"""

    error_msg: str
    error_line: int
    error_col: int
    context_lines: list[tuple[int, str, bool]] = field(default_factory=list)


@dataclass
class PushRecord:
    """推送记录"""

    game: str
    package: str
    mode: str
    notes: str = ""
    version: int = 0
    saved_at: str = ""
    json_path: str = ""
    data: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "game": self.game,
            "package": self.package,
            "mode": self.mode,
            "notes": self.notes,
            "version": self.version,
            "saved_at": self.saved_at or datetime.now().isoformat(),
            "data": self.data,
        }
