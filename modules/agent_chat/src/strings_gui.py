"""Agent 智能助手 — GUI 文案常量"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Tab 标题
# ---------------------------------------------------------------------------

TAB_TITLE: Final = "Agent 智能助手"
TAB_ICON: Final = "🤖"

# ---------------------------------------------------------------------------
# 文档字符串（模块级描述）
# ---------------------------------------------------------------------------

DOC_MODULE: Final = "Agent 智能助手 — GUI Tab"

# ---------------------------------------------------------------------------
# 标签 (QLabel)
# ---------------------------------------------------------------------------

LABEL_TITLE: Final = "🤖 Agent 智能助手"
LABEL_CONTEXT_AREA: Final = "上下文区域"
LABEL_API_KEY: Final = "API Key"
LABEL_MODEL: Final = "模型"
LABEL_REPLY_LANGUAGE: Final = "回复语言"
LABEL_TEMPERATURE: Final = "Temperature"
LABEL_MAX_CONVERSATIONS: Final = "最大保存会话数:"
LABEL_MAX_CONTEXT_MESSAGES: Final = "最大上下文消息数:"
LABEL_TOOL_RESULT_MAX_LENGTH: Final = "工具结果最大长度:"
LABEL_CHARACTERS: Final = "字符"
LABEL_SOP_NAME: Final = "名称"
LABEL_SOP_SOURCE: Final = "来源"
LABEL_SOP_ACTION: Final = "操作"
LABEL_SOP_IMPORT: Final = "导入 SOP"
LABEL_MCP_SERVER: Final = "服务器"
LABEL_MCP_STATUS: Final = "状态"
LABEL_MCP_TOOL_COUNT: Final = "工具数"
LABEL_MCP_SDK_NOT_INSTALLED: Final = "MCP SDK 未安装"

# ---------------------------------------------------------------------------
# 占位符
# ---------------------------------------------------------------------------

PLACEHOLDER_CHAT_INPUT: Final = "描述你的任务..."

# ---------------------------------------------------------------------------
# 按钮
# ---------------------------------------------------------------------------

BTN_SEND: Final = "发送"
BTN_STOP: Final = "停止"
BTN_NEW_CONVERSATION: Final = "+"
BTN_SAVE: Final = "保存"
BTN_CANCEL: Final = "取消"
BTN_DELETE: Final = "删除"
BTN_OPEN: Final = "打开"
BTN_RENAME: Final = "重命名"
BTN_TOGGLE_KEY_SHOW: Final = "👁"
BTN_TOGGLE_KEY_HIDE: Final = "🔒"
BTN_GLM: Final = "GLM (智谱)"
BTN_CLAUDE: Final = "Claude (Anthropic)"
BTN_IMPORT_SOP: Final = "📥 导入 SOP"
BTN_ADD_MCP_SERVER: Final = "➕ 添加"
BTN_REMOVE_MCP_SERVER: Final = "🗑 移除"
BTN_TOGGLE_MCP_SERVER: Final = "⏯ 启用/禁用"
BTN_OPEN_REPORT_DIR: Final = "📂 打开报告目录"
BTN_VIEW_REPORT: Final = "📋 查看报告"
BTN_SAVE_NEW_SOP: Final = "保存为新 SOP"
BTN_SKIP: Final = "跳过"

# ---------------------------------------------------------------------------
# 分组标题
# ---------------------------------------------------------------------------

GROUP_LLM_PROVIDER: Final = "LLM Provider"
GROUP_CONVERSATION_HISTORY: Final = "对话历史"
GROUP_CONTEXT_MANAGEMENT: Final = "上下文管理"
GROUP_WORKFLOW_LEARNING: Final = "工作流学习"
GROUP_LANGUAGE: Final = "语言"
GROUP_SOP_MANAGEMENT: Final = "SOP 管理"
GROUP_MCP_MANAGEMENT: Final = "MCP 管理"
GROUP_ADVANCED_SETTINGS: Final = "高级设置"

# ---------------------------------------------------------------------------
# Checkbox
# ---------------------------------------------------------------------------

CHECK_SMART_SWITCH: Final = "智能切换: 复杂任务自动使用 Claude（需双 Key）"
CHECK_WORKFLOW_LEARNING: Final = "对话结束时检测可沉淀工作流"

# ---------------------------------------------------------------------------
# Tooltip
# ---------------------------------------------------------------------------

TOOLTIP_NEW_CONVERSATION: Final = "新建会话"
TOOLTIP_CONTEXT_LIST: Final = "选中后可按 Backspace/Delete 删除"

# ---------------------------------------------------------------------------
# 对话框标题
# ---------------------------------------------------------------------------

DLG_TITLE_AGENT_SETTINGS: Final = "⚙ Agent 设置"
DLG_TITLE_SWITCH_CONVERSATION: Final = "切换会话"
DLG_TITLE_NEW_CONVERSATION: Final = "新建对话"
DLG_TITLE_DELETE_CONVERSATION: Final = "删除对话"
DLG_TITLE_RENAME_CONVERSATION: Final = "重命名对话"
DLG_TITLE_AGENT_NOT_READY: Final = "Agent 未就绪"
DLG_TITLE_ADD_MCP_SERVER: Final = "添加 MCP 服务器"
DLG_TITLE_MCP: Final = "MCP"
DLG_TITLE_SOP_SAVED: Final = "SOP 已保存"
DLG_TITLE_IMPORT_SOP: Final = "导入 SOP"

# ---------------------------------------------------------------------------
# 消息文本
# ---------------------------------------------------------------------------

MSG_SWITCH_STOP_TASK: Final = "当前有任务在执行中，切换会话将停止当前任务。是否继续？"
MSG_NEW_CONV_STOP_TASK: Final = "当前有任务在执行中，新建对话将停止当前任务。是否继续？"
MSG_CONFIRM_DELETE_CONVERSATION: Final = "确认删除该对话？"
MSG_RENAME_PLACEHOLDER: Final = "新名称:"
MSG_AGENT_NOT_READY_NO_KEY: Final = "请先在设置中配置 API Key。"
MSG_AGENT_NOT_READY_INVALID_KEY: Final = "API Key 未配置或无效，请在设置中检查。"
MSG_STOPPED_HINT: Final = "⚠️ 工作已中断。你可以继续发送消息。"
MSG_ERROR_FMT: Final = "❌ 错误: {}"
MSG_SOP_SAVED_FMT: Final = "SOP 已保存到:\n{}\n\n是否打开编辑？"
MSG_MCP_NOT_INSTALLED: Final = "MCP SDK 未安装"
MSG_SOP_SERVER_NAME: Final = "服务器名称:"
MSG_SOP_START_CMD: Final = "启动命令 (如 npx):"
MSG_SOP_ARGS: Final = "参数 (空格分隔):"

# ---------------------------------------------------------------------------
# 状态/思考文字
# ---------------------------------------------------------------------------

STATE_THINKING: Final = "💭 {}"
STATE_TOOL_RUNNING: Final = "执行中..."
STATE_TOOL_RUNNING_FMT: Final = "执行中... ({:.1f}s)"
STATE_TOOL_COMPLETE_FMT: Final = "完成 ({:.1f}s)"
STATE_TOOL_FAILED: Final = "失败"
STATE_TOOL_CANCELLED: Final = "已取消"
STATE_TOOL_EXPAND: Final = "▶ 展开"
STATE_TOOL_COLLAPSE: Final = "▼ 收起"
STATE_SAVING: Final = "SOP 保存中..."
STATE_SKIPPED: Final = "已跳过"
STATE_DONE_FMT: Final = "✓ {}"
STATE_CONNECTING: Final = "未连接"
STATE_DISABLED: Final = "已禁用"

# ---------------------------------------------------------------------------
# 欢迎页
# ---------------------------------------------------------------------------

WELCOME_TITLE: Final = "🤖 Agent 智能助手"
WELCOME_SUBTITLE: Final = "描述你的任务，我将自动匹配工作流完成分析。"
WELCOME_HINT: Final = "💡 提示: 你也可以直接描述需求，无需选择具体分析类型"
WELCOME_SHORTCUT_TRACE: Final = "🔍 Trace 分析"
WELCOME_SHORTCUT_PERFDog: Final = "📊 PerfDog 分析"
WELCOME_SHORTCUT_POLICY: Final = "⚙ 策略审查"
WELCOME_SHORTCUT_JANK: Final = "🔬 综合卡顿分析"

# ---------------------------------------------------------------------------
# 工作流
# ---------------------------------------------------------------------------

WORKFLOW_TITLE_FMT: Final = "📋 工作流: {}"
WORKFLOW_STEP_FMT: Final = "  Step {}: {}"
WORKFLOW_DEPOSIT_HEADER: Final = "💡 工作流沉淀"
WORKFLOW_DEPOSIT_DESC_FMT: Final = "本次对话使用了 {} 个工具、{} 个步骤"
WORKFLOW_DEVIATION_FMT: Final = "偏差: {}"

# ---------------------------------------------------------------------------
# Token 用量
# ---------------------------------------------------------------------------

TOKEN_USAGE_FMT: Final = "↑{:,} ↓{:,} tokens"

# ---------------------------------------------------------------------------
# 上下文
# ---------------------------------------------------------------------------

CONTEXT_FILE_MISSING: Final = " [文件不存在]"
CONTEXT_FILE_CONTEXT: Final = "[文件上下文]"

# ---------------------------------------------------------------------------
# SOP 树
# ---------------------------------------------------------------------------

SOP_BUILTIN_FOLDER: Final = "📁 内置"
SOP_CUSTOM_FOLDER: Final = "📁 自定义"
SOP_BUILT_IN: Final = "内置"
SOP_CUSTOM: Final = "自定义"
SOP_NO_SKILLS: Final = "暂无 Skill"

# ---------------------------------------------------------------------------
# MCP
# ---------------------------------------------------------------------------

MCP_DESC: Final = "管理 MCP 服务器连接，已连接的服务器工具会自动注入 Agent。"
MCP_TOOL_PREFIX: Final = "  🔧 {}"

# ---------------------------------------------------------------------------
# 文件过滤器
# ---------------------------------------------------------------------------

FILE_FILTER_MARKDOWN: Final = "Markdown (*.md);;所有文件 (*)"

# ---------------------------------------------------------------------------
# 会话
# ---------------------------------------------------------------------------

CONVERSATION_NEW: Final = "新对话"
CONVERSATION_NEW_TAB: Final = "新对话"

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------

LOG_WORKER_EXCEPTION: Final = "AgentWorker 异常: {}"
LOG_ON_CHUNK_FAILED: Final = "_on_chunk: 信号发射失败 (对象可能已销毁)"
LOG_ON_TOOL_START_DESTROYED: Final = "_on_tool_start: widget 已销毁, 忽略"
LOG_ON_TOOL_END_DESTROYED: Final = "_on_tool_end: widget 已销毁, 忽略"
LOG_ON_FINISHED_DESTROYED: Final = "_on_finished: widget 已销毁, 忽略"
LOG_ON_ERROR_DESTROYED: Final = "_on_error: widget 已销毁, 忽略"
LOG_SKIP_WORKFLOW_DEPOSIT: Final = "用户跳过工作流沉淀"
LOG_PATH_NOT_EXISTS_FMT: Final = "路径不存在: {}"
LOG_OPEN_PATH_FAILED_FMT: Final = "打开路径失败 '{}': {}"
