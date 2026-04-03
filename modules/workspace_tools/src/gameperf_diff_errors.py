"""gameperfconfig 对比模块异常（对外语义化，避免裸 Exception）"""

from __future__ import annotations


class XmlParseError(Exception):
    """XML 非良构或无法解析。"""


class InvalidGamePerfFileError(Exception):
    """文件可解析但根节点等不符合 gameperfconfig 约定。"""


class DiffValidationError(Exception):
    """对比/合并不满足前置条件（无会话、索引越界等）。"""


class GamePerfDevicePullError(Exception):
    """从设备拉取配置文件失败。"""

    def __init__(self, message: str, *, failure_kind: str = "transport") -> None:
        super().__init__(message)
        self.user_message = message
        self.failure_kind = failure_kind
