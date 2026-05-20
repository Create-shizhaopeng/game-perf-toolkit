"""Perfetto 抓取模块 — GUI 文案常量"""

from __future__ import annotations

from typing import Final

# ────────────────────────────────────────────────────────────────────────────
# 模块信息
# ────────────────────────────────────────────────────────────────────────────

MODULE_DOC_FMT: Final = "Perfetto 抓取模块 — GUI 页面（方案 A：{}）"

# ────────────────────────────────────────────────────────────────────────────
# Tab 标题
# ────────────────────────────────────────────────────────────────────────────

TAB_TITLE: Final = "Perfetto 抓取"

# ────────────────────────────────────────────────────────────────────────────
# 分组标题 (QGroupBox)
# ────────────────────────────────────────────────────────────────────────────

GROUP_CAPTURE_CONFIG: Final = "⚙ 抓取配置"
GROUP_ATRACE_CATEGORIES: Final = "📦 Atrace Categories"
GROUP_FTRACE_EVENTS: Final = "🔧 Ftrace Events"
GROUP_JANK_MONITOR: Final = "📊 Jank 监控"
GROUP_SESSION_STATUS: Final = "📊 会话状态"

# ────────────────────────────────────────────────────────────────────────────
# 标签 (QLabel / 状态栏)
# ────────────────────────────────────────────────────────────────────────────

LABEL_DURATION: Final = "Duration"
LABEL_SECONDS: Final = "秒"
LABEL_BUFFER: Final = "Buffer"
LABEL_KB: Final = "KB"
LABEL_SAVED_COUNT: Final = "已保存"
LABEL_SEGMENTS: Final = "段"
LABEL_TIMER: Final = "时长"
LABEL_DEVICE: Final = "设备"
LABEL_STATUS_READY_EMOJI: Final = "🟢 就绪"
LABEL_STATUS_CAPTURING: Final = "⏺ 抓取中"
LABEL_STATUS_WAIT_RECONNECT: Final = "🟡 等待重连"
LABEL_STATUS_DEVICE_DISCONNECTED: Final = "🔴 设备断开"
LABEL_STATUS: Final = "状态"
LABEL_SAVED_DEFAULT_FMT: Final = "已保存: 0 段"
LABEL_TIMER_DEFAULT_FMT: Final = "时长: --:--"
LABEL_DEVICE_DEFAULT: Final = "设备: --"

# ────────────────────────────────────────────────────────────────────────────
# 复选框文字 (QCheckBox)
# ────────────────────────────────────────────────────────────────────────────

CHECK_MANUAL_BUFFER: Final = "手动设置 Buffer"
CHECK_FTRACE_CUSTOM: Final = "启用 Ftrace 自定义"
CHECK_JANK_MONITOR: Final = "启用 Jank 检测"

# ────────────────────────────────────────────────────────────────────────────
# 按钮文字 (QPushButton)
# ────────────────────────────────────────────────────────────────────────────

BTN_IMPORT_CONFIG: Final = "📂 导入配置"
BTN_START: Final = "▶ 开始"
BTN_CAPTURING: Final = "⏸ 抓取中"
BTN_SAVE: Final = "💾 保存"
BTN_STOP: Final = "⏹ 停止"
BTN_ABANDON: Final = "❌ 放弃会话"

# ────────────────────────────────────────────────────────────────────────────
# Tooltip
# ────────────────────────────────────────────────────────────────────────────

TOOLTIP_IMPORT_CONFIG: Final = "选择 JSON 配置文件导入"

# ────────────────────────────────────────────────────────────────────────────
# 对话框标题 (QFileDialog / warning_dialog)
# ────────────────────────────────────────────────────────────────────────────

DLG_TITLE_SELECT_CONFIG: Final = "选择配置文件"
DLG_TITLE_EXPORT_FPS: Final = "导出帧率数据"
DLG_TITLE_JANK_SELECT_APP: Final = "提示"
DLG_TITLE_JANK_MSG_SELECT_APP: Final = "已启用 Jank 检测，请先选择监控应用"

# ────────────────────────────────────────────────────────────────────────────
# 文件过滤器 (QFileDialog)
# ────────────────────────────────────────────────────────────────────────────

