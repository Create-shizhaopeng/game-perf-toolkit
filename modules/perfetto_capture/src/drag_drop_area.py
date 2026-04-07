"""拖入区域组件 — 接受外部 trace 文件。"""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)

_ACCEPTED_SUFFIXES = {".perfetto-trace", ".pb", ".pftrace"}


class DragDropArea(QWidget):
    """拖入区域，接受 Perfetto trace 文件。"""

    file_dropped = pyqtSignal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(48)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._label = QLabel("📥 拖入 trace 文件到此处")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet(
            "color: #a6adc8; font-size: 12px; "
            "border: 1px dashed #45475a; border-radius: 6px; "
            "padding: 8px;"
        )
        layout.addWidget(self._label)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = Path(url.toLocalFile())
                if self._is_accepted(path):
                    event.acceptProposedAction()
                    self._label.setStyleSheet(
                        "color: #cba6f7; font-size: 12px; "
                        "border: 2px dashed #cba6f7; border-radius: 6px; "
                        "padding: 8px; background: rgba(203, 166, 247, 0.1);"
                    )
                    return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._label.setStyleSheet(
            "color: #a6adc8; font-size: 12px; "
            "border: 1px dashed #45475a; border-radius: 6px; "
            "padding: 8px;"
        )
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self._label.setStyleSheet(
            "color: #a6adc8; font-size: 12px; "
            "border: 1px dashed #45475a; border-radius: 6px; "
            "padding: 8px;"
        )

        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if self._is_accepted(path):
                self.file_dropped.emit(path)
                logger.info("文件拖入: %s", path)
            else:
                logger.warning("格式不支持: %s", path.suffix)

    def _is_accepted(self, path: Path) -> bool:
        return path.is_file() and path.suffix in _ACCEPTED_SUFFIXES
