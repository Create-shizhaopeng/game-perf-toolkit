"""性能诊断工具 — 耗时打点 + 主线程卡死检测。

设计目标：补齐 debug 模式缺失的"启动耗时、主线程阻塞、慢 ADB"观测能力。

提供三个能力（均走统一 logging 体系，不依赖 GUI 面板）：

1. ``TimeIt`` 上下文管理器 / ``timed`` 装饰器
   测量任意代码段耗时。超过 ``min_ms`` 阈值时输出 warning（慢操作告警），
   否则在 debug 模式下输出 debug 日志（阶段耗时明细）。

2. ``MainThreadWatchdog`` + ``start_main_thread_heartbeat``
   后台 QThread 监测主线程心跳。主线程事件循环正常时由 QTimer 定期更新
   心跳时间戳；若主线程被阻塞（如同步 ADB、大文件扫描），心跳停止更新，
   超过阈值后 watchdog 自动 dump 主线程堆栈到日志 —— 解决"卡死但无日志"。

3. ``set_debug_enabled`` / ``is_debug_enabled``
   由 app.py 根据 ``--debug`` 参数统一控制。

使用示例::

    from toolkit.core.perf_debug import TimeIt, timed

    with TimeIt("adb devices", min_ms=500):
        devices = adb.get_connected_devices()

    @timed(min_ms=200)
    def on_activated(self):
        ...
"""

from __future__ import annotations

import logging
import sys
import threading
import time
import traceback
from functools import wraps

from PyQt6.QtCore import QObject, QThread, QTimer

LOGGER = logging.getLogger(__name__)

_debug_enabled = False


def set_debug_enabled(enabled: bool) -> None:
    """全局开关：是否处于 debug 模式（由 app.py 根据 --debug 设置）。"""
    global _debug_enabled
    _debug_enabled = bool(enabled)


def is_debug_enabled() -> bool:
    return _debug_enabled


# ---------------------------------------------------------------------------
# 1. 耗时打点
# ---------------------------------------------------------------------------


class TimeIt:
    """耗时打点上下文管理器。

    Args:
        label: 打点名称（写入日志）
        min_ms: 超过该毫秒数输出 warning（慢操作告警），否则 debug 输出。
                设 0 时所有调用仅输出 debug 明细。
    """

    __slots__ = ("_label", "_min_ms", "_start")

    def __init__(self, label: str, min_ms: int = 0) -> None:
        self._label = label
        self._min_ms = min_ms
        self._start = 0.0

    def __enter__(self) -> "TimeIt":
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        elapsed_s = time.perf_counter() - self._start
        elapsed_ms = elapsed_s * 1000.0
        if elapsed_ms >= self._min_ms:
            LOGGER.warning("[perf] %s 耗时 %.1fms（超过阈值 %.0fms）",
                           self._label, elapsed_ms, self._min_ms)
        elif is_debug_enabled():
            LOGGER.debug("[perf] %s 耗时 %.1fms", self._label, elapsed_ms)
        return False


def timed(min_ms: int = 0):
    """耗时打点装饰器 — 包裹函数调用，语义同 TimeIt。"""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            label = f"{fn.__qualname__}()"
            with TimeIt(label, min_ms=min_ms):
                return fn(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# 2. 主线程卡死检测
# ---------------------------------------------------------------------------

# 主线程心跳（进程级单例共享给所有 watchdog 实例）
_heartbeat: dict[str, float] = {"last": 0.0, "tick": 0}


def touch_main_thread_heartbeat() -> None:
    """主线程心跳更新（由 QTimer 驱动，仅主线程调用）。"""
    _heartbeat["last"] = time.monotonic()
    _heartbeat["tick"] += 1


def _heartbeat_snapshot() -> tuple[float, int]:
    return _heartbeat["last"], _heartbeat["tick"]


def start_main_thread_heartbeat(parent: QObject, interval_ms: int = 500) -> QTimer:
    """启动主线程心跳定时器。返回 QTimer（由 parent 生命周期管理）。

    事件循环空闲时每 interval_ms 更新一次心跳；主线程一旦阻塞，
    心跳停止更新，MainThreadWatchdog 即可据此判定卡死。
    """
    timer = QTimer(parent)
    timer.timeout.connect(touch_main_thread_heartbeat)
    timer.start(interval_ms)
    touch_main_thread_heartbeat()  # 立即建立基线
    return timer


class MainThreadWatchdog(QThread):
    """主线程卡死检测线程。

    后台线程周期性比对主线程心跳时间。心跳超过 timeout_s 未更新则判定
    主线程疑似卡死，dump 主线程堆栈到日志（warning 级别，自动弹面板）。

    Args:
        timeout_s: 心跳超时阈值（秒），默认 5s
        interval_s: 检测周期（秒），默认 1s
        parent: QObject 父对象
    """

    def __init__(self, timeout_s: float = 5.0, interval_s: float = 1.0,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timeout_s = timeout_s
        self._interval_s = max(0.2, interval_s)
        self._stop = threading.Event()
        self._last_alert_tick = -1

    def run(self) -> None:
        while not self._stop.is_set():
            self._check_once()
            self._stop.wait(self._interval_s)

    def stop_watchdog(self) -> None:
        """请求停止检测线程（线程内 wait 会在 interval 内退出）。"""
        self._stop.set()
        self.wait(2000)

    def _check_once(self) -> None:
        last, tick = _heartbeat_snapshot()
        age = time.monotonic() - last
        if age <= self._timeout_s:
            return
        # 同一卡死只告警一次（心跳恢复后 tick 变化才重置）
        if tick == self._last_alert_tick:
            return
        self._last_alert_tick = tick
        stack = self._format_main_thread_stack()
        LOGGER.warning(
            "[perf] 主线程疑似卡死 %.1fs（心跳 tick=%d）%s",
            age, tick, ("，堆栈:\n" + stack) if stack else "",
        )

    @staticmethod
    def _format_main_thread_stack() -> str:
        """返回主线程当前调用栈（格式化字符串），取不到返回空串。"""
        try:
            frames = sys._current_frames()
            main_ident = threading.main_thread().ident
            frame = frames.get(main_ident)
            if frame is None:
                return ""
            return "".join(traceback.format_stack(frame))
        except Exception:
            return ""
