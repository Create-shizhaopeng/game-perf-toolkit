"""设备伪装 — Service 层进度与错误消息常量"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# 服务元数据
# ---------------------------------------------------------------------------

SERVICE_DISPLAY_NAME: Final = "设备伪装工具"

# ---------------------------------------------------------------------------
# reset() 进度
# ---------------------------------------------------------------------------

PROGRESS_READING_ORIGINAL: Final = "正在读取原始设备信息..."
PROGRESS_NOT_DISGUISED: Final = "✓ 设备未伪装，无需还原"

# ---------------------------------------------------------------------------
# _execute_modify() 进度步骤
# ---------------------------------------------------------------------------

PROGRESS_MODIFYING: Final = "设备信息修改中..."
PROGRESS_ADB_ROOT: Final = "  adb root..."
PROGRESS_ADB_ROOT_OK: Final = "  ✓ adb root 成功"
PROGRESS_ADB_REMOUNT: Final = "  adb remount..."
PROGRESS_SETENFORCE: Final = "  setenforce 0..."
PROGRESS_SETENFORCE_OK: Final = "  ✓ setenforce 0 成功"
PROGRESS_PULL_BUILD_PROP: Final = "  拉取 build.prop..."
PROGRESS_PULL_OK: Final = "  ✓ 拉取 build.prop 成功"
PROGRESS_MODIFY_BUILD_PROP: Final = "  修改 build.prop..."
PROGRESS_MODIFY_OK: Final = "  ✓ 修改 build.prop 成功"
PROGRESS_PUSH_BUILD_PROP: Final = "  推送 build.prop..."
PROGRESS_PUSH_OK: Final = "  ✓ 推送 build.prop 成功"
PROGRESS_REBOOTING: Final = "正在重启设备请稍后..."
PROGRESS_WAIT_REBOOT: Final = "  等待设备重启完成..."
PROGRESS_REBOOT_OK: Final = "  ✓ 设备重启完成"
PROGRESS_VERIFYING: Final = "  验证设备属性..."
PROGRESS_DISGUISE_OK_FMT: Final = "  ✓ 设备信息{}成功: brand={}, manufacturer={}, model={}"

# ---------------------------------------------------------------------------
# 验证错误
# ---------------------------------------------------------------------------

ERR_VERIFY_FAILED_FMT: Final = (
    "设备信息{}验证失败: 属性值与预期不一致\n"
    "  期望: brand={}, manufacturer={}, model={}\n"
    "  实际: brand={}, manufacturer={}, model={}"
)

# ---------------------------------------------------------------------------
# 数据模型错误
# ---------------------------------------------------------------------------

ERR_PROFILE_EXISTS_FMT: Final = "设备档案已存在: {}/{}/{}"
ERR_PROFILE_NOT_FOUND_UPDATE: Final = "未找到要更新的档案"
ERR_PROFILE_NOT_FOUND_DELETE: Final = "未找到要删除的档案"
ERR_JSON_ROOT_ARRAY: Final = "JSON 根节点须为数组，元素为设备档案对象"
WARN_PROFILE_FILE_CORRUPTED_FMT: Final = "档案文件损坏，已重置: {}"
