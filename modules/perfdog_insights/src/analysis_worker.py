"""后台解析线程 — 调用 `PerfdogInsightsService.load_report`。"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from toolkit.core.perfdog.errors import PerfDogParseError, PerfDogUnsupportedError

from .service import PerfdogInsightsService


class PerfDogAnalysisWorker(QThread):
    """在子线程中解析 xlsx，通过信号回传结果。"""

    progress = pyqtSignal(str)
    finished_ok = pyqtSignal(object)
    finished_err = pyqtSignal(str)

    def __init__(self, path: str, service: PerfdogInsightsService, parent=None) -> None:
        super().__init__(parent)
        self._path = path
        self._service = service

    def run(self) -> None:
        try:
            self.progress.emit("正在读取 Excel…")
            self.progress.emit("正在解析 Data_v4 与生成洞察…")
            report = self._service.load_report(
                self._path,
                interrupt_check=lambda: self.isInterruptionRequested(),
            )
            self.progress.emit("完成")
            self.finished_ok.emit(report)
        except PerfDogUnsupportedError as e:
            self.finished_err.emit(str(e))
        except PerfDogParseError as e:
            self.finished_err.emit(str(e))
        except Exception as e:
            self.finished_err.emit(f"解析失败: {e}")
