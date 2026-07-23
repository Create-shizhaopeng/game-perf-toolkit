"""游戏性能配置 — GUI 文案常量"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Tab
# ---------------------------------------------------------------------------

TAB_TITLE: Final = "性能配置"

# ---------------------------------------------------------------------------
# 文件区域
# ---------------------------------------------------------------------------

TITLE_CONFIG_FILE: Final = "配置文件"
HINT_DROP_FILE: Final = '选择或拖拽「文件名包含 gameperfconfig」的 .xml'
PLACEHOLDER_FILE_PATH: Final = "gameperfconfig.xml 文件路径"
BTN_BROWSE: Final = "浏览..."

# ---------------------------------------------------------------------------
# 来源标签
# ---------------------------------------------------------------------------

ORIGIN_DEVICE: Final = "来源：设备"
ORIGIN_LOCAL_FILE: Final = "来源：本地文件"

# ---------------------------------------------------------------------------
# 筛选区域
# ---------------------------------------------------------------------------

LABEL_GAME: Final = "游戏:"
LABEL_MODE: Final = "模式:"
BTN_SAVE_AS: Final = "另存为"
POLICY_VERSION_FMT: Final = "策略版本: {v}"
POLICY_VERSION_NONE: Final = "策略版本: —"

# ---------------------------------------------------------------------------
# 频率表
# ---------------------------------------------------------------------------

TITLE_FREQ_TABLE: Final = "频率配置表"
TABLE_HEADER_TEMP_LEVEL: Final = "温度等级"
TABLE_HEADER_TRIGGER_TEMP: Final = "触发温度(℃)"
TABLE_HEADER_GOLD_LO: Final = "Gold下限"
TABLE_HEADER_GOLD_HI: Final = "Gold上限"
TABLE_HEADER_GOLD_IDX: Final = "Gold索引"
TABLE_HEADER_PRIME_LO: Final = "Prime下限"
TABLE_HEADER_PRIME_HI: Final = "Prime上限"
TABLE_HEADER_PRIME_IDX: Final = "Prime索引"
TABLE_HEADER_GPU_LO: Final = "GPU下限"
TABLE_HEADER_GPU_HI: Final = "GPU上限"
TABLE_HEADER_GPU_IDX: Final = "GPU索引"

# ---------------------------------------------------------------------------
# 策略标签页
# ---------------------------------------------------------------------------

TAB_OVERALL_STRATEGY: Final = "整体策略"
TAB_MODE_STRATEGY: Final = "性能模式策略"

# ---------------------------------------------------------------------------
# 策略块
# ---------------------------------------------------------------------------

LABEL_KEY: Final = "Key"
LABEL_VALUE: Final = "Value"
LABEL_ACTION: Final = "操作"
LABEL_DATA: Final = "数据:"
BTN_ADD_ROW: Final = "+ 添加"
BTN_DELETE_BLOCK: Final = "× 删除整块"
BTN_DELETE_ROW: Final = "删此行"
DASH: Final = "—"

# ---------------------------------------------------------------------------
# 进度区域
# ---------------------------------------------------------------------------

PROGRESS_PERCENT_FMT: Final = "{value}%"
BTN_CANCEL: Final = "取消"
TOOLTIP_CANCEL_PULL: Final = "取消正在进行的从设备拉取（各步骤间隙生效）"

# ---------------------------------------------------------------------------
# 主按钮
# ---------------------------------------------------------------------------

BTN_START: Final = "▶ Start"
BTN_CLEAR: Final = "↺ 重置修改"
BTN_RESET: Final = "↺ Reset"

# ---------------------------------------------------------------------------
# 对话框标题
# ---------------------------------------------------------------------------

DLG_TITLE_SELECT_CONFIG: Final = "选择配置文件"
DLG_TITLE_SAVE_AS: Final = "另存为"
DLG_TITLE_PARSE_FAILED: Final = "解析失败"
DLG_TITLE_FORMAT_ERROR: Final = "格式错误"
DLG_TITLE_CONFIRM_DELETE: Final = "确认删除"
DLG_TITLE_SAVE_SUCCESS: Final = "保存成功"
DLG_TITLE_PUSH_NOTES: Final = "填写推送备注"
DLG_TITLE_EMPTY_NOTES: Final = "备注为空"
DLG_TITLE_NO_FILE: Final = "未选择文件"
DLG_TITLE_FILE_NOT_FOUND: Final = "文件不存在"
DLG_TITLE_UNSAVED_CHANGES: Final = "未保存的修改"
DLG_TITLE_RESET_FAILED: Final = "无法重置"
DLG_TITLE_OPERATION_RUNNING: Final = "操作进行中"

# ---------------------------------------------------------------------------
# 对话框消息
# ---------------------------------------------------------------------------

MSG_PARSE_FAILED_FMT: Final = "解析 XML 失败: {e}"
MSG_NO_VALID_DATA: Final = "未解析到有效配置数据！"
MSG_TEMP_RANGE: Final = "触发温度请填写 0～200 的整数"
MSG_INDEX_FORMAT: Final = "索引须为 start_end 格式（如 2_8）"
MSG_CONFIRM_DELETE_BINDCORE: Final = "确定删除该绑核子项？"
MSG_CONFIRM_DELETE_SUBTREE: Final = "确定删除该节点及其所有子项？"
MSG_SAVED_TO_FMT: Final = "已保存到：\n{path}"
MSG_PUSH_NOTES_HINT: Final = "推送前必须填写备注，将写入推送记录。请简要说明本次变更目的："
PLACEHOLDER_NOTES: Final = "必填，例如：修复 XX 游戏温控策略"
MSG_EMPTY_NOTES: Final = "请填写非空备注后再推送。"
MSG_NO_FILE_SELECTED: Final = "请先选择要推送的配置文件"
MSG_FILE_NOT_FOUND_FMT: Final = "找不到文件:\n{filepath}"
MSG_DISCARD_CHANGES: Final = "当前配置有未保存的修改。是否放弃修改并从设备重新载入 gameperfconfig.xml？"
DLG_CONFIRM_DISCARD: Final = "放弃并载入"
MSG_NO_BACKUP: Final = "无可用备份，无法重置。请先执行一次 push 操作。"
MSG_OPERATION_RUNNING: Final = "上一个操作仍在进行中，请等待完成后再试。"

# ---------------------------------------------------------------------------
# 通用按钮
# ---------------------------------------------------------------------------

BTN_DELETE: Final = "删除"
BTN_CONFIRM: Final = "确定"

# ---------------------------------------------------------------------------
# 文件过滤器
# ---------------------------------------------------------------------------

FILE_FILTER_XML: Final = "XML文件 (*.xml)"

# ---------------------------------------------------------------------------
# 日志 / 状态
# ---------------------------------------------------------------------------

LOG_INVALID_FILE: Final = "✗ 仅支持 gameperfconfig*.xml 文件"
LOG_RESET_CONTENTS: Final = "↺ 已重置为文件原始内容（保持当前游戏/模式）"
LOG_CANCEL_PULL: Final = "… 已请求取消拉取（等待当前步骤结束）"
LOG_PULL_INTERNAL_ERROR: Final = "✗ 从设备载入失败：内部错误"
LOG_PULL_CACHE_MISSING: Final = "✗ 从设备载入失败：本地缓存文件不存在"
LOG_PULL_SUCCESS: Final = "✓ 已从设备载入并显示配置"
LOG_DEVICE_PULL_CANCELLED: Final = "[设备] 已取消自动载入（保留本地修改）"
LOG_DEVICE_PULLING: Final = "[设备] 正在从 /system/etc/gameperfconfig.xml 拉取…"
