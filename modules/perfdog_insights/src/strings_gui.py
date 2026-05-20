"""PerfDog 分析 — GUI 文案常量"""

from __future__ import annotations

from typing import Final

# ────────────────────────────────────────────────────────────────────────────
# Tab 信息
# ────────────────────────────────────────────────────────────────────────────

TAB_TITLE: Final = "PerfDog分析"

# ────────────────────────────────────────────────────────────────────────────
# 拖拽区域
# ────────────────────────────────────────────────────────────────────────────

LABEL_PERFDOG_EXPORT: Final = "PerfDog 导出"
HINT_DRAG_DROP: Final = "拖拽 .xlsx / .xlsm，或使用「选择文件」"

# ────────────────────────────────────────────────────────────────────────────
# 状态与路径
# ────────────────────────────────────────────────────────────────────────────

LABEL_NO_FILE_SELECTED: Final = "未选择文件"
LABEL_PARSING: Final = "解析中…"
LABEL_PARSE_COMPLETE: Final = "解析完成"
LABEL_PARSE_FAILED: Final = "解析失败"

# ────────────────────────────────────────────────────────────────────────────
# 按钮
# ────────────────────────────────────────────────────────────────────────────

BTN_SELECT_FILE: Final = "选择文件…"
BTN_START_ANALYSIS: Final = "开始分析"
BTN_CLEAR_ANALYSIS: Final = "清除当前分析"
BTN_EXPORT_REPORT: Final = "导出报告…"
BTN_COPY_REPORT: Final = "复制报告"

# ────────────────────────────────────────────────────────────────────────────
# 对话框
# ────────────────────────────────────────────────────────────────────────────

DLG_TITLE_UNSUPPORTED_FORMAT: Final = "格式不支持"
DLG_MSG_UNSUPPORTED_FORMAT: Final = "请拖入 .xlsx 或 .xlsm 文件。"
DLG_TITLE_SELECT_FILE: Final = "选择 PerfDog 导出"
FILE_FILTER_EXCEL: Final = "Excel (*.xlsx *.xlsm)"
DLG_TITLE_INVALID_FILE: Final = "文件无效"
DLG_MSG_INVALID_FILE: Final = "所选路径不是有效文件。"
DLG_TITLE_PARSE_FAILED: Final = "解析失败"
DLG_TITLE_EXPORT_REPORT: Final = "导出 Markdown 报告"
DLG_FILE_FILTER_MD: Final = "Markdown (*.md);;文本 (*.txt)"
DLG_DEFAULT_EXPORT_NAME: Final = "perfdog_report.md"
DLG_TITLE_EXPORT_FAIL: Final = "导出失败"

# ────────────────────────────────────────────────────────────────────────────
# 浏览器占位文字
# ────────────────────────────────────────────────────────────────────────────

PLACEHOLDER_BROWSER: Final = (
    "导入 PerfDog 导出后，将在此显示会话摘要与异常洞察。"
)

# ────────────────────────────────────────────────────────────────────────────
# 报告 HTML 区块标题
# ────────────────────────────────────────────────────────────────────────────

