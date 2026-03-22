"""后台联合分析线程 — 重新加载 xlsx 并调用 toolkit.core.joint_assessment。"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from toolkit.core.joint_assessment import assess_joint, build_observations_snapshot
from toolkit.core.perfdog import AnalyzeOptions, load_and_analyze
from toolkit.sdk.joint_models import JointAssessOptions, PolicySnapshot


class JointAssessmentWorker(QThread):
    """子线程执行 assess_joint；入参为文件路径 + 已序列化策略 dict，避免跨线程传大对象。"""

    progress = pyqtSignal(str)
    joint_finished_ok = pyqtSignal(object)
    joint_finished_err = pyqtSignal(str)

    def __init__(
        self,
        report_path: str,
        policy_dict: dict,
        *,
        skip_package_warning: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._report_path = report_path
        self._policy_dict = policy_dict
        self._skip_package_warning = skip_package_warning

    def run(self) -> None:
        try:
            if self.isInterruptionRequested():
                return
            self.progress.emit("正在加载 PerfDog 报告…")
            opts = AnalyzeOptions(
                interrupt_check=lambda: self.isInterruptionRequested(),
            )
            report = load_and_analyze(self._report_path, options=opts)
            if self.isInterruptionRequested():
                return
            self.progress.emit("正在执行联合分析…")
            policy = PolicySnapshot.model_validate(self._policy_dict)
            observations = build_observations_snapshot(report)
            joint = assess_joint(
                policy,
                observations,
                options=JointAssessOptions(skip_package_warning=self._skip_package_warning),
            )
            self.progress.emit("完成")
            self.joint_finished_ok.emit(joint.model_dump(mode="json"))
        except Exception as e:
            self.joint_finished_err.emit(str(e))
