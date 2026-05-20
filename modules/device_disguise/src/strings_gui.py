"""设备伪装 — GUI 文案常量"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Tab 标题
# ---------------------------------------------------------------------------

TAB_TITLE: Final = "设备伪装"

# ---------------------------------------------------------------------------
# 文档字符串（模块级描述）
# ---------------------------------------------------------------------------

DOC_MODULE: Final = "设备伪装工具 — GUI 页面（方案 A：左右分栏）"

# ---------------------------------------------------------------------------
# 标签 (QLabel / QFormLayout 行标签)
# ---------------------------------------------------------------------------

LABEL_BRAND: Final = "品牌"
LABEL_MANUFACTURER: Final = "厂商"
LABEL_MODEL: Final = "型号"
LABEL_CONNECTION: Final = "连接"
LABEL_DISGUISE: Final = "伪装"
LABEL_TARGET_BRAND: Final = "目标品牌"
LABEL_TARGET_MANUFACTURER: Final = "目标厂商"
LABEL_TARGET_MODEL: Final = "目标型号"
LABEL_NOTES: Final = "备注"

# ---------------------------------------------------------------------------
# 占位符
# ---------------------------------------------------------------------------

PLACEHOLDER_PROP_HINT_FMT: Final = "通过 '{}' 属性获取"
PLACEHOLDER_SEARCH_PROFILE: Final = "搜索档案..."
PLACEHOLDER_NOTES: Final = "可选备注..."

# ---------------------------------------------------------------------------
# 按钮
# ---------------------------------------------------------------------------

BTN_SELECT_PROFILE: Final = "选择档案"
BTN_SAVE_PROFILE: Final = "保存档案"
BTN_IMPORT_CONFIG: Final = "导入配置"
BTN_DISGUISE: Final = "伪装"
BTN_RESET: Final = "还原"
BTN_EDIT: Final = "编辑"
BTN_DELETE: Final = "删除"
BTN_SAVE: Final = "保存"
BTN_DONT_SAVE: Final = "不保存"
BTN_CANCEL: Final = "取消"

# ---------------------------------------------------------------------------
# 分组标题
# ---------------------------------------------------------------------------

GROUP_DEVICE_STATUS: Final = "设备状态"
GROUP_DISGUISE_SETTINGS: Final = "伪装设置"

# ---------------------------------------------------------------------------
# 状态文字
# ---------------------------------------------------------------------------

STATUS_CONNECTED_FMT: Final = "已连接 ({})"
STATUS_NOT_CONNECTED: Final = "未连接设备"
STATUS_DISGUISED: Final = "已伪装"
STATUS_NOT_DISGUISED: Final = "未伪装"
DASH: Final = "--"

# ---------------------------------------------------------------------------
# Tooltip
# ---------------------------------------------------------------------------

TOOLTIP_IMPORT_CONFIG: Final = "从 JSON 文件导入设备档案（合并到当前列表，重复项跳过）"

# ---------------------------------------------------------------------------
# 对话框标题
# ---------------------------------------------------------------------------

DLG_TITLE_SAVE_PROFILE: Final = "保存档案"
DLG_TITLE_LIBRARY: Final = "档案库"
DLG_TITLE_SELECT_PROFILE: Final = "选择设备档案"
DLG_TITLE_EDIT_PROFILE: Final = "编辑设备档案"
DLG_TITLE_IMPORT_FILE: Final = "导入设备配置 (JSON)"
DLG_TITLE_IMPORT_COMPLETE: Final = "导入完成"
DLG_TITLE_IMPORT_FAILED: Final = "导入失败"
DLG_TITLE_EDIT_FAILED: Final = "编辑失败"
DLG_TITLE_CONFIRM_DELETE: Final = "确认删除"
DLG_TITLE_DELETE_FAILED: Final = "删除失败"

# ---------------------------------------------------------------------------
# 直接的消息文本
# ---------------------------------------------------------------------------

MSG_NO_DEVICE: Final = "无设备"
MSG_PROFILE_LIBRARY_EMPTY: Final = "档案库为空，请先添加档案。"
MSG_PROFILE_NOT_EXISTS_FMT: Final = "目标组合 {}/{}/{} 不在档案库中。\n是否保存为新档案？"
MSG_IMPORT_RESULT_FMT: Final = "已导入 {} 条，跳过 {} 条。\n档案已同步写入配置文件。"
MSG_FILL_ALL_FIELDS: Final = "请先填写品牌、厂商和型号。"
MSG_EMPTY_FIELDS: Final = "品牌、厂商和型号不能为空。"
MSG_CONFIRM_DELETE_FMT: Final = "确认删除档案 {}/{}/{}？"


# ---------------------------------------------------------------------------
# 文件过滤器
# ---------------------------------------------------------------------------

FILE_FILTER_JSON: Final = "JSON 文件 (*.json);;所有文件 (*.*)"

# ---------------------------------------------------------------------------
# 日志 / 结果输出
# ---------------------------------------------------------------------------

LOG_ACTION_COMPLETE: Final = "✓ 操作完成"
LOG_ACTION_FAILED_FMT: Final = "✗ {}"
LOG_IMPORT_SUCCEEDED_FMT: Final = "✓ 导入配置: 新增 {} 条, 跳过 {} 条"
LOG_IMPORT_FAILED_FMT: Final = "✗ 导入配置失败: {}"
LOG_PROFILE_SAVED_FMT: Final = "档案已保存: {}/{}/{}"
LOG_SAVE_FAILED_FMT: Final = "保存失败: {}"
