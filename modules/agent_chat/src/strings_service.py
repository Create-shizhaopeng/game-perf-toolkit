"""Agent 智能助手 — Service 层文案常量"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# 服务元数据
# ---------------------------------------------------------------------------

SERVICE_DISPLAY_NAME: Final = "Agent 智能助手"

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYS_PROMPT_IDENTITY_ZH: Final = (
    "你是 Game Perf Toolkit 的 Agent 智能助手，专注于游戏性能分析。"
    "请用简洁专业的中文回复用户。"
)
SYS_PROMPT_IDENTITY_EN: Final = (
    "You are the Agent assistant of Game Perf Toolkit, "
    "specialized in game performance analysis. "
    "Reply concisely and professionally in English."
)
SYS_PROMPT_TOOLS_FMT: Final = "可用工具: {}"
SYS_PROMPT_SKILLS_HEADER: Final = "可用 Skills：\n"
SYS_PROMPT_SKILLS_FOOTER: Final = (
    "使用 skill_list / skill_load / skill_load_resource 工具获取详细知识。"
    "根据用户意图自主编排工具调用流程。"
)
SYS_PROMPT_SOP_HEADER: Final = "可用 SOP 工作流：\n"
SYS_PROMPT_SOP_FOOTER: Final = (
    "当用户意图匹配某 SOP 时，按 SOP 步骤引导用户完成任务。"
    "如无匹配 SOP，以自由对话 + 工具调用方式协助用户。"
)
SYS_PROMPT_SOP_SKILL_FMT: Final = "- {}: {} (tags: {})"
SYS_PROMPT_SOP_ENTRY_FMT: Final = "- {}: {} (关键词: {})"

# ---------------------------------------------------------------------------
# 进度 / 状态
# ---------------------------------------------------------------------------

PROGRESS_THINKING_FIRST: Final = "正在思考..."
PROGRESS_THINKING_LOOP: Final = "正在分析工具结果..."

# ---------------------------------------------------------------------------
# 错误消息
# ---------------------------------------------------------------------------

ERR_PROVIDER_NOT_INIT: Final = "LLM Provider 未初始化，请检查 API Key 配置"
ERR_TOOL_LOOP_LIMIT_FMT: Final = "工具调用次数已达上限，请检查任务是否合理。"
ERR_TOOL_NO_EXECUTOR_FMT: Final = "工具 '{}' 无可用执行器"
ERR_TOOL_EXEC_EXCEPTION_FMT: Final = "工具执行异常: {}"
ERR_PROVIDER_INIT_FAILED_FMT: Final = "Provider 初始化失败: {}"
ERR_PROVIDER_NO_API_KEY_FMT: Final = "Provider '{}' 无可用 API Key"
ERR_LLM_MANAGER_NO_PROVIDER: Final = "LLMManager 未配置 Provider，尝试本地初始化"

# ---------------------------------------------------------------------------
# 取消标记
# ---------------------------------------------------------------------------

CANCELLED_MARK: Final = "[已取消]"
CANCELLED_APPEND: Final = "\n[已取消]"

# ---------------------------------------------------------------------------
# 工具结果截断
# ---------------------------------------------------------------------------

TOOL_RESULT_TRUNCATED: Final = "\n... [结果已截断]"

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------

LOG_AGENT_PROVIDER_SWITCHED_FMT: Final = "Agent Provider 已切换至: {}"
LOG_TOOL_RETRY_FMT: Final = "工具 '{}' 失败，重试 1 次"
LOG_TOOL_EXEC_ERROR_FMT: Final = "工具 '{}' 执行异常: {}"
