import os
import re
import shutil
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

from core.adb_manager import AdbManager, AdbRootError, AdbNotFoundError, AdbError


REMOTE_CONFIG_PATH = "/system/etc/gameperfconfig.xml"


def is_valid_config_filename(filepath: str) -> bool:
    """文件名须包含完整子串 gameperfconfig 且扩展名为 .xml 才视为有效策略配置。"""
    name = os.path.basename(filepath)
    return "gameperfconfig" in name and name.lower().endswith(".xml")


@dataclass
class XmlErrorContext:
    """XML 解析错误及其上下文行"""
    error_msg: str
    error_line: int
    error_col: int
    context_lines: List[Tuple[int, str, bool]] = field(default_factory=list)


class PushPolicyService(QThread):
    progress = pyqtSignal(str)
    error = pyqtSignal(str)
    xml_error = pyqtSignal(object)  # XmlErrorContext
    finished_signal = pyqtSignal(bool, str)  # (success, message)

    def __init__(self, adb_manager: AdbManager, data_dir: str, parent=None):
        super().__init__(parent)
        self._adb = adb_manager
        self._data_dir = data_dir
        self._action: Optional[str] = None
        self._config_file: str = ""

    def _backup_dir(self) -> str:
        devices = self._adb.get_connected_devices()
        serial = devices[0] if devices else "unknown"
        safe_serial = re.sub(r'[\\/:*?"<>|]', '_', serial)
        path = os.path.join(self._data_dir, "backups", safe_serial)
        os.makedirs(path, exist_ok=True)
        return path

    def validate_xml(self, filepath: str) -> Optional[XmlErrorContext]:
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
                error_msg=str(e.msg) if hasattr(e, 'msg') else str(e),
                error_line=line_no,
                error_col=col,
            )

            start = max(0, line_no - 4)
            end = min(len(all_lines), line_no + 3)
            for i in range(start, end):
                is_error_line = (i + 1 == line_no)
                line_text = all_lines[i].rstrip('\n\r')
                ctx.context_lines.append((i + 1, line_text, is_error_line))

            return ctx
        except Exception as e:
            return XmlErrorContext(
                error_msg=str(e),
                error_line=0,
                error_col=0,
            )

    def push(self, config_file: str):
        self._action = "push"
        self._config_file = config_file
        self.start()

    def reset(self):
        self._action = "reset"
        self.start()

    def run(self):
        try:
            if self._action == "push":
                self._run_push()
            elif self._action == "reset":
                self._run_reset()
        except AdbRootError as e:
            self.error.emit(str(e))
        except AdbNotFoundError as e:
            self.error.emit(str(e))
        except AdbError as e:
            self.error.emit(f"ADB 错误: {e}")
        except Exception as e:
            self.error.emit(f"未知错误: {e}")

    def _run_push(self):
        if not os.path.isfile(self._config_file):
            self.error.emit(f"配置文件不存在: {self._config_file}")
            return
        if not is_valid_config_filename(self._config_file):
            self.error.emit(
                "无效的配置文件：文件名须包含 gameperfconfig 且扩展名为 .xml（如 gameperfconfig（11）.xml、aaagameperfconfig.xml）"
            )
            return

        self.progress.emit("[1/10] XML 格式检查...")
        xml_err = self.validate_xml(self._config_file)
        if xml_err is not None:
            self.xml_error.emit(xml_err)
            self.error.emit("XML 格式检查未通过，已终止推送")
            return
        self.progress.emit("✓ XML 格式检查通过")

        self.progress.emit("[2/10] 读取设备配置文件 version...")
        device_ver = self._get_device_version()
        target_ver = device_ver + 1
        self.progress.emit(f"  设备当前 version = {device_ver}，目标 version = {target_ver}")

        self.progress.emit("[3/10] 修改本地文件 version...")
        work_file = self._prepare_work_copy(self._config_file, target_ver)
        self.progress.emit(f"✓ 本地 version 已更新为 {target_ver}")

        self.progress.emit("[4/10] adb root...")
        self._adb.run_cmd(["root"], timeout=15)
        self.progress.emit("✓ adb root 成功")

        self.progress.emit("[5/10] adb remount...")
        self._adb.run_cmd(["remount"], timeout=15)
        self.progress.emit("✓ adb remount 成功")

        self.progress.emit("[6/10] setenforce 0...")
        self._adb.run_cmd(["shell", "setenforce", "0"], timeout=10)
        self.progress.emit("✓ setenforce 0 成功")

        self.progress.emit("[7/10] 备份设备当前配置...")
        backup_file = self._backup_device_config()
        self.progress.emit(f"✓ 已备份到 {backup_file}")

        self.progress.emit(f"[8/10] push → {REMOTE_CONFIG_PATH}...")
        self._adb.run_cmd(["push", work_file, REMOTE_CONFIG_PATH], timeout=30)
        self.progress.emit("✓ push 成功")

        self.progress.emit("[9/10] 重启设备...")
        self._adb.run_cmd(["reboot"], timeout=10)
        self.progress.emit("  等待设备重启完成...")
        self._adb.run_cmd(["wait-for-device"], timeout=120)
        self._wait_boot_completed()
        self.progress.emit("✓ 设备重启完成")

        self.progress.emit("[10/10] 校验 version...")
        actual_ver = self._get_device_version()
        if actual_ver == target_ver:
            self.progress.emit(f"✓ 校验通过！设备 version = {actual_ver}")
            self.finished_signal.emit(True, f"推送成功，version = {actual_ver}")
        else:
            msg = f"校验失败：期望 version={target_ver}，实际 version={actual_ver}"
            self.error.emit(msg)
            self.finished_signal.emit(False, msg)

        try:
            os.unlink(work_file)
        except OSError:
            pass

    def _run_reset(self):
        backup_dir = self._backup_dir()
        backup_file = os.path.join(backup_dir, "gameperfconfig.xml")
        if not os.path.isfile(backup_file):
            self.error.emit("无可用备份，无法重置。请先执行一次 push 操作。")
            return

        self.progress.emit("[1/8] 读取设备当前 version...")
        device_ver = self._get_device_version()
        target_ver = device_ver + 1
        self.progress.emit(f"  设备当前 version = {device_ver}，重置后 version = {target_ver}")

        self.progress.emit("[2/8] 将备份 version 修改为 设备 version + 1...")
        work_file = self._prepare_work_copy(backup_file, target_ver)
        self.progress.emit("✓ 备份 version 已更新")

        self.progress.emit("[3/8] adb root...")
        self._adb.run_cmd(["root"], timeout=15)
        self.progress.emit("✓ adb root 成功")

        self.progress.emit("[4/8] adb remount...")
        self._adb.run_cmd(["remount"], timeout=15)
        self.progress.emit("✓ adb remount 成功")

        self.progress.emit("[5/8] setenforce 0...")
        self._adb.run_cmd(["shell", "setenforce", "0"], timeout=10)
        self.progress.emit("✓ setenforce 0 成功")

        self.progress.emit(f"[6/8] push 备份文件 → {REMOTE_CONFIG_PATH}...")
        try:
            self._adb.run_cmd(["push", work_file, REMOTE_CONFIG_PATH], timeout=30)
        finally:
            try:
                os.unlink(work_file)
                os.rmdir(os.path.dirname(work_file))
            except OSError:
                pass
        self.progress.emit("✓ push 备份成功")

        self.progress.emit("[7/8] 重启设备...")
        self._adb.run_cmd(["reboot"], timeout=10)
        self.progress.emit("  等待设备重启完成...")
        self._adb.run_cmd(["wait-for-device"], timeout=120)
        self._wait_boot_completed()
        self.progress.emit("✓ 设备重启完成")

        self.progress.emit("[8/8] 校验 version...")
        actual_ver = self._get_device_version()
        if actual_ver == target_ver:
            self.progress.emit(f"✓ 设备已重置，当前 version = {actual_ver}")
            self.finished_signal.emit(True, f"重置成功，version = {actual_ver}")
        else:
            self.error.emit(f"重置后 version 校验异常：期望 {target_ver}，实际 {actual_ver}")
            self.finished_signal.emit(False, "")

    def _get_device_version(self) -> int:
        try:
            output = self._adb.run_cmd(
                ["shell", "head", "-5", REMOTE_CONFIG_PATH], timeout=10
            )
        except AdbError:
            return 0
        match = re.search(r'<GameOptPolicy\s+version\s*=\s*"(\d+)"', output)
        return int(match.group(1)) if match else 0

    def _read_version_from_file(self, filepath: str) -> Optional[int]:
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                head = f.read(1024)
            match = re.search(r'<GameOptPolicy\s+version\s*=\s*"(\d+)"', head)
            return int(match.group(1)) if match else None
        except Exception:
            return None

    def _prepare_work_copy(self, src: str, target_version: int) -> str:
        tmp_dir = tempfile.mkdtemp()
        work_file = os.path.join(tmp_dir, os.path.basename(src))
        shutil.copy2(src, work_file)

        with open(work_file, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.search(r'<GameOptPolicy\s+version\s*=\s*"(\d+)"', content)
        if match:
            new_content = content.replace(
                match.group(0),
                f'<GameOptPolicy version = "{target_version}"',
            )
            with open(work_file, "w", encoding="utf-8") as f:
                f.write(new_content)

        return work_file

    def _backup_device_config(self) -> str:
        backup_dir = self._backup_dir()
        backup_file = os.path.join(backup_dir, "gameperfconfig.xml")
        tmp_dir = tempfile.mkdtemp()
        tmp_file = os.path.join(tmp_dir, "gameperfconfig.xml")
        try:
            self._adb.run_cmd(["pull", REMOTE_CONFIG_PATH, tmp_file], timeout=15)
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

    def _wait_boot_completed(self, timeout: int = 120):
        start = time.time()
        while time.time() - start < timeout:
            try:
                val = self._adb.get_prop("sys.boot_completed")
                if val == "1":
                    return
            except Exception:
                pass
            time.sleep(2)
        raise AdbError("等待设备启动超时")

    def has_backup(self) -> bool:
        try:
            backup_dir = self._backup_dir()
            backup_file = os.path.join(backup_dir, "gameperfconfig.xml")
            return os.path.isfile(backup_file)
        except Exception:
            return False
