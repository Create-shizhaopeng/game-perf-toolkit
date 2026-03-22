"""后台联合分析线程 — 调用 `PerfdogInsightsService`（先 load 再 assess）。"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from .service import PerfdogInsightsService


class JointAssessmentWorker(QThread):
    """子线程执行联合分析；入参为文件路径 + 已序列化策略 dict，避免跨线程传大对象。"""

    progress = pyqtSignal(str)
    joint_finished_ok = pyqtSignal(object)
    joint_finished_err = pyqtSignal(str)

    def __init__(
        self,
        report_path: str,
        policy_dict: dict,
        service: PerfdogInsightsService,
        *,
        skip_package_warning: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._report_path = report_path
        self._policy_dict = policy_dict
        self._service = service
        self._skip_package_warning = skip_package_warning

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                return
            self.progress.emit("正在加载 PerfDog 报告…")
            report = self._service.load_report(
                self._report_path,
                interrupt_check=lambda: self.isInterruptionRequested(),
            )
            if self.isInterruptionRequested():
                return
            self.progress.emit("正在执行联合分析…")
            payload = self._service.assess_joint_from_loaded_report(
                report,
                self._policy_dict,
                skip_package_warning=self._skip_package_warning,
            )
            self.progress.emit("完成")
            self.joint_finished_ok.emit(payload)
        except Exception as e:
            self.joint_finished_err.emit(str(e))
