"""PerfDog 分析 — GUI Tab（离线文件分析，不依赖 ADB）。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QGuiApplication
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from toolkit.core.joint_assessment import build_joint_markdown
from toolkit.core.perfdog import AnalysisReport, build_markdown
from toolkit.gui.base_tab import BaseTab
from toolkit.sdk.joint_models import JointAssessmentReport

from .analysis_worker import PerfDogAnalysisWorker
from .joint_worker import JointAssessmentWorker

_GP_JOINT_KEY = "gp_joint_policy_snapshot"


class PerfdogInsightsTab(BaseTab):
    """PerfDog Excel 导入与报告展示。"""

    tab_title = "PerfDog分析"
    tab_icon = "📈"

    def __init__(self, context: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._context = context or {}
        self._report: AnalysisReport | None = None
        self._worker: PerfDogAnalysisWorker | None = None
        self._joint_worker: JointAssessmentWorker | None = None
        self._last_good_report: AnalysisReport | None = None
        self._joint_report: dict | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 4, 8, 4)
        root.setSpacing(6)

        drop_card = QFrame()
        drop_card.setProperty("class", "sectionCard")
        drop_card.setAcceptDrops(True)
        dc_layout = QVBoxLayout(drop_card)
        dc_layout.setContentsMargins(12, 8, 12, 8)
        dc_layout.setSpacing(6)

        title_row = QHBoxLayout()
        t1 = QLabel("PerfDog 导出")
        t1.setProperty("class", "sectionTitleBlue")
        title_row.addWidget(t1)
        hint = QLabel("拖拽 .xlsx / .xlsm，或使用「选择文件」")
        hint.setProperty("class", "fieldLabel")
        hint.setStyleSheet("font-size: 10px; font-style: italic;")
        title_row.addWidget(hint)
        title_row.addStretch()
        dc_layout.addLayout(title_row)

        path_row = QHBoxLayout()
        self._path_edit = QLabel("未选择文件")
        self._path_edit.setWordWrap(True)
        self._path_edit.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )
        path_row.addWidget(self._path_edit, 1)
        self._browse_btn = QPushButton("选择文件…")
        self._browse_btn.setFixedHeight(28)
        self._browse_btn.setFixedWidth(96)
        path_row.addWidget(self._browse_btn)
        self._import_btn = QPushButton("开始分析")
        self._import_btn.setObjectName("primaryButton")
        self._import_btn.setFixedHeight(28)
        self._import_btn.setEnabled(False)
        path_row.addWidget(self._import_btn)
        self._clear_btn = QPushButton("清除当前分析")
        self._clear_btn.setFixedHeight(28)
        path_row.addWidget(self._clear_btn)
        dc_layout.addLayout(path_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setFixedHeight(6)
        dc_layout.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setProperty("class", "fieldLabel")
        dc_layout.addWidget(self._status_lbl)

        drop_card.dragEnterEvent = self._on_drag_enter  # type: ignore[method-assign]
        drop_card.dropEvent = self._on_drop  # type: ignore[method-assign]
        root.addWidget(drop_card)

        actions = QHBoxLayout()
        self._export_btn = QPushButton("导出报告…")
        self._export_btn.setFixedHeight(28)
        self._export_btn.setEnabled(False)
        self._copy_btn = QPushButton("复制报告")
        self._copy_btn.setFixedHeight(28)
        self._copy_btn.setEnabled(False)
        self._joint_btn = QPushButton("联合分析")
        self._joint_btn.setFixedHeight(28)
        self._joint_btn.setToolTip(
            "结合「游戏性能配置」中已加载的 XML 与当前 PerfDog 报告做对照（无需连接设备）。",
        )
        self._joint_btn.setEnabled(False)
        actions.addWidget(self._export_btn)
        actions.addWidget(self._copy_btn)
        actions.addWidget(self._joint_btn)
        actions.addStretch()
        root.addLayout(actions)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(0, 0, 8, 0)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setPlaceholderText(
            "导入 PerfDog 导出后，将在此显示会话摘要、问题与洞察、建议等。",
        )
        inner_layout.addWidget(self._browser)

        self._joint_group = QGroupBox("游戏性能策略联合分析")
        jg = QVBoxLayout(self._joint_group)
        self._joint_browser = QTextBrowser()
        self._joint_browser.setOpenExternalLinks(False)
        self._joint_browser.setPlaceholderText(
            "点击「联合分析」后在此展示策略要点、观测要点、一致性解读与警告。",
        )
        self._joint_browser.setMinimumHeight(160)
        jg.addWidget(self._joint_browser)

        sug_title = QLabel("策略调整建议（启发式）")
        sug_title.setProperty("class", "fieldLabel")
        jg.addWidget(sug_title)
        grid = QGridLayout()
        grid.addWidget(QLabel("绑核"), 0, 0)
        grid.addWidget(QLabel("频点"), 0, 1)
        self._bind_suggest_list = QListWidget()
        self._bind_suggest_list.setMinimumHeight(72)
        self._freq_suggest_list = QListWidget()
        self._freq_suggest_list.setMinimumHeight(72)
        grid.addWidget(self._bind_suggest_list, 1, 0)
        grid.addWidget(self._freq_suggest_list, 1, 1)
        jg.addLayout(grid)

        inner_layout.addWidget(self._joint_group)

        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        self._browse_btn.clicked.connect(self._on_browse)
        self._import_btn.clicked.connect(self._on_import)
        self._clear_btn.clicked.connect(self._on_clear)
        self._export_btn.clicked.connect(self._on_export)
        self._copy_btn.clicked.connect(self._on_copy)
        self._joint_btn.clicked.connect(self._on_joint_analyze)

    @staticmethod
    def _norm_pkg(s: str | None) -> str:
        return (s or "").strip().lower()

    def on_devices_changed(self, devices: list[str]) -> None:
        """离线分析：不因无设备禁用导入控件。"""
        self._device_connected = len(devices) > 0

    def on_activated(self) -> None:
        pass

    def on_deactivated(self) -> None:
        pass

    def _on_drag_enter(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def _on_drop(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        path = urls[0].toLocalFile()
        if path.lower().endswith((".xlsx", ".xlsm")):
            self._set_selected_path(path)
            event.acceptProposedAction()
        else:
            QMessageBox.warning(self, "格式不支持", "请拖入 .xlsx 或 .xlsm 文件。")
            event.ignore()

    def _set_selected_path(self, path: str) -> None:
        self._path_edit.setText(path)
        busy = (self._worker and self._worker.isRunning()) or (
            self._joint_worker and self._joint_worker.isRunning()
        )
        self._import_btn.setEnabled(bool(path) and not busy)

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 PerfDog 导出",
            "",
            "Excel (*.xlsx *.xlsm)",
        )
        if path:
            self._set_selected_path(path)

    def _on_import(self) -> None:
        path = self._path_edit.text().strip()
        if path == "未选择文件" or not path:
            return
        if not Path(path).is_file():
            QMessageBox.warning(self, "文件无效", "所选路径不是有效文件。")
            return

        self._start_worker(path)

    def _start_worker(self, path: str) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._browse_btn.setEnabled(False)
        self._import_btn.setEnabled(False)
        self._joint_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status_lbl.setText("解析中…")
        self._worker = PerfDogAnalysisWorker(path, self)
        self._worker.progress.connect(self._status_lbl.setText)
        self._worker.finished_ok.connect(self._on_worker_ok)
        self._worker.finished_err.connect(self._on_worker_err)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_ok(self, report: object) -> None:
        if not isinstance(report, AnalysisReport):
            return
        self._report = report
        self._last_good_report = report
        self._render_report(report)
        self._export_btn.setEnabled(True)
        self._copy_btn.setEnabled(True)
        self._joint_btn.setEnabled(True)
        self._status_lbl.setText("解析完成")

    def _on_worker_err(self, message: str) -> None:
        self._status_lbl.setText("解析失败")
        QMessageBox.warning(self, "解析失败", message)
        # FR-009：不覆盖上一份成功结果
        if self._last_good_report is not None:
            self._report = self._last_good_report
            self._render_report(self._last_good_report)
            self._joint_btn.setEnabled(True)

    def _on_worker_finished(self) -> None:
        self._progress.setVisible(False)
        self._browse_btn.setEnabled(True)
        p = self._path_edit.text().strip()
        busy = self._joint_worker and self._joint_worker.isRunning()
        self._import_btn.setEnabled(bool(p) and p != "未选择文件" and not busy)
        if self._report is not None and not busy:
            self._joint_btn.setEnabled(True)

    def _render_report(self, report: AnalysisReport) -> None:
        html_parts: list[str] = []

        s = report.session
        html_parts.append("<h3>会话摘要</h3>")
        html_parts.append("<ul>")
        html_parts.append(f"<li>包名: {self._esc(s.package_name or '（未识别）')}</li>")
        html_parts.append(f"<li>设备: {self._esc(s.device_name or '（未识别）')}</li>")
        html_parts.append(f"<li>推断目标帧率: {s.target_fps_hint or '—'}</li>")
        html_parts.append(f"<li>时长(ms): {s.duration_ms or '—'}</li>")
        html_parts.append("</ul>")

        html_parts.append("<h3>核心指标</h3><ul>")
        for k, v in report.summary_metrics.items():
            html_parts.append(f"<li>{self._esc(str(k))}: {self._esc(str(v))}</li>")
        html_parts.append("</ul>")

        html_parts.append("<h3>导出列与「未映射」说明</h3>")
        html_parts.append(
            "<p>PerfDog <code>Data_v4</code> 中含多类指标：<b>采样序号</b>（Num）、"
            "<b>多种时间戳</b>（time / absTime / monoTime）、<b>场景标签</b>（label、Notes）、"
            "<b>帧与卡顿相关</b>（InterFrame 等）、<b>应用/整机 CPU</b>、"
            "<b>各核频率与占用</b>（CPUClock*/CPUUsage*）、<b>GPU 占用与频率</b>、"
            "<b>电池温度/热状态</b>、<b>亮度与电量</b>、<b>电流电压功耗</b> 等。</p>"
            "<p>已在工具中<b>登记别名</b>的列会进入「核心指标」并参与洞察规则；"
            "其中 CPU/GPU 频点与占用等也会汇总进上方指标（若导出中存在）。</p>"
            "<p><b>「未映射列」</b>仅表示该列名尚未在别名表中登记，"
            "<b>数据仍已从 Excel 完整读入</b>，不是「分析不出来」；"
            "多为功耗细分、截图标记等，后续版本可继续扩展规则。</p>",
        )

        if report.stat_row_disclaimer:
            html_parts.append("<h3>数据脚注</h3>")
            html_parts.append(f"<p>{self._esc(report.stat_row_disclaimer)}</p>")

        html_parts.append("<h3>问题与洞察</h3>")
        for f in report.findings:
            tr = ""
            if f.time_start_ms is not None:
                tr = f"（约 {f.time_start_ms/1000:.2f}s"
                if f.time_end_ms is not None and f.time_end_ms != f.time_start_ms:
                    tr += f" ~ {f.time_end_ms/1000:.2f}s"
                tr += "）"
            html_parts.append(
                f"<h4>{self._esc(f.title)} <code>{self._esc(f.id)}</code>{tr}</h4>",
            )
            detail_html = self._esc(f.detail).replace("\n", "<br/>")
            html_parts.append(
                f"<p><b>{f.severity.value}</b> · {f.category.value}<br/>{detail_html}</p>",
            )

        html_parts.append("<h3>建议</h3><ul>")
        for r in report.recommendations:
            ids = ", ".join(r.finding_ids) if r.finding_ids else "—"
            html_parts.append(
                f"<li><b>{self._esc(r.category)}</b> [{self._esc(ids)}]: "
                f"{self._esc(r.text)}</li>",
            )
        html_parts.append("</ul>")

        if report.unrecognized_columns:
            html_parts.append("<h3>尚未登记别名的列名</h3>")
            html_parts.append("<p>")
            html_parts.append(self._esc(", ".join(report.unrecognized_columns[:60])))
            html_parts.append("</p>")

        self._browser.setHtml("".join(html_parts))

    def _render_joint_ui(self, data: dict) -> None:
        """将 joint model_dump 渲染到联合分析区（T048/T050）。"""
        parts: list[str] = []

        def ul(title: str, items: list[str]) -> None:
            parts.append(f"<h4>{self._esc(title)}</h4><ul>")
            for it in items:
                parts.append(f"<li>{self._esc(it)}</li>")
            parts.append("</ul>")

        ul("策略侧要点", list(data.get("policy_section") or []))
        ul("观测侧要点", list(data.get("observation_section") or []))
        ul("一致性 / 矛盾与启发式解读", list(data.get("consistency_section") or []))
        warns = list(data.get("warnings") or [])
        if warns:
            ul("警告与校验", warns)
        disc = (data.get("disclaimer") or "").strip()
        if disc:
            parts.append(f"<p><i>{self._esc(disc)}</i></p>")
        self._joint_browser.setHtml("".join(parts))

        self._bind_suggest_list.clear()
        self._freq_suggest_list.clear()
        for s in data.get("bindcore_suggestions") or []:
            it = QListWidgetItem(str(s.get("text", "")))
            it.setToolTip(str(s.get("basis", "")))
            self._bind_suggest_list.addItem(it)
        br = data.get("bindcore_insufficient_reason")
        if br and not (data.get("bindcore_suggestions") or []):
            it = QListWidgetItem(f"（数据不足）{br}")
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._bind_suggest_list.addItem(it)

        for s in data.get("freq_suggestions") or []:
            it = QListWidgetItem(str(s.get("text", "")))
            it.setToolTip(str(s.get("basis", "")))
            self._freq_suggest_list.addItem(it)
        fr = data.get("freq_insufficient_reason")
        if fr and not (data.get("freq_suggestions") or []):
            it = QListWidgetItem(f"（数据不足）{fr}")
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._freq_suggest_list.addItem(it)

    @staticmethod
    def _esc(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def _compose_export_markdown(self) -> str:
        """JA-FR-007 / T051：PerfDog 全文 + 空行 + 联合章节（base_report=None 避免重复会话摘要）。"""
        if self._report is None:
            return ""
        body = build_markdown(self._report)
        if self._joint_report is None:
            return body
        joint = JointAssessmentReport.model_validate(self._joint_report)
        return body + "\n\n" + build_joint_markdown(joint, base_report=None)

    def _on_joint_analyze(self) -> None:
        policy = self._context.get(_GP_JOINT_KEY)
        if not policy:
            QMessageBox.information(
                self,
                "联合分析",
                "请先在 **游戏性能配置** 中加载 gameperfconfig*.xml，并选择游戏与性能模式。",
            )
            return
        if self._report is None:
            QMessageBox.warning(self, "联合分析", "请先完成 PerfDog 文件分析。")
            return
        path = self._report.source_path
        if not path or not Path(path).is_file():
            QMessageBox.warning(self, "联合分析", "当前报告缺少有效的源文件路径，请重新分析。")
            return

        skip_warn = False
        pol_pkg = str((policy.get("package_name") or "")).strip()
        obs_pkg = str((self._report.session.package_name or "")).strip()
        if pol_pkg and obs_pkg and self._norm_pkg(pol_pkg) != self._norm_pkg(obs_pkg):
            r = QMessageBox.question(
                self,
                "包名不一致",
                f"游戏性能配置包名：{pol_pkg}\nPerfDog 会话包名：{obs_pkg}\n\n"
                "仍要继续联合分析吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                return
            skip_warn = True

        if self._joint_worker and self._joint_worker.isRunning():
            return
        self._joint_btn.setEnabled(False)
        self._import_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status_lbl.setText("联合分析中…")
        self._joint_worker = JointAssessmentWorker(
            path,
            policy,
            skip_package_warning=skip_warn,
            parent=self,
        )
        self._joint_worker.progress.connect(self._status_lbl.setText)
        self._joint_worker.joint_finished_ok.connect(self._on_joint_ok)
        self._joint_worker.joint_finished_err.connect(self._on_joint_err)
        self._joint_worker.finished.connect(self._on_joint_finished)
        self._joint_worker.start()

    def _on_joint_ok(self, payload: object) -> None:
        if isinstance(payload, dict):
            self._joint_report = payload
            self._render_joint_ui(payload)
        self._status_lbl.setText("联合分析完成")

    def _on_joint_err(self, message: str) -> None:
        self._status_lbl.setText("联合分析失败")
        QMessageBox.warning(self, "联合分析失败", message)

    def _on_joint_finished(self) -> None:
        self._progress.setVisible(False)
        self._browse_btn.setEnabled(True)
        p = self._path_edit.text().strip()
        self._import_btn.setEnabled(bool(p) and p != "未选择文件")
        if self._report is not None:
            self._joint_btn.setEnabled(True)

    def _on_clear(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(3000)
        if self._joint_worker and self._joint_worker.isRunning():
            self._joint_worker.requestInterruption()
            self._joint_worker.wait(3000)
        self._report = None
        self._last_good_report = None
        self._joint_report = None
        self._browser.clear()
        self._joint_browser.clear()
        self._bind_suggest_list.clear()
        self._freq_suggest_list.clear()
        self._path_edit.setText("未选择文件")
        self._export_btn.setEnabled(False)
        self._copy_btn.setEnabled(False)
        self._joint_btn.setEnabled(False)
        self._status_lbl.setText("")
        self._import_btn.setEnabled(False)

    def _on_export(self) -> None:
        if self._report is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Markdown 报告",
            "perfdog_report.md",
            "Markdown (*.md);;文本 (*.txt)",
        )
        if not path:
            return
        text = self._compose_export_markdown()
        try:
            Path(path).write_text(text, encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def _on_copy(self) -> None:
        if self._report is None:
            return
        QGuiApplication.clipboard().setText(self._compose_export_markdown())
