from __future__ import annotations

from typing import Final


# ── MainWindow ──

MAIN_WINDOW_STATUS_READY: Final = "就绪"
MAIN_WINDOW_STATUS_CONNECTED_FMT: Final = "已连接: {device}"
MAIN_WINDOW_STATUS_MULTIPLE_FMT: Final = "{count} 台设备已连接"
MAIN_WINDOW_STATUS_NO_DEVICE: Final = "未连接设备"
MAIN_WINDOW_STATUS_DISGUISED: Final = "已伪装"
MAIN_WINDOW_STATUS_NOT_DISGUISED: Final = "未伪装"
MAIN_WINDOW_STATUS_DISGUISED_FMT: Final = "已连接: {serial} ({disguise})"
MAIN_WINDOW_LLM_DEGRADED_FMT: Final = "⚠ LLM 已降级: {from_provider} → {to_provider}"
MAIN_WINDOW_BUDGET_ALERT_TITLE: Final = "Token 预算告警"
MAIN_WINDOW_BUDGET_ALERT_MSG_FMT: Final = "当前会话 Token 用量已达预算的 {pct}%。\n\n是否继续后续请求？"
MAIN_WINDOW_BUDGET_CONTINUE: Final = "继续"


# ── HomeTab ──

HOME_TAB_TITLE: Final = "首页"
HOME_WELCOME: Final = "欢迎使用 Game Toolkit"
HOME_SUBTITLE: Final = "游戏开发测试工具集 — 集成设备管理、性能分析、日志分析等能力"
HOME_CARD_DEVICE: Final = "设备状态"
HOME_CARD_MODULES: Final = "已加载模块"
HOME_CARD_DATABASE: Final = "数据库"
HOME_CARD_THEME: Final = "当前主题"
HOME_STATUS_DISCONNECTED: Final = "未连接"
HOME_STATUS_READY: Final = "就绪"
HOME_STATUS_DARK: Final = "暗色"
HOME_STATUS_LIGHT: Final = "亮色"
HOME_DEVICE_COUNT_FMT: Final = "{count} 台"
HOME_NO_MODULES: Final = "暂无已加载模块"
HOME_MODULES_TITLE: Final = "已加载模块"


# ── LLMSettingsDialog ──

LLM_SETTINGS_TITLE: Final = "⚙ LLM 模型设置"
LLM_SETTINGS_API_KEY_PLACEHOLDER: Final = "输入 API Key"
LLM_SETTINGS_TOGGLE_SHOW: Final = "显示"
LLM_SETTINGS_TOGGLE_HIDE: Final = "隐藏"
LLM_SETTINGS_MODEL_LABEL: Final = "模型:"
LLM_SETTINGS_SMART_SWITCH: Final = "启用失败自动降级"
LLM_SETTINGS_FORM_SMART_SWITCH: Final = "智能切换:"
LLM_SETTINGS_FORM_TOKEN_BUDGET: Final = "Token 预算:"
LLM_SETTINGS_FORM_ALERT_THRESHOLD: Final = "告警阈值:"
LLM_SETTINGS_BTN_SAVE: Final = "保存"
LLM_SETTINGS_BTN_CANCEL: Final = "取消"


# ── ToolkitDialog ──

DLG_BTN_CONFIRM: Final = "确认"
DLG_BTN_CANCEL: Final = "取消"
DLG_BTN_OK: Final = "确定"


# ── BaseTab ──

BASE_TAB_UNNAMED: Final = "未命名"
BASE_TAB_WARN_NO_DEVICE_TITLE: Final = "设备已断开"
BASE_TAB_WARN_NO_DEVICE_MSG: Final = "当前无可用设备，请连接设备后重试。"


# ── LLMStatusWidget ──

LLM_STATUS_NOT_CONFIGURED: Final = "未配置"


# ── TitleBar / SettingsButton ──

TITLEBAR_TOOLTIP_THEME: Final = "切换主题"
TITLEBAR_TOOLTIP_SETTINGS: Final = "设置"
TITLEBAR_MENU_THEME: Final = "主题切换"
TITLEBAR_MENU_LLM_SETTINGS: Final = "LLM 模型设置"
TITLEBAR_MENU_AGENT_SETTINGS: Final = "Agent 设置"
TITLEBAR_NAV_PANEL: Final = "左侧导航"
TITLEBAR_BOTTOM_PANEL: Final = "底部面板"
TITLEBAR_RIGHT_PANEL: Final = "右侧面板"
TITLEBAR_NO_DEVICE: Final = "未连接设备"
TITLEBAR_CONNECTED_FMT: Final = "已连接: {device}"
TITLEBAR_DEVICES_CONNECTED_FMT: Final = "{count} 台设备已连接"
TITLEBAR_MENU_LOG: Final = "日志"
TITLEBAR_MENU_LOG_EXPORT: Final = "导出日志"
TITLEBAR_MENU_LOG_OPEN_DIR: Final = "历史日志"
TITLEBAR_MENU_LOG_CLEAR_HISTORY: Final = "清空历史"
DLG_CLEAR_LOG_HISTORY_TITLE: Final = "清空日志历史"
DLG_CLEAR_LOG_HISTORY_MSG: Final = "确定要删除 data/logs/ 目录下的所有 .log 文件吗？此操作不可撤销。"
DLG_CLEAR_LOG_HISTORY_CONFIRM: Final = "删除"
