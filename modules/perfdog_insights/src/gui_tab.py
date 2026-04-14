"""PerfDog 分析 — GUI Tab（离线文件分析，不依赖 ADB）。"""

from __future__ import annotations

import html
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QGuiApplication
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from toolkit.gui.toolkit_dialog import warning_dialog

from toolkit.core.perfdog.config_defaults import REPORT_METHODS_AND_LIMITATIONS_ZH
from toolkit.core.perfdog.export_md import anomaly_chunk_to_tsv, format_finding_anomaly_period
from toolkit.core.perfdog.report_types import AnomalyDataChunk
from toolkit.gui.base_tab import BaseTab

from .analysis_worker import PerfDogAnalysisWorker
from .models import AnalysisReport
from .service import PerfdogInsightsService


class PerfdogInsightsTab(BaseTab):
    """PerfDog Excel 导入与报告展示。"""

    tab_title = "PerfDog分析"
    tab_icon = "📈"

    def __init__(self, context: dict | None = None, parent: QWidget | None = None) -> None:
        super().__init__(context, parent)
        self._context = context or {}
        raw_svc = self._context.get("pdi_service")
        self._service: PerfdogInsightsService = (
            raw_svc if isinstance(raw_svc, PerfdogInsightsService) else PerfdogInsightsService()
        )
        self._report: AnalysisReport | None = None
        self._worker: PerfDogAnalysisWorker | None = None
        self._last_good_report: AnalysisReport | None = None
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
        hint.setObjectName("fieldHint")
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
        actions.addWidget(self._export_btn)
        actions.addWidget(self._copy_btn)
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
            "导入 PerfDog 导出后，将在此显示会话摘要与异常洞察。",
        )
        inner_layout.addWidget(self._browser)

        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        self._browse_btn.clicked.connect(self._on_browse)
        self._import_btn.clicked.connect(self._on_import)
        self._clear_btn.clicked.connect(self._on_clear)
        self._export_btn.clicked.connect(self._on_export)
        self._copy_btn.clicked.connect(self._on_copy)

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
            warning_dialog(self, "格式不支持", "请拖入 .xlsx 或 .xlsm 文件。")
            event.ignore()

    def _set_selected_path(self, path: str) -> None:
        self._path_edit.setText(path)
        busy = self._worker and self._worker.isRunning()
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
            warning_dialog(self, "文件无效", "所选路径不是有效文件。")
            return

        self._start_worker(path)

    def _start_worker(self, path: str) -> None:
        if self._worker and self._worker.isRunning():
            return
        self._browse_btn.setEnabled(False)
        self._import_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status_lbl.setText("解析中…")
        self._worker = PerfDogAnalysisWorker(path, self._service, self)
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
        self._status_lbl.setText("解析完成")

    def _on_worker_err(self, message: str) -> None:
        self._status_lbl.setText("解析失败")
        warning_dialog(self, "解析失败", message)
        # FR-009：不覆盖上一份成功结果
        if self._last_good_report is not None:
            self._report = self._last_good_report
            self._render_report(self._last_good_report)

    def _on_worker_finished(self) -> None:
        self._progress.setVisible(False)
        self._browse_btn.setEnabled(True)
        p = self._path_edit.text().strip()
        self._import_btn.setEnabled(bool(p) and p != "未选择文件")

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
            period = format_finding_anomaly_period(f)
            if period:
                html_parts.append(
                    f"<p><b>异常时间段</b>：{self._esc(period)}</p>",
                )
            detail_html = self._esc(f.detail).replace("\n", "<br/>")
            html_parts.append(
                f"<p><b>{f.severity.value}</b> · {f.category.value}<br/>{detail_html}</p>",
            )
            ev = f.evidence or {}
            comp = ev.get("freq_gpu_window_vs_global")
            if isinstance(comp, dict) and comp:
                html_parts.append("<p><b>频点/GPU（异常窗 vs 全段均值）</b><ul>")
                for col, pair in comp.items():
                    g, w = pair
                    html_parts.append(
                        f"<li>{self._esc(str(col))}: 全段≈{g}，窗内≈{w}</li>",
                    )
                html_parts.append("</ul></p>")
            tt = ev.get("thread_top_in_window")
            if isinstance(tt, list) and tt:
                html_parts.append("<p><b>该窗线程 Top</b><ul>")
                for row in tt[:8]:
                    if not isinstance(row, dict):
                        continue
                    html_parts.append(
                        "<li>"
                        f"{self._esc(str(row.get('thread', '')))}: "
                        f"均值 {row.get('mean_pct', '')}% "
                        f"峰值 {row.get('peak_pct', '')}%"
                        "</li>",
                    )
                html_parts.append("</ul></p>")

        if report.frame_stats and report.frame_stats.count:
            fs = report.frame_stats
            html_parts.append("<h3>帧级（@FrameInfo）</h3><ul>")
            html_parts.append(
                f"<li>帧数 {fs.count}；均值 {fs.mean_ms:.2f} ms；"
                f"p99 {fs.p99_ms:.2f} ms；最大 {fs.max_ms:.2f} ms</li>",
            )
            html_parts.append(f"<li>超 2×预算帧数: {fs.over_budget_count}</li>")
            if fs.max_frame_at_ms is not None:
                html_parts.append(
                    f"<li>最大帧时刻（相对）: {fs.max_frame_at_ms/1000:.2f} s</li>",
                )
            html_parts.append("</ul>")

        chfi = report.frameinfo_window_chunk
        if chfi is not None and chfi.rows:
            html_parts.append("<h3>帧级异常关联采样（@FrameInfo）</h3>")
            html_parts.append(
                "<p>最大帧耗时附近逐帧行（<b>time</b> ∈ "
                f"[{chfi.time_lo_ms:.1f}, {chfi.time_hi_ms:.1f}] ms，"
                f"共 <b>{len(chfi.rows)}</b> 行；非全量帧表。</p>",
            )
            html_parts.append(
                f"<h4><code>{self._esc(chfi.finding_id)}</code> "
                f"{self._esc(chfi.finding_title)}</h4>",
            )
            self._html_anomaly_chunk_detail(html_parts, chfi)
            tsv = anomaly_chunk_to_tsv(chfi)
            html_parts.append(
                '<pre style="white-space:pre;overflow:auto;max-height:360px;font-size:10px;line-height:1.2">',
            )
            html_parts.append(html.escape(tsv, quote=False))
            html_parts.append("</pre>")

        html_parts.append("<h3>关联分析（线程 / 频点）</h3>")
        if not report.has_thread_cpu_sheet:
            html_parts.append(
                "<p><i>本导出未包含 <code>@ThreadCpuUsageData</code> 工作表，"
                "线程级关联分析<b>不可用</b>；仍可根据 Data_v4 在洞察中附频点/GPU 窗内对比（若列存在）。</i></p>",
            )
        elif not report.thread_top and not any(
            (x.evidence or {}).get("thread_top_in_window") for x in report.findings
        ):
            html_parts.append(
                "<p><i>已检测到线程 CPU 表，但当前无可对齐的异常时间窗或有效采样，"
                "未生成线程 Top 列表。</i></p>",
            )
        else:
            if report.thread_top:
                html_parts.append("<p><b>异常窗内线程 Top（汇总）</b></p><ul>")
                for e in report.thread_top:
                    html_parts.append(
                        f"<li>{self._esc(e.thread_label)}: "
                        f"窗内均值 {e.mean_pct_in_window:.2f}%，"
                        f"峰值 {e.peak_pct_in_window:.2f}%</li>",
                    )
                html_parts.append("</ul>")

        html_parts.append("<h3>异常关联采样（Data_v4）</h3>")
        if report.anomaly_data_chunks:
            html_parts.append(
                "<p>各段为 <code>time_ms</code> 落在「异常时间段」± "
                f"<b>{report.anomaly_sample_pad_ms}</b> ms 内的秒级采样（制表符分隔）；"
                "其余时段不逐行展开。</p>",
            )
            for ch in report.anomaly_data_chunks:
                html_parts.append(
                    f"<h4><code>{self._esc(ch.finding_id)}</code> "
                    f"{self._esc(ch.finding_title)}</h4>",
                )
                self._html_anomaly_chunk_detail(html_parts, ch)
                tsv = anomaly_chunk_to_tsv(ch)
                if not tsv:
                    html_parts.append("<p>（该时间窗内无秒级采样点。）</p>")
                else:
                    html_parts.append(
                        '<pre style="white-space:pre;overflow:auto;max-height:360px;font-size:10px;line-height:1.2">',
                    )
                    html_parts.append(html.escape(tsv, quote=False))
                    html_parts.append("</pre>")
        else:
            html_parts.append(
                "<p>（当前无带「异常时间段」的洞察，或 Data_v4 中无匹配采样行。）</p>",
            )

        html_parts.append("<h3>其余时段说明</h3>")
        na = (report.non_anomaly_summary_zh or "").strip() or "（无）"
        html_parts.append(f"<p>{self._esc(na)}</p>")

        if report.unrecognized_columns:
            html_parts.append("<h3>尚未登记别名的列名</h3>")
            html_parts.append("<p>")
            html_parts.append(self._esc(", ".join(report.unrecognized_columns[:60])))
            html_parts.append("</p>")

        html_parts.append("<h3>方法与局限性</h3>")
        for para in REPORT_METHODS_AND_LIMITATIONS_ZH.strip().split("\n\n"):
            p = para.strip()
            if p:
                html_parts.append(f"<p>{self._esc(p)}</p>")

        self._browser.setHtml("".join(html_parts))

    def _html_anomaly_chunk_detail(self, html_parts: list[str], ch: AnomalyDataChunk) -> None:
        """墙钟、时间窗、CPU/GPU/各核、线程 Top（与 export_md 并列）。"""
        if ch.wall_clock_zh:
            html_parts.append(f"<p><b>墙钟时间</b>：{self._esc(ch.wall_clock_zh)}</p>")
        html_parts.append(
            "<p><b>截取相对时间窗（ms）</b>："
            f"{ch.time_lo_ms:.1f} ~ {ch.time_hi_ms:.1f}</p>",
        )
        if (
            ch.metrics_time_lo_ms is not None
            and ch.metrics_time_hi_ms is not None
            and (
                abs(ch.metrics_time_lo_ms - ch.time_lo_ms) > 0.5
                or abs(ch.metrics_time_hi_ms - ch.time_hi_ms) > 0.5
            )
        ):
            html_parts.append(
                "<p><b>对齐 Data_v4 指标窗（ms）</b>："
                f"{ch.metrics_time_lo_ms:.1f} ~ {ch.metrics_time_hi_ms:.1f}</p>",
            )
        html_parts.append("<p><b>窗内资源摘要</b></p><ul>")
        for s in ch.resource_summary_zh:
            html_parts.append(f"<li>{self._esc(s)}</li>")
        html_parts.append("</ul>")
        html_parts.append("<p><b>线程 CPU Top（@ThreadCpuUsageData）</b></p><ul>")
        for s in ch.thread_summary_zh:
            html_parts.append(f"<li>{self._esc(s)}</li>")
        html_parts.append("</ul>")

    @staticmethod
    def _esc(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def _compose_export_markdown(self) -> str:
        if self._report is None:
            return ""
        return self._service.compose_export_markdown(self._report)

    def _on_clear(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(3000)
        self._report = None
        self._last_good_report = None
        self._browser.clear()
        self._path_edit.setText("未选择文件")
        self._export_btn.setEnabled(False)
        self._copy_btn.setEnabled(False)
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
            warning_dialog(self, "导出失败", str(e))

    def _on_copy(self) -> None:
        if self._report is None:
            return
        QGuiApplication.clipboard().setText(self._compose_export_markdown())