FILE_FILTER_JSON: Final = "JSON 配置 (*.json);;所有文件 (*)"
FILE_FILTER_EXCEL: Final = "Excel 文件 (*.xlsx)"

# ────────────────────────────────────────────────────────────────────────────
# 历史 Tab 名称
# ────────────────────────────────────────────────────────────────────────────

TAB_HISTORY_CAPTURE: Final = "抓取历史"
TAB_HISTORY_ANALYSIS: Final = "分析历史"

# ────────────────────────────────────────────────────────────────────────────
# Worker 线程信号消息
# ────────────────────────────────────────────────────────────────────────────

WORKER_CAPTURE_STARTED: Final = "▶ 抓取已开始"
WORKER_SAVED_FMT: Final = "💾 已保存第 {} 段 trace"
WORKER_EXPORTED_FMT: Final = "■ 会话结束，已导出 {} 个文件"
WORKER_CAPTURE_RESUMED: Final = "▶ 抓取已恢复"

# ────────────────────────────────────────────────────────────────────────────
# Jank 监控相关
# ────────────────────────────────────────────────────────────────────────────

JANK_CONNECT_DEVICE_FIRST: Final = "⚠ 请先连接设备"
JANK_NO_APP_WARNING: Final = "⚠ Jank 监控未启动：请先选择监控应用"
JANK_MONITOR_STARTED_FMT: Final = "▶ 开始监控: {}"
JANK_DURATION_LIMIT_FMT: Final = "⏱ 监控时长上限: {} 小时"
JANK_PAUSE_JUDGMENT: Final = "⏸ 已暂停 Jank 判定"
JANK_RESUME_JUDGMENT: Final = "▶ 已恢复 Jank 判定"
JANK_NO_DATA: Final = "⚠ 监控未运行，无数据可导出"
JANK_EXPORTED_FMT: Final = "✓ 已导出: {}"
JANK_EXPORT_NOT_IMPLEMENTED: Final = "⚠ 导出功能尚未实现"
JANK_EXPORT_FAIL_FMT: Final = "✗ 导出失败: {}"
JANK_MONITOR_STOPPED: Final = "■ Jank 监控已停止"
JANK_DURATION_EXCEEDED: Final = "⏱ 已达到最大监控时长，自动停止"
JANK_TRIGGERED_FMT: Final = "⚠ Jank 触发: {} 帧, 平均帧耗时 {}ms"
JANK_APP_FOREGROUND: Final = "📱 应用回到前台"
JANK_APP_BACKGROUND: Final = "📱 应用切到后台"
JANK_STATUS_FMT: Final = "📊 Jank 状态: {}"
JANK_AUTO_SAVE: Final = "📦 Jank 检测触发，自动保存 trace..."

# ────────────────────────────────────────────────────────────────────────────
# 状态变迁标签
# ────────────────────────────────────────────────────────────────────────────

STATE_LABELS: Final = {
    "IDLE": "就绪",
    "MONITORING": "监控中",
    "TRIGGERED": "已触发",
    "STABILIZING": "稳定中",
    "SAVING": "保存中",
    "PAUSED": "已暂停",
    "COMPLETED": "已完成",
    "ERROR": "错误",
}

# ────────────────────────────────────────────────────────────────────────────
# 日志输出 (通过 _log)
# ────────────────────────────────────────────────────────────────────────────

