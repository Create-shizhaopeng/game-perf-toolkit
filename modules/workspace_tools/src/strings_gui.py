"""性能配置对比 — GUI 文案常量"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Tab
# ---------------------------------------------------------------------------

TAB_TITLE: Final = "性能配置对比"
TAB_ICON: Final = "🧰"
TAB_INTRO_LABEL: Final = "工具说明"
TAB_DIFF_LABEL: Final = "配置对比"

# ---------------------------------------------------------------------------
# 介绍页
# ---------------------------------------------------------------------------

INTRO_TITLE: Final = "性能配置对比"
MSG_INTRO_BODY: Final = (
    "本模块用于多份游戏性能策略 XML（gameperfconfig*.xml）的对比与合并。\n\n"
    "「配置对比」页支持选定基准与多个对比源、语义差异展示、按条采纳、另存为（原子写盘），"
    "以及从已连接设备拉取标准路径配置参与对比。"
)

# ---------------------------------------------------------------------------
# 差异页 — 分组
# ---------------------------------------------------------------------------

GROUP_BASELINE: Final = "基准文件"
GROUP_COMPARATORS: Final = "对比文件（可拖拽 gameperfconfig*.xml 到下方区域）"
GROUP_SUMMARY: Final = "各对比文件差异条数"
GROUP_DIFF_DETAIL: Final = "差异明细（选中一行后采纳一侧）"

# ---------------------------------------------------------------------------
# 差异页 — 按钮
# ---------------------------------------------------------------------------

BTN_BROWSE: Final = "浏览…"
BTN_ADD_LOCAL: Final = "添加本地…"
BTN_REMOVE: Final = "移除选中"
BTN_SET_BASELINE: Final = "设为基准"
BTN_ADD_FROM_DEVICE: Final = "从当前设备添加"
BTN_START_DIFF: Final = "开始对比"
BTN_CANCEL_DIFF: Final = "取消"
BTN_CANCEL_PULL: Final = "取消拉取"
BTN_ADOPT_BASE: Final = "采纳基准侧"
BTN_ADOPT_COMP: Final = "采纳对比侧"
BTN_UNDO: Final = "撤销上次采纳"
BTN_RESET: Final = "重置合并"
BTN_SAVE_AS: Final = "另存为…"

# ---------------------------------------------------------------------------
# 差异页 — 标签与占位文本
# ---------------------------------------------------------------------------

LABEL_ACTIVE_COMP: Final = "当前对比："
PLACEHOLDER_BASELINE: Final = "选择包含 gameperfconfig 的 .xml 作为基准"
HINT_DROP: Final = "拖拽文件到此处添加为对比项"

MSG_SERVICE_UNAVAILABLE: Final = "未注入 wo_gameperf_diff_service，配置对比不可用。"

# ---------------------------------------------------------------------------
# 差异树表头
# ---------------------------------------------------------------------------

TABLE_HEADER_SEMANTIC_PATH: Final = "语义路径"
TABLE_HEADER_BASELINE_SIDE: Final = "基准侧"
TABLE_HEADER_COMP_SIDE: Final = "对比侧"

# ---------------------------------------------------------------------------
# 对话框标题
# ---------------------------------------------------------------------------

DLG_TITLE_HINT: Final = "提示"
DLG_TITLE_INVALID_FILENAME: Final = "文件名无效"
DLG_TITLE_LOAD_FAILED: Final = "载入失败"
DLG_TITLE_REMOVE_FAILED: Final = "移除失败"
DLG_TITLE_OPERATION_FAILED: Final = "操作失败"
DLG_TITLE_DIFF_FAILED: Final = "对比失败"
DLG_TITLE_CONFIRM_SAVE: Final = "确认保存"
DLG_TITLE_FILE_CHANGED: Final = "文件已变化"
DLG_TITLE_COMPLETE: Final = "完成"
DLG_TITLE_SAVE_FAILED: Final = "保存失败"
DLG_TITLE_DEVICE: Final = "设备"
DLG_TITLE_ADOPT_FAILED: Final = "采纳失败"
DLG_TITLE_PULL_FAILED: Final = "拉取失败"
DLG_TITLE_SELECT_BASELINE: Final = "选择基准 gameperfconfig XML"
DLG_TITLE_ADD_COMP: Final = "添加对比文件"
DLG_TITLE_SAVE_AS: Final = "另存为 gameperfconfig"

# ---------------------------------------------------------------------------
# 对话框消息
# ---------------------------------------------------------------------------

MSG_SELECT_BASELINE_FIRST: Final = "请先选择基准文件。"
MSG_INVALID_FILENAME_BASELINE: Final = "须为文件名包含 gameperfconfig 的 .xml"
MSG_SELECT_COMPARATOR_FIRST: Final = "请先在列表中选中一个对比文件。"
MSG_INVALID_FILENAME_SAVE: Final = "建议文件名包含 gameperfconfig 且为 .xml"
MSG_FILE_CHANGED: Final = "目标文件在操作过程中已被外部修改，仍要覆盖写入吗？"
MSG_SAVE_SUCCESS: Final = "保存成功。"
MSG_SELECT_DIFF_ROW: Final = "请在差异树中选择一行。"
MSG_NOT_MERGEABLE: Final = "该项不可一键采纳。"
MSG_NO_SERIAL: Final = "无当前设备序列号。"

# ---------------------------------------------------------------------------
# 确认保存格式
# ---------------------------------------------------------------------------

MSG_CONFIRM_SAVE_FMT: Final = (
    "目标路径：\n{path}\n\n"
    "{will_overwrite}"
    "合并脏状态（相对基准已修改）：{dirty}\n\n"
    "确认保存？"
)
MSG_FILE_OVERWRITE_YES: Final = "将覆盖已存在文件。\n"
MSG_FILE_OVERWRITE_NO: Final = "将创建新文件。\n"
MSG_DIRTY_YES: Final = "是"
MSG_DIRTY_NO: Final = "否"

# ---------------------------------------------------------------------------
# 文件过滤器
# ---------------------------------------------------------------------------

FILE_FILTER_XML: Final = "XML (*.xml)"

# ---------------------------------------------------------------------------
# 日志消息
# ---------------------------------------------------------------------------

LOG_BASELINE_LOADED_FMT: Final = "已载入基准：{path}"
LOG_START_DIFF: Final = "开始语义对比…"
LOG_CANCEL_DIFF_REQUESTED: Final = "已请求取消对比（步骤间隙生效）…"
LOG_DIFF_COMPLETE: Final = "对比完成。"
LOG_DIFF_FAILED_FMT: Final = "对比失败：{msg}"
LOG_ADOPT_FMT: Final = "已采纳：{side} ← {path}"
LOG_UNDO_WITH_DETAIL_FMT: Final = "已撤销上次采纳。{detail}"
LOG_UNDO: Final = "已撤销上次采纳。"
LOG_NOTHING_TO_UNDO: Final = "无可撤销操作。"
LOG_RESET_MERGE: Final = "已重置合并为基准副本。"
LOG_SAVED_FMT: Final = "已保存：{path}"
LOG_PULL_START_FMT: Final = "[设备] 开始拉取 {serial} …"
LOG_CANCEL_PULL_REQUESTED: Final = "已请求取消拉取（步骤间隙生效）…"
LOG_PULL_SUCCESS: Final = "设备配置已加入对比列表。"
LOG_PULL_FAILED_FMT: Final = "拉取失败：{msg}"
LOG_SET_BASELINE: Final = "已将该对比文件设为基准，对比列表已清空。"

# ---------------------------------------------------------------------------
# 差异摘要格式
# ---------------------------------------------------------------------------

SUMMARY_DIFF_COUNT_FMT: Final = "{label}：{n} 条差异"
SUMMARY_NO_DIFF: Final = "{label}：无差异"

# ---------------------------------------------------------------------------
# 通用标记
# ---------------------------------------------------------------------------

DASH: Final = "—"

# ---------------------------------------------------------------------------
# 日志级别判定标记
# ---------------------------------------------------------------------------

LOG_ERR_MARKER: Final = "失败"
LOG_ERR_SYMBOL: Final = "✗"
LOG_OK_SYMBOL: Final = "✓"
LOG_OK_MARKER: Final = "成功"
LOG_DONE_MARKER: Final = "完成"
