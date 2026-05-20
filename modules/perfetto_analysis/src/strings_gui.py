"""Perfetto 解析分析 — GUI 文案常量"""

from __future__ import annotations

from typing import Final

# ────────────────────────────────────────────────────────────────────────────
# Tab 信息
# ────────────────────────────────────────────────────────────────────────────

TAB_TITLE: Final = "Perfetto 分析"

# ────────────────────────────────────────────────────────────────────────────
# 分组标题 (QGroupBox)
# ────────────────────────────────────────────────────────────────────────────

GROUP_TRACE_FILE: Final = "Trace 文件"
GROUP_ANALYSIS_CONFIG: Final = "分析配置"
GROUP_ANALYSIS_RESULT: Final = "分析结果"

# ────────────────────────────────────────────────────────────────────────────
# 输入占位符
# ────────────────────────────────────────────────────────────────────────────

PLACEHOLDER_TRACE_FILE: Final = "选择或拖拽 .perfetto-trace 文件"
PLACEHOLDER_PROCESS: Final = "留空自动识别"
PLACEHOLDER_RESULT: Final = "分析完成后显示结果概览"

# ────────────────────────────────────────────────────────────────────────────
# 标签 (QLabel)
# ────────────────────────────────────────────────────────────────────────────

LABEL_TARGET_PROCESS: Final = "目标进程"
LABEL_APP_TYPE: Final = "App 类型"
LABEL_ANALYSIS_MODE: Final = "分析模式"
LABEL_STATUS_READY: Final = "● 就绪"
LABEL_STATUS_ANALYZING: Final = "● 分析中..."

# ────────────────────────────────────────────────────────────────────────────
# 按钮文字 (QPushButton)
# ────────────────────────────────────────────────────────────────────────────

BTN_BROWSE: Final = "浏览"
BTN_START_ANALYSIS: Final = "开始分析"
BTN_STOP: Final = "停止"

# ────────────────────────────────────────────────────────────────────────────
# 分析模式选项
# ────────────────────────────────────────────────────────────────────────────

MODE_ITEM_FULL: Final = "完整分析"
MODE_ITEM_PARSE: Final = "仅解析"
MODE_ITEM_DIMENSIONS: Final = "独立维度"

# ────────────────────────────────────────────────────────────────────────────
# 维度选择器
# ────────────────────────────────────────────────────────────────────────────

DIM_SELECTOR_ALL: Final = "全部维度 ▾"
DIM_SELECTOR_COUNT_FMT: Final = "{} 个维度 ▾"
DIM_SELECTOR_NONE: Final = "未选维度 ▾"

# 中文维度标签
DIM_LABEL_THREAD: Final = "线程"
DIM_LABEL_SUMMARY: Final = "整体"

# 菜单动作
BTN_SELECT_ALL: Final = "全选"
BTN_SELECT_NONE: Final = "全不选"

# ────────────────────────────────────────────────────────────────────────────
# 分析历史
# ────────────────────────────────────────────────────────────────────────────

LABEL_HISTORY_TITLE: Final = "📜 分析历史"
HISTORY_HEADER_TRACE: Final = "Trace"
HISTORY_HEADER_TARGET_PROCESS: Final = "目标进程"
HISTORY_HEADER_MODE: Final = "模式"
HISTORY_HEADER_TIME: Final = "时间"
HISTORY_HEADER_STATUS: Final = "状态"
HISTORY_HEADER_OPERATION: Final = "操作"

# ────────────────────────────────────────────────────────────────────────────
# 对话框
# ────────────────────────────────────────────────────────────────────────────

DLG_TITLE_SELECT_TRACE: Final = "选择 Trace 文件"
FILE_FILTER_PERFETTO_TRACE: Final = (
    "Perfetto Trace (*.perfetto-trace *.perfetto);;所有文件 (*)"
)

# ────────────────────────────────────────────────────────────────────────────
# Worker 消息
# ────────────────────────────────────────────────────────────────────────────

