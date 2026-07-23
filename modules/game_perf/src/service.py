"""游戏性能配置模块 — 服务层（纯同步，不依赖 GUI 框架）"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import threading
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import datetime

from toolkit.core.adb_manager import AdbManager
from toolkit.sdk.exceptions import AdbError

from .models import (
    AutoDevicePullResult,
    GamePerfDocumentOrigin,
    PushRecord,
    XmlErrorContext,
)

logger = logging.getLogger(__name__)

REMOTE_CONFIG_PATH = "/system/etc/gameperfconfig.xml"

ProgressCallback = Callable[[str], None] | None


def is_valid_config_filename(filepath: str) -> bool:
    """文件名须包含完整子串 gameperfconfig 且扩展名为 .xml"""
    name = os.path.basename(filepath)
    return "gameperfconfig" in name and name.lower().endswith(".xml")


class GamePerfService:
    """推送/还原/版本管理的纯同步业务逻辑。

    GUI 层应在 QThread 中调用，CLI/Agent 可直接调用。
    """

    def __init__(self, adb: AdbManager, data_dir: str) -> None:
        self._adb = adb
        self._data_dir = data_dir

    def get_service_info(self) -> dict:
        return {"name": "game_perf", "display_name": "游戏性能配置"}

    # ------------------------------------------------------------------
    # 推送
    # ------------------------------------------------------------------

    def push(
        self,
        serial: str,
        config_file: str,
        on_progress: ProgressCallback = None,
        notes: str = "",
    ) -> int:
        """完整推送流程，返回最终 version"""
        if not is_valid_config_filename(config_file):
            raise AdbError("无效的配置文件：文件名须包含 gameperfconfig 且扩展名为 .xml")
        if not os.path.isfile(config_file):
            raise AdbError(f"配置文件不存在: {config_file}")

        self._notify(on_progress, "[1/10] XML 格式检查...")
        xml_err = self.validate_xml(config_file)
        if xml_err is not None:
            raise XmlValidationError(xml_err)
        self._notify(on_progress, "✓ XML 格式检查通过")

        self._notify(on_progress, "[2/10] 读取设备配置文件 version...")
        device_ver = self.get_device_version(serial)
        target_ver = device_ver + 1
        self._notify(on_progress, f"  设备当前 version = {device_ver}，目标 version = {target_ver}")

        self._notify(on_progress, "[3/10] 修改本地文件 version...")
        work_file = self._prepare_work_copy(config_file, target_ver)
        self._notify(on_progress, f"✓ 本地 version 已更新为 {target_ver}")

        self._notify(on_progress, "[4/10] adb root...")
        self._adb.root(serial)
        self._notify(on_progress, "✓ adb root 成功")

        self._notify(on_progress, "[5/10] adb remount...")
        self._adb.remount(serial, on_progress=on_progress)

        self._notify(on_progress, "[6/10] setenforce 0...")
        self._adb.shell(serial, "setenforce 0")
        self._notify(on_progress, "✓ setenforce 0 成功")

        self._notify(on_progress, "[7/10] 备份设备当前配置...")
        backup_file = self._backup_device_config(serial)
        self._notify(on_progress, f"✓ 已备份到 {backup_file}")

        self._notify(on_progress, f"[8/10] push → {REMOTE_CONFIG_PATH}...")
        self._adb.push(serial, work_file, REMOTE_CONFIG_PATH)
        self._notify(on_progress, "✓ push 成功")

        self._notify(on_progress, "[9/10] 重启设备...")
        self._adb.reboot(serial)
        self._notify(on_progress, "  等待设备重启完成...")
        self._adb.wait_for_device(serial, timeout=120)
        self._adb.wait_boot_completed(serial, timeout=120)
        self._notify(on_progress, "✓ 设备重启完成")

        self._notify(on_progress, "[10/10] 校验 version...")
        actual_ver = self.get_device_version(serial)
        if actual_ver == target_ver:
            self._notify(on_progress, f"✓ 校验通过！设备 version = {actual_ver}")
        else:
            raise AdbError(
                f"校验失败：期望 version={target_ver}，实际 version={actual_ver}"
            )

        try:
            os.unlink(work_file)
        except OSError:
            pass

        return actual_ver

    # ------------------------------------------------------------------
    # 还原
    # ------------------------------------------------------------------

    def reset(
        self,
        serial: str,
        on_progress: ProgressCallback = None,
    ) -> int:
        """从备份恢复配置，返回最终 version"""
        backup_file = self._get_backup_path(serial)
        if not os.path.isfile(backup_file):
            raise AdbError("无可用备份，无法重置。请先执行一次 push 操作。")

        self._notify(on_progress, "[1/8] 读取设备当前 version...")
        device_ver = self.get_device_version(serial)
        target_ver = device_ver + 1
        self._notify(on_progress, f"  设备当前 version = {device_ver}，重置后 version = {target_ver}")

        self._notify(on_progress, "[2/8] 将备份 version 修改为 设备 version + 1...")
        work_file = self._prepare_work_copy(backup_file, target_ver)
        self._notify(on_progress, "✓ 备份 version 已更新")

        self._notify(on_progress, "[3/8] adb root...")
        self._adb.root(serial)
        self._notify(on_progress, "✓ adb root 成功")

        self._notify(on_progress, "[4/8] adb remount...")
        self._adb.remount(serial, on_progress=on_progress)

        self._notify(on_progress, "[5/8] setenforce 0...")
        self._adb.shell(serial, "setenforce 0")
        self._notify(on_progress, "✓ setenforce 0 成功")

        self._notify(on_progress, f"[6/8] push 备份文件 → {REMOTE_CONFIG_PATH}...")
        try:
            self._adb.push(serial, work_file, REMOTE_CONFIG_PATH)
        finally:
            try:
                os.unlink(work_file)
                os.rmdir(os.path.dirname(work_file))
            except OSError:
                pass
        self._notify(on_progress, "✓ push 备份成功")

        self._notify(on_progress, "[7/8] 重启设备...")
        self._adb.reboot(serial)
        self._notify(on_progress, "  等待设备重启完成...")
        self._adb.wait_for_device(serial, timeout=120)
        self._adb.wait_boot_completed(serial, timeout=120)
        self._notify(on_progress, "✓ 设备重启完成")

        self._notify(on_progress, "[8/8] 校验 version...")
        actual_ver = self.get_device_version(serial)
        if actual_ver == target_ver:
            self._notify(on_progress, f"✓ 设备已重置，当前 version = {actual_ver}")
        else:
            raise AdbError(f"重置后 version 校验异常：期望 {target_ver}，实际 {actual_ver}")

        return actual_ver

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_device_version(self, serial: str) -> int:
        try:
            output = self._adb.shell(serial, f"head -5 {REMOTE_CONFIG_PATH}")
        except AdbError:
            return 0
        match = re.search(r'<GameOptPolicy\s+version\s*=\s*"(\d+)"', output)
        return int(match.group(1)) if match else 0

    def get_info(self, serial: str) -> dict:
        version = self.get_device_version(serial)
        has_backup = self.has_backup(serial)
        return {
            "serial": serial,
            "remote_path": REMOTE_CONFIG_PATH,
            "version": version,
            "has_backup": has_backup,
        }

    def has_backup(self, serial: str) -> bool:
        return os.path.isfile(self._get_backup_path(serial))

    # ------------------------------------------------------------------
    # 配置文件分析（Agent 工具）
    # ------------------------------------------------------------------

    @staticmethod
    def analyze_config(xml_path: str) -> dict:
        """解析 gameperfconfig.xml 并返回结构化策略摘要。

        Agent 可通过此方法获取 CPU/GPU 频点、支持的游戏列表、
        场景策略、温控配置等信息，用于策略审查和优化建议。
        """
        from .parser import GamePerfParser

        p = GamePerfParser(xml_path)
        cpu_clusters = {}
        for name, ci in p.cpu_clusters.items():
            cpu_clusters[name] = {
                "frequencies_mhz": ci.frequencies,
                "count": len(ci.frequencies),
            }
        gpu_freq = {}
        if p.gpu_cluster:
            gpu_freq = {
                "frequencies_mhz": p.gpu_cluster.frequencies,
                "count": len(p.gpu_cluster.frequencies),
            }

        supported_games = []
        for pkg, scenes in p.game_scenes.items():
            from .parser import GAME_ALIAS_MAP
            alias = GAME_ALIAS_MAP.get(pkg, pkg)
            supported_games.append({
                "package": pkg,
                "alias": alias,
                "scene_count": len(scenes),
            })

        scene_policies = []
        for row in p.freq_rows[:30]:
            scene_policies.append(row.to_dict())

        return {
            "xml_path": xml_path,
            "cpu_clusters": cpu_clusters,
            "gpu_freq": gpu_freq,
            "supported_games": supported_games,
            "scene_policies_sample": scene_policies,
            "total_freq_rows": len(p.freq_rows),
        }

    # ------------------------------------------------------------------
    # 从设备拉取配置（US6 / T026）
    # ------------------------------------------------------------------

    @staticmethod
    def _pull_cancelled_result(local_path: str, cache_dir: str) -> AutoDevicePullResult:
        GamePerfService._cleanup_pull_target(local_path, cache_dir)
        return AutoDevicePullResult(
            ok=False,
            user_message="已取消从设备拉取。",
            failure_kind="cancelled",
        )

    def pull_device_config_from_device(
        self,
        serial: str,
        on_progress: ProgressCallback = None,
        cancel_event: threading.Event | None = None,
    ) -> AutoDevicePullResult:
        """将设备上的 ``gameperfconfig.xml`` 拉到本地缓存目录并校验 XML。

        纯读操作（adb pull），不需要 root 权限，避免触发设备 adbd 重启。
        成功时 ``local_path`` 指向 ``data_dir/pull_cache/<serial>/gameperfconfig.xml``。
        ``cancel_event`` 置位后会在各步骤间隙中止（无法打断单次 adb 阻塞调用）。
        """
        serial = (serial or "").strip()
        if not serial:
            return AutoDevicePullResult(
                ok=False,
                user_message="未检测到设备序列号，请连接设备后重试。",
                failure_kind="transport",
            )

        cache_dir = os.path.join(self._data_dir, "pull_cache", self._safe_serial_dir(serial))
        local_path = os.path.join(cache_dir, "gameperfconfig.xml")
        os.makedirs(cache_dir, exist_ok=True)

        def cancelled() -> bool:
            return cancel_event is not None and cancel_event.is_set()

        try:
            if cancelled():
                return self._pull_cancelled_result(local_path, cache_dir)

            self._notify(on_progress, f"[拉取 1/2] pull → {local_path}...")
            self._adb.pull(serial, REMOTE_CONFIG_PATH, local_path)
            self._notify(on_progress, "✓ pull 成功")
            if cancelled():
                return self._pull_cancelled_result(local_path, cache_dir)
        except AdbError as e:
            self._cleanup_pull_target(local_path, cache_dir)
            kind, msg = self._classify_device_pull_error(e)
            return AutoDevicePullResult(
                ok=False,
                user_message=msg,
                failure_kind=kind,
            )
        except Exception as e:
            logger.exception("pull_device_config_from_device 未预期异常")
            self._cleanup_pull_target(local_path, cache_dir)
            return AutoDevicePullResult(
                ok=False,
                user_message=f"从设备拉取失败：{e}",
                failure_kind="transport",
            )

        if cancelled():
            return self._pull_cancelled_result(local_path, cache_dir)

        self._notify(on_progress, "[拉取 2/2] 校验 XML...")
        xml_err = self.validate_xml(local_path)
        if xml_err is not None:
            self._cleanup_pull_target(local_path, cache_dir)
            return AutoDevicePullResult(
                ok=False,
                user_message=(
                    "设备上的配置文件不是合法 XML，无法载入。"
                    f"（第 {xml_err.error_line} 行：{xml_err.error_msg}）"
                ),
                failure_kind="parse",
            )

        self._notify(on_progress, "✓ XML 校验通过")
        return AutoDevicePullResult(
            ok=True,
            user_message="已从设备载入 gameperfconfig.xml。",
            origin=GamePerfDocumentOrigin.DEVICE,
            local_path=local_path,
        )

    @staticmethod
    def _classify_device_pull_error(exc: AdbError) -> tuple[str, str]:
        text = str(exc).lower()
        if (
            "no such file" in text
            or "does not exist" in text
            or "not found" in text
            or "remote object" in text
        ):
            return (
                "missing",
                "设备上未找到 /system/etc/gameperfconfig.xml，或路径不可访问。",
            )
        if "permission" in text or "denied" in text:
            return (
                "permission",
                "无法读取设备上的配置文件，请确认设备已 root 且 remount 成功。",
            )
        return ("transport", f"从设备拉取失败：{exc}")

    @staticmethod
    def _cleanup_pull_target(local_path: str, cache_dir: str) -> None:
        try:
            if os.path.isfile(local_path):
                os.unlink(local_path)
        except OSError:
            pass
        try:
            if os.path.isdir(cache_dir) and not os.listdir(cache_dir):
                os.rmdir(cache_dir)
        except OSError:
            pass

    @staticmethod
    def _safe_serial_dir(serial: str) -> str:
        return re.sub(r'[\\/:*?"<>|]', "_", serial)

    # ------------------------------------------------------------------
    # XML 校验
    # ------------------------------------------------------------------

    @staticmethod
    def validate_xml(filepath: str) -> XmlErrorContext | None:
        try:
            ET.parse(filepath)
            return None
        except ET.ParseError as e:
            line_no, col = e.position
            try:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
            except Exception:
                all_lines = []

            ctx = XmlErrorContext(
                error_msg=str(getattr(e, "msg", str(e))),
                error_line=line_no,
                error_col=col,
            )
            start = max(0, line_no - 4)
            end = min(len(all_lines), line_no + 3)
            for i in range(start, end):
                is_err = i + 1 == line_no
                ctx.context_lines.append((i + 1, all_lines[i].rstrip("\n\r"), is_err))
            return ctx
        except Exception as e:
            return XmlErrorContext(error_msg=str(e), error_line=0, error_col=0)

    # ------------------------------------------------------------------
    # 推送记录
    # ------------------------------------------------------------------

    def save_push_record(
        self,
        record: PushRecord,
        db_manager=None,
    ) -> str:
        """JSON + DB 双写，返回 JSON 文件路径"""
        safe_pkg = re.sub(r'[\\/:*?"<>|]', "_", record.package)
        record_dir = os.path.join(self._data_dir, "push_records", safe_pkg)
        os.makedirs(record_dir, exist_ok=True)

        filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
        json_path = os.path.join(record_dir, filename)
        record.json_path = json_path

        payload = record.to_dict()
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("保存推送记录 JSON 失败: %s", e)

        if db_manager is not None:
            try:
                db_manager.execute(
                    """INSERT INTO perf_push_history
                       (game, package, mode, notes, version, json_path, saved_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record.game, record.package, record.mode,
                        record.notes, record.version, json_path,
                        record.saved_at or datetime.now().isoformat(),
                    ),
                )
            except Exception as e:
                logger.error("保存推送记录 DB 失败: %s", e)

        return json_path

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _backup_device_config(self, serial: str) -> str:
        backup_dir = self._get_backup_dir(serial)
        backup_file = os.path.join(backup_dir, "gameperfconfig.xml")
        tmp_dir = tempfile.mkdtemp()
        tmp_file = os.path.join(tmp_dir, "gameperfconfig.xml")
        try:
            self._adb.pull(serial, REMOTE_CONFIG_PATH, tmp_file)
            shutil.move(tmp_file, backup_file)
        except AdbError:
            if os.path.isfile(backup_file):
                return backup_file
            raise
        finally:
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass
        return backup_file

    def _get_backup_dir(self, serial: str) -> str:
        from toolkit.core.app_paths import get_backup_path

        safe_serial = self._safe_serial_dir(serial)
        path = str(get_backup_path("game_perf", safe_serial))
        os.makedirs(path, exist_ok=True)
        return path

    def _get_backup_path(self, serial: str) -> str:
        return os.path.join(self._get_backup_dir(serial), "gameperfconfig.xml")

    @staticmethod
    def _prepare_work_copy(src: str, target_version: int) -> str:
        tmp_dir = tempfile.mkdtemp()
        work_file = os.path.join(tmp_dir, os.path.basename(src))
        shutil.copy2(src, work_file)

        with open(work_file, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.search(r'<GameOptPolicy\s+version\s*=\s*"(\d+)"', content)
        if match:
            new_content = content.replace(
                match.group(0), f'<GameOptPolicy version = "{target_version}"'
            )
            with open(work_file, "w", encoding="utf-8") as f:
                f.write(new_content)

        return work_file

    @staticmethod
    def _notify(callback: ProgressCallback, message: str) -> None:
        if callback:
            callback(message)


class XmlValidationError(Exception):
    """XML 格式校验失败"""

    def __init__(self, context: XmlErrorContext) -> None:
        self.context = context
        super().__init__(f"XML 格式错误（第 {context.error_line} 行）: {context.error_msg}")
