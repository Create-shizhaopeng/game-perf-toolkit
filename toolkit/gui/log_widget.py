"""共享日志文本组件 — 提供带颜色着色的日志追加功能。

多个模块（perfetto_capture、device_disguise、game_perf）共用此组件，
避免各自重复实现 QTextCharFormat + cursor 日志着色逻辑。
"""

from __future__ import annotations

import datetime

from PyQt6.QtGui import QColor, QTextCharFormat
from PyQt6.QtWidgets import QTextEdit, QWidget

from toolkit.gui.theme_colors import get_colors


class LogTextEdit(QTextEdit):
    """带主题着色的只读日志文本框。

    用法:
        self._log = LogTextEdit()
        self._log.append_log("操作成功", level="success")
        self._log.append_log("发生错误", level="error")
        self._log.append_log("提示信息")  # 默认 info 级别
        self._log.append_log("自定义颜色", color="#FF6600")
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self._theme = "dark"

    def set_theme(self, theme: str) -> None:
        self._theme = theme

    def append_log(
        self,
        text: str,
        *,
        level: str = "info",
        color: str | None = None,
        timestamp: bool = True,
    ) -> None:
        """追加一行日志，按 level 或自定义 color 着色。

        Args:
            text: 日志文本
            level: "info" | "success" | "error" | "warning"
            color: 自定义颜色（优先级高于 level）
            timestamp: 是否在前面添加 [HH:MM:SS] 时间戳
        """
        if color:
            fg = color
        else:
            c = get_colors(self._theme)
            fg = {
                "success": c["success"],
                "error": c["error"],
                "warning": c["warning"],
            }.get(level, c["fg"])

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(fg))

        prefix = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] " if timestamp else ""
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(f"{prefix}{text}\n", fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
