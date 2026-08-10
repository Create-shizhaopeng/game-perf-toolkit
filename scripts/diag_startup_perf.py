"""启动/切 tab 性能诊断脚本 — 定位主线程卡死点。

用法:
    .venv/Scripts/python scripts/diag_startup_perf.py

原理:
    1. 设置 QT_QPA_PLATFORM=offscreen 无头创建 QApplication
    2. 开启 faulthandler.dump_traceback_later(1) — 若某处阻塞 >1s，
       自动 dump 当前堆栈，精确定位卡住的位置
    3. 分阶段计时: _build_context → _load_plugins → MainWindow →
       逐个 add_tab → 逐个 _on_tab_selected → adb poll → scan_sessions
    4. 输出每步耗时，找出卡死点
"""

from __future__ import annotations

import faulthandler
import logging
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# 开启 faulthandler：每 3s dump 一次堆栈（用于抓阻塞点）
faulthandler.dump_traceback_later(3, repeat=True)
faulthandler.enable()

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def t(label: str) -> None:
    global _last
    now = time.perf_counter()
    print(f"[{now - _last:8.3f}s] {label}")
    _last = now


_last = time.perf_counter()

# 1. 构建上下文
from toolkit.app import _build_context, _load_plugins

t("开始 _build_context")
context = _build_context()
t("_build_context 完成")

# 2. 加载插件（含 on_startup）
t("开始 _load_plugins")
pm = _load_plugins(context)
context["plugin_manager"] = pm
t(f"_load_plugins 完成 ({len(pm.loaded_modules)} 模块)")

# 3. 构建 MainWindow — 拆成子步骤定位
import sys as _sys

def _mstep(label: str) -> None:
    print(f"      [sub] {label}", flush=True)
    global _last
    now = time.perf_counter()
    print(f"      [sub]   (本次间隔 {now - _last:.3f}s)", flush=True)
    _last = now

from PyQt6.QtWidgets import QApplication
app = QApplication([])
_mstep("QApplication 创建完成")

t("开始 MainWindow 构建")
from toolkit.gui.main_window import MainWindow
_mstep("import MainWindow 完成")
window = MainWindow(context)
_mstep("MainWindow 实例化完成")
t("MainWindow 构建完成")

# 4. 模拟 run_gui 中 register_gui_tab + add_tab
tabs = pm.pm.hook.register_gui_tab()
for tab in tabs:
    if tab is None:
        continue
    tt = time.perf_counter()
    window.add_tab(tab)
    print(f"    add_tab '{tab.tab_title}': {time.perf_counter() - tt:.3f}s")
t(f"add_tab 完成 ({len([x for x in tabs if x])} tabs)")

# 5. 模拟 _on_tab_selected 遍历每个 tab（切 tab 路径）
from toolkit.core.adb_manager import AdbManager
adb = window._adb_manager

t("开始切 tab 遍历")
for i in range(len(window._tabs)):
    tab = window._tabs[i]
    tt = time.perf_counter()
    try:
        window._on_tab_selected(i)
    except Exception as e:
        print(f"    !! _on_tab_selected({i}) 异常: {e}")
    print(
        f"    切到 '{tab.tab_title}': {time.perf_counter() - tt:.3f}s"
        f"  (on_activated={tab.__class__.__name__})"
    )
t("切 tab 遍历完成")

# 6. 模拟 DeviceMonitor._poll（主线程 adb 调用）
t("开始 DeviceMonitor._poll")
try:
    tt = time.perf_counter()
    window._device_monitor._poll()
    print(f"    _poll 完成: {time.perf_counter() - tt:.3f}s")
except Exception as e:
    print(f"    !! _poll 异常: {e}")
t("_poll 完成")

# 7. 模拟设备连接场景（慢 adb mock）：触发 on_devices_changed + 切 tab
print("\n=== 模拟设备连接场景（adb 慢响应 mock）===", flush=True)
import toolkit.core.adb_manager as adb_mod

_orig_run = adb_mod.AdbManager._run_cmd_raw

def _slow_adb(self, args, timeout=30, input_text=None):
    """模拟慢 adb：每个命令 sleep 0.8s（真实设备假死/慢响应场景）。"""
    import time as _t
    _t.sleep(0.8)
    return _orig_run(self, args, timeout=timeout, input_text=input_text)

adb_mod.AdbManager._run_cmd_raw = _slow_adb

# 8. 触发设备变化（模拟 DeviceMonitor 检测到设备连接）
t("触发 _on_devices_changed(['FAKE_DEV'])")
tt = time.perf_counter()
try:
    window._on_devices_changed(["FAKE_DEV"])
    print(f"    _on_devices_changed 完成: {time.perf_counter() - tt:.3f}s")
except Exception as e:
    print(f"    !! _on_devices_changed 异常: {type(e).__name__}: {e}")
t("设备变化处理完成")

# 9. 模拟带设备时的切 tab 遍历
t("开始带设备切 tab")
for i in range(len(window._tabs)):
    tab = window._tabs[i]
    tt = time.perf_counter()
    try:
        window._on_tab_selected(i)
    except Exception as e:
        print(f"    !! _on_tab_selected({i}) 异常: {type(e).__name__}: {e}")
    print(
        f"    切到 '{tab.tab_title}': {time.perf_counter() - tt:.3f}s"
        f"  (on_activated={tab.__class__.__name__})",
        flush=True,
    )
t("带设备切 tab 遍历完成")

# 恢复
adb_mod.AdbManager._run_cmd_raw = _orig_run

# 10. 实测 scan_sessions 耗时
try:
    from modules.perfetto_capture.src.history_service import HistoryService
    from modules.perfetto_capture.src.history_storage import HistoryStorage
    from modules.perfetto_capture.src.models import HistoryConfig

    output_dir = ROOT / "data" / "output"
    storage = HistoryStorage(ROOT / "data" / "db" / "perfetto_capture_history.db")
    svc = HistoryService(storage, output_dir, HistoryConfig())
    tt = time.perf_counter()
    sessions = svc.scan_sessions()
    print(f"    scan_sessions: {time.perf_counter() - tt:.3f}s ({len(sessions)} 会话)")
except Exception as e:
    print(f"    !! scan_sessions 异常: {e}")
t("scan_sessions 完成")

print("\n=== 诊断结束 ===")
