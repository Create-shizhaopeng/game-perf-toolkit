"""游戏性能配置 — Service 层进度与错误消息常量"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# 服务元数据
# ---------------------------------------------------------------------------

SERVICE_DISPLAY_NAME: Final = "游戏性能配置"

# ---------------------------------------------------------------------------
# push() 进度
# ---------------------------------------------------------------------------

PROGRESS_PUSH_STEP1: Final = "[1/10] XML 格式检查..."
PROGRESS_PUSH_XML_OK: Final = "✓ XML 格式检查通过"
PROGRESS_PUSH_STEP2: Final = "[2/10] 读取设备配置文件 version..."
PROGRESS_PUSH_VERSION_FMT: Final = "  设备当前 version = {device_ver}，目标 version = {target_ver}"
PROGRESS_PUSH_STEP3: Final = "[3/10] 修改本地文件 version..."
PROGRESS_PUSH_UPDATE_VERSION_FMT: Final = "✓ 本地 version 已更新为 {target_ver}"
PROGRESS_PUSH_STEP4: Final = "[4/10] adb root..."
PROGRESS_PUSH_ROOT_OK: Final = "✓ adb root 成功"
PROGRESS_PUSH_STEP5: Final = "[5/10] adb remount..."
PROGRESS_PUSH_STEP6: Final = "[6/10] setenforce 0..."
PROGRESS_PUSH_SETENFORCE_OK: Final = "✓ setenforce 0 成功"
PROGRESS_PUSH_STEP7: Final = "[7/10] 备份设备当前配置..."
PROGRESS_PUSH_BACKUP_FMT: Final = "✓ 已备份到 {backup_file}"
PROGRESS_PUSH_STEP8_FMT: Final = "[8/10] push → {remote_path}..."
PROGRESS_PUSH_PUSH_OK: Final = "✓ push 成功"
PROGRESS_PUSH_STEP9: Final = "[9/10] 重启设备..."
PROGRESS_PUSH_WAIT_REBOOT: Final = "  等待设备重启完成..."
PROGRESS_PUSH_REBOOT_OK: Final = "✓ 设备重启完成"
PROGRESS_PUSH_STEP10: Final = "[10/10] 校验 version..."
PROGRESS_PUSH_VERIFY_OK_FMT: Final = "✓ 校验通过！设备 version = {actual_ver}"

# ---------------------------------------------------------------------------
# reset() 进度
# ---------------------------------------------------------------------------

PROGRESS_RESET_STEP1: Final = "[1/8] 读取设备当前 version..."
PROGRESS_RESET_VERSION_FMT: Final = "  设备当前 version = {device_ver}，重置后 version = {target_ver}"
PROGRESS_RESET_STEP2: Final = "[2/8] 将备份 version 修改为 设备 version + 1..."
PROGRESS_RESET_BACKUP_UPDATED: Final = "✓ 备份 version 已更新"
PROGRESS_RESET_STEP3: Final = "[3/8] adb root..."
PROGRESS_RESET_ROOT_OK: Final = "✓ adb root 成功"
PROGRESS_RESET_STEP4: Final = "[4/8] adb remount..."
PROGRESS_RESET_STEP5: Final = "[5/8] setenforce 0..."
PROGRESS_RESET_SETENFORCE_OK: Final = "✓ setenforce 0 成功"
PROGRESS_RESET_STEP6_FMT: Final = "[6/8] push 备份文件 → {remote_path}..."
PROGRESS_RESET_PUSH_OK: Final = "✓ push 备份成功"
PROGRESS_RESET_STEP7: Final = "[7/8] 重启设备..."
PROGRESS_RESET_WAIT_REBOOT: Final = "  等待设备重启完成..."
PROGRESS_RESET_REBOOT_OK: Final = "✓ 设备重启完成"
PROGRESS_RESET_STEP8: Final = "[8/8] 校验 version..."
PROGRESS_RESET_VERIFY_OK_FMT: Final = "✓ 设备已重置，当前 version = {actual_ver}"

# ---------------------------------------------------------------------------
# pull_device_config_from_device() 进度
# ---------------------------------------------------------------------------

PROGRESS_PULL_STEP1_FMT: Final = "[拉取 1/2] pull → {local_path}..."
PROGRESS_PULL_PULL_OK: Final = "✓ pull 成功"
PROGRESS_PULL_STEP2: Final = "[拉取 2/2] 校验 XML..."
PROGRESS_PULL_XML_OK: Final = "✓ XML 校验通过"

# ---------------------------------------------------------------------------
# 结果/完成消息
# ---------------------------------------------------------------------------

MSG_PULL_COMPLETE: Final = "已从设备载入 gameperfconfig.xml。"

# ---------------------------------------------------------------------------
# 错误消息
# ---------------------------------------------------------------------------

ERR_INVALID_CONFIG_FILENAME: Final = "无效的配置文件：文件名须包含 gameperfconfig 且扩展名为 .xml"
ERR_CONFIG_FILE_NOT_FOUND_FMT: Final = "配置文件不存在: {config_file}"
ERR_VERSION_VERIFY_FMT: Final = "校验失败：期望 version={target_ver}，实际 version={actual_ver}"
ERR_NO_BACKUP: Final = "无可用备份，无法重置。请先执行一次 push 操作。"
ERR_RESET_VERIFY_FMT: Final = "重置后 version 校验异常：期望 {target_ver}，实际 {actual_ver}"
ERR_PULL_CANCELLED: Final = "已取消从设备拉取。"
ERR_NO_SERIAL: Final = "未检测到设备序列号，请连接设备后重试。"
ERR_PULL_FAILED_FMT: Final = "从设备拉取失败：{e}"
ERR_DEVICE_XML_INVALID_FMT: Final = "设备上的配置文件不是合法 XML，无法载入。（第 {line} 行：{msg}）"
ERR_DEVICE_CONFIG_MISSING: Final = "设备上未找到 /system/etc/gameperfconfig.xml，或路径不可访问。"
ERR_DEVICE_CONFIG_PERMISSION: Final = "无法读取设备上的配置文件，请确认设备已 root 且 remount 成功。"
ERR_PULL_GENERIC_FMT: Final = "从设备拉取失败：{exc}"

# ---------------------------------------------------------------------------
# XmlValidationError
# ---------------------------------------------------------------------------

ERR_XML_VALIDATION_FMT: Final = "XML 格式错误（第 {line} 行）: {msg}"