REPORT_SESSION_SUMMARY: Final = "会话摘要"
REPORT_PACKAGE_NAME: Final = "包名"
REPORT_DEVICE: Final = "设备"
REPORT_TARGET_FPS: Final = "推断目标帧率"
REPORT_DURATION_MS: Final = "时长(ms)"
REPORT_CORE_METRICS: Final = "核心指标"
REPORT_UNMAPPED_COLUMNS_GUIDE: Final = "导出列与「未映射」说明"
REPORT_UNMAPPED_NOTE_1: Final = (
    'PerfDog <code>Data_v4</code> 中含多类指标：<b>采样序号</b>（Num）、'
    '<b>多种时间戳</b>（time / absTime / monoTime）、<b>场景标签</b>（label、Notes）、'
    '<b>帧与卡顿相关</b>（InterFrame 等）、<b>应用/整机 CPU</b>、'
    '<b>各核频率与占用</b>（CPUClock*/CPUUsage*）、<b>GPU 占用与频率</b>、'
    '<b>电池温度/热状态</b>、<b>亮度与电量</b>、<b>电流电压功耗</b> 等。'
)
REPORT_UNMAPPED_NOTE_2: Final = (
    "已在工具中<b>登记别名</b>的列会进入「核心指标」并参与洞察规则；"
    "其中 CPU/GPU 频点与占用等也会汇总进上方指标（若导出中存在）。"
)
REPORT_UNMAPPED_NOTE_3: Final = (
    '<b>「未映射列」</b>仅表示该列名尚未在别名表中登记，'
    '<b>数据仍已从 Excel 完整读入</b>，不是「分析不出来」；'
    "多为功耗细分、截图标记等，后续版本可继续扩展规则。"
)
REPORT_NOT_RECOGNIZED: Final = "（未识别）"
REPORT_NO_DATA: Final = "—"
REPORT_FOOTNOTE: Final = "数据脚注"
REPORT_FINDINGS: Final = "问题与洞察"
REPORT_ANOMALY_PERIOD: Final = "异常时间段"
REPORT_SEVERITY: Final = "严重等级"
REPORT_CATEGORY: Final = "类别"
REPORT_FREQ_GPU_COMPARISON: Final = "频点/GPU（异常窗 vs 全段均值）"
REPORT_THREAD_TOP_IN_WINDOW: Final = "该窗线程 Top"
REPORT_FRAME_STATS: Final = "帧级（@FrameInfo）"
REPORT_FRAME_INFO: Final = "帧级异常关联采样（@FrameInfo）"
REPORT_RELATED_ANALYSIS: Final = "关联分析（线程 / 频点）"
REPORT_NO_THREAD_CPU_SHEET: Final = (
    "本导出未包含 <code>@ThreadCpuUsageData</code> 工作表，"
    "线程级关联分析<b>不可用</b>；仍可根据 Data_v4 在洞察中附频点/GPU 窗内对比（若列存在）。"
)
REPORT_THREAD_NO_WINDOW: Final = (
    "已检测到线程 CPU 表，但当前无可对齐的异常时间窗或有效采样，"
    "未生成线程 Top 列表。"
)
REPORT_THREAD_TOP_SUMMARY: Final = "异常窗内线程 Top（汇总）"
REPORT_ANOMALY_DATA: Final = "异常关联采样（Data_v4）"
REPORT_ANOMALY_DATA_INTRO_FMT: Final = (
    "各段为 <code>time_ms</code> 落在「异常时间段」± "
    "<b>{}</b> ms 内的秒级采样（制表符分隔）；"
    "其余时段不逐行展开。"
)
REPORT_NO_ANOMALY: Final = "（当前无带「异常时间段」的洞察，或 Data_v4 中无匹配采样行。）"
REPORT_OTHER_PERIODS: Final = "其余时段说明"
REPORT_NO_OTHER_PERIODS: Final = "（无）"
REPORT_UNRECOGNIZED_COLUMNS: Final = "尚未登记别名的列名"
REPORT_METHODS_AND_LIMITATIONS: Final = "方法与局限性"
REPORT_NO_ROWS_IN_WINDOW: Final = "（该时间窗内无秒级采样点。）"

# ────────────────────────────────────────────────────────────────────────────
# 异常区块详情标签
# ────────────────────────────────────────────────────────────────────────────

CHUNK_WALL_CLOCK: Final = "墙钟时间"
CHUNK_TIME_WINDOW: Final = "截取相对时间窗（ms）"
CHUNK_ALIGNED_METRICS_WINDOW: Final = "对齐 Data_v4 指标窗（ms）"
CHUNK_RESOURCE_SUMMARY: Final = "窗内资源摘要"
CHUNK_THREAD_CPU_TOP: Final = "线程 CPU Top（@ThreadCpuUsageData）"