WORKER_ABORTED: Final = "分析已中止（已完成的数据已保留）"

# ────────────────────────────────────────────────────────────────────────────
# 分析结果文本
# ────────────────────────────────────────────────────────────────────────────

RESULT_TARGET_PROCESS_FMT: Final = "目标进程: {}"
RESULT_REPORT_PATH_FMT: Final = "报告路径: {}"
RESULT_JANK_TIMES_FMT: Final = "丢帧次数: {}"
RESULT_FRAME_NUM_FMT: Final = "总帧数: {}"
RESULT_REFRESH_RATE_FMT: Final = "刷新率: {}Hz"
RESULT_APP_TYPE_FMT: Final = "App 类型: {}"
RESULT_ELAPSED_FMT: Final = "分析耗时: {}s"
RESULT_DIMENSIONS_COMPLETED_FMT: Final = "\n维度完成: {}"
RESULT_DIMENSIONS_SKIPPED_FMT: Final = "维度跳过: {}"

# ────────────────────────────────────────────────────────────────────────────
# 模式标签映射
# ────────────────────────────────────────────────────────────────────────────

MODE_LABELS: Final = {
    "full": "完整",
    "parse": "仅解析",
    "dimensions": "独立维度",
}

# ────────────────────────────────────────────────────────────────────────────
# Tooltip
# ────────────────────────────────────────────────────────────────────────────

TOOLTIP_REGENERATE_REPORT: Final = "从数据库重新生成报告"
TOOLTIP_OPEN_REPORT: Final = "打开分析报告"
TOOLTIP_OPEN_REPORT_DIR: Final = "打开报告所在目录"
TOOLTIP_DELETE_REPORT: Final = "删除该分析报告"

# ────────────────────────────────────────────────────────────────────────────
# 日志输出
# ────────────────────────────────────────────────────────────────────────────

LOG_SELECT_TRACE_FIRST: Final = "请先选择 Trace 文件"
LOG_FILE_NOT_FOUND_FMT: Final = "文件不存在: {}"
LOG_SERVICE_NOT_INIT: Final = "服务未初始化"
LOG_SELECT_DIMENSION: Final = "请至少选择一个分析维度"
LOG_START_ANALYSIS_FMT: Final = "开始分析: {}"
LOG_STOPPING_ANALYSIS: Final = "正在停止分析..."
LOG_ANALYSIS_COMPLETE_FMT: Final = "✅ 分析完成 ({}s)"
LOG_ANALYSIS_FAILED_FMT: Final = "❌ 分析失败: {}"
LOG_REGENERATE_REPORT_FMT: Final = "重新生成报告: {}"
LOG_REGENERATE_FAIL: Final = "重新生成报告失败（数据库中可能无该 trace 数据）"
LOG_REPORT_NOT_FOUND: Final = "报告文件不存在"
LOG_OPEN_REPORT_FAIL_FMT: Final = "打开报告失败: {}"
LOG_REPORT_DIR_NOT_FOUND: Final = "报告目录不存在或未生成"
LOG_OPEN_DIR_FAIL_FMT: Final = "打开目录失败: {}"
LOG_DELETE_FILE_FAIL_FMT: Final = "删除文件失败: {}"
LOG_DELETED_FMT: Final = "已删除: {}"
LOG_DELETED_RECORD_FMT: Final = "已删除记录: {}"
LOG_DELETED_RECORD_KEEP_DIR: Final = "已删除记录（报告目录保留，其他模式仍在使用）"
LOG_DELETE_FILE_FAIL_FMT: Final = "删除文件失败: {}"

# ────────────────────────────────────────────────────────────────────────────
# Tooltip for dimension mode history items
# ────────────────────────────────────────────────────────────────────────────

MODE_DIMS_TIP_FMT: Final = "维度: {}"

# ────────────────────────────────────────────────────────────────────────────
# 日志内容关键词
# ────────────────────────────────────────────────────────────────────────────

FAILURE_KEYWORD: Final = "失败"