LOG_STARTING: Final = "正在启动 Perfetto 抓取..."
LOG_ATRACE_FMT: Final = "  Atrace: {}"
LOG_FTRACE_FMT: Final = "  Ftrace: {}"
LOG_BUFFER_FMT: Final = "  Buffer: {} KB ({}) | Duration: {}s"
LOG_BUFF_LABEL_MANUAL: Final = "手动"
LOG_BUFF_LABEL_AUTO: Final = "自动"
LOG_CAPTURE_STARTED_FMT: Final = "✓ Perfetto 后台抓取已启动{}"
LOG_CAPTURE_MODE_SNAPSHOT: Final = " [快照模式]"
LOG_CAPTURE_MODE_AUTO_BUFFER: Final = " [自动缓冲模式]"
LOG_GET_DEVICE_DIR_FAIL_FMT: Final = "✗ 获取设备目录失败: {}"
LOG_SAVE_TRACE_SEGMENT: Final = "保存当前 trace 段..."
LOG_SAVED_FMT: Final = "✓ 第 {} 段已保存"
LOG_STOP_AND_EXPORT: Final = "停止抓取，导出 trace..."
LOG_EXPORTED_FMT: Final = "✓ 已导出 {} 个文件:"
LOG_OPEN_EXPORT_DIR_FMT: Final = "📂 已打开导出目录: {}"
LOG_NO_VALID_TRACE: Final = "本次抓取未保存有效 trace"
LOG_DEVICE_UNAVAILABLE: Final = "设备不可用"
LOG_DEVICE_DISCONNECT_WARNING: Final = "⚠ 设备断开！已保存的 trace 保留在设备上，等待自动重连..."
LOG_DEVICE_RECONNECTED: Final = "✓ 设备已重连，正在恢复抓取..."
LOG_SERVICE_UNAVAILABLE: Final = "✗ 服务或设备不可用，无法恢复"
LOG_RECONNECT_FAIL_FMT: Final = "✗ 恢复抓取失败: {}"
LOG_RECONNECT_HINT: Final = "请点击「放弃会话」后重新开始"
LOG_SESSION_ABANDONED: Final = "会话已放弃"
LOG_CANNOT_READ_DEVICE: Final = "⚠ 无法读取设备详细信息，已使用默认值"
LOG_SVC_NOT_INIT: Final = "✗ 服务未初始化"
LOG_NO_DEVICE: Final = "✗ 未检测到设备"
LOG_NO_DEVICE_INFO: Final = "✗ 设备信息未获取，无法保存"
LOG_CONFIG_IMPORTED_FMT: Final = "✓ 已导入配置: {}"
LOG_CONFIG_LOAD_FAIL_FMT: Final = "✗ 加载配置失败: {}"
LOG_SVC_NOT_INIT_HISTORY: Final = "历史服务未就绪"
LOG_FILE_EXISTS_FMT: Final = "文件已存在: {}"
LOG_IMPORTED_FMT: Final = "已导入: {}"
LOG_IMPORT_FAIL_FMT: Final = "导入失败: {}"
LOG_PATH_NOT_FOUND_FMT: Final = "路径不存在: {}"
LOG_SENT_TO_AGENT_FMT: Final = "已发送到 Agent: {}"
LOG_SEND_AGENT_FAIL_FMT: Final = "发送到 Agent 失败: {}"
LOG_SERVICE_NOT_INIT_HISTORY_2: Final = "历史服务未初始化"
LOG_CLEANUP_FMT: Final = "已清理 {} 个过期会话"
LOG_NO_EXPIRED_SESSIONS: Final = "没有需要清理的过期会话"
LOG_REQUEST_ANALYSIS_FMT: Final = "已请求分析: {}"
LOG_SEND_ANALYSIS_FAIL_FMT: Final = "发送分析请求失败: {}"
LOG_ANALYSIS_STATUS_FMT: Final = "分析状态: {} — {}"
LOG_REPORT_OPENED_FMT: Final = "📄 报告已生成并打开: {}"
LOG_REPORT_NOT_GENERATED: Final = "分析完成，但未生成报告"
LOG_SAVE_RECORD_FAIL_FMT: Final = "保存分析记录失败: {}"
LOG_ANALYSIS_FAILED_FMT: Final = "❌ 分析失败: {}"
LOG_FILE_NOT_EXISTS_FMT: Final = "报告文件不存在: {}"
LOG_FILE_NOT_FOUND_FMT: Final = "文件不存在: {}"
LOG_SESSION_DELETED_FMT: Final = "已删除会话: {}"
LOG_SESSION_DELETE_FAIL_FMT: Final = "删除会话失败: {}"
LOG_TRACE_DELETED_FMT: Final = "已删除: {}"
LOG_TRACE_DELETE_FAIL_FMT: Final = "删除失败: {}"
LOG_ANALYSIS_RECORD_DELETED: Final = "已删除分析记录"
LOG_ANALYSIS_RECORD_DELETE_FAIL: Final = "删除分析记录失败"
LOG_ANALYSIS_RECORD_DELETE_FAIL_FMT: Final = "删除分析记录失败: {}"

# ────────────────────────────────────────────────────────────────────────────
# 取消操作
# ────────────────────────────────────────────────────────────────────────────

CANCEL_ANALYSIS_REQUEST: Final = "取消分析请求"

# ────────────────────────────────────────────────────────────────────────────
# AI 聊天消息
# ────────────────────────────────────────────────────────────────────────────

CHAT_SELECT_TRACE_FIRST: Final = "请先在左侧选择 trace 文件"
CHAT_ENGINE_NOT_READY: Final = "分析引擎未就绪，请确认 perfetto_analysis 模块已加载"
CHAT_ANALYSIS_COMPLETE: Final = "分析完成，但未生成报告"
CHAT_REPORT_OPENED_FMT: Final = "📄 报告已生成并打开: {}"
CHAT_ANALYSIS_FAILED_FMT: Final = "❌ 分析失败: {}"
CHAT_SELECT_SOP_DESC: Final = "描述你的任务..."

# ────────────────────────────────────────────────────────────────────────────
# Agent SOP 相关
# ────────────────────────────────────────────────────────────────────────────

SOP_SAVE_NEW: Final = "保存为新 SOP"
SOP_SKIP: Final = "跳过"
SOP_SAVING: Final = "SOP 保存中..."
SOP_SKIPPED: Final = "已跳过"
SOP_WORKFLOW_INSIGHTS: Final = "💡 工作流沉淀"
SOP_TOOLS_USED_FMT: Final = "工具: {}"
SOP_DEVIATION_FMT: Final = "偏差: {}"
SOP_WORKFLOW_FMT: Final = "📋 工作流: {}"
SOP_SAVE_HINT: Final = "本次对话使用了 {} 个工具，存在 {} 处偏差"

# ────────────────────────────────────────────────────────────────────────────
# Agent 设置对话框
# ────────────────────────────────────────────────────────────────────────────

AGENT_SETTINGS_TITLE: Final = "⚙ Agent 设置"
AGENT_SETTINGS_SOP_TAB: Final = "SOP 管理"
AGENT_SETTINGS_MCP_TAB: Final = "MCP 管理"
AGENT_SETTINGS_ADVANCED_TAB: Final = "高级设置"
AGENT_SETTINGS_SAVE: Final = "保存"
AGENT_SETTINGS_CANCEL: Final = "取消"
AGENT_SETTINGS_PROVIDER_GLM: Final = "GLM (智谱)"
AGENT_SETTINGS_MODEL: Final = "模型"
AGENT_SETTINGS_LANGUAGE: Final = "回复语言"
AGENT_SETTINGS_LANG_CHINESE: Final = "中文"
AGENT_SETTINGS_LANG_ENGLISH: Final = "English"
AGENT_SETTINGS_SMART_SWITCH: Final = "智能切换: 复杂任务自动使用 Claude"
AGENT_SETTINGS_IMPORT_SOP: Final = "📥 导入 SOP"

# ────────────────────────────────────────────────────────────────────────────
# MCP 设置
# ────────────────────────────────────────────────────────────────────────────

MCP_SERVER: Final = "服务器"
MCP_STATUS: Final = "状态"
MCP_TOOL_COUNT: Final = "工具数"
MCP_NOT_CONNECTED: Final = "未连接"
MCP_ENABLED: Final = "已启用"
MCP_DISABLED: Final = "已禁用"
MCP_ADD: Final = "➕ 添加"
MCP_REMOVE: Final = "🗑 移除"
MCP_TOGGLE: Final = "⏯ 启用/禁用"
MCP_SDK_NOT_INSTALLED: Final = "MCP SDK 未安装"
MCP_DIALOG_TITLE: Final = "添加 MCP 服务器"
MCP_NAME_LABEL: Final = "服务器名称:"
MCP_COMMAND_LABEL: Final = "启动命令 (如 python):"
MCP_ARGS_LABEL: Final = "参数 (空格分隔):"

# ────────────────────────────────────────────────────────────────────────────
# 其他
# ────────────────────────────────────────────────────────────────────────────

HISTORY_CLOSE_HINT: Final = "历史面板关闭按钮 — 保留兼容，当前无操作。"
CONFIG_IMPORT_SUCCESS: Final = "配置导入成功"
CONFIG_IMPORT_FAIL: Final = "配置导入失败"
CONFIG_EXPORT_SUCCESS: Final = "配置导出成功"
