"""perf_debug 诊断工具测试 — TimeIt 耗时打点 / timed 装饰器 / 主线程卡死检测。"""

from __future__ import annotations

import logging
import time

import pytest

from toolkit.core import perf_debug as pd


# 每个测试前重置 debug 开关（避免跨测试污染）
@pytest.fixture(autouse=True)
def _reset_debug():
    pd.set_debug_enabled(False)
    yield
    pd.set_debug_enabled(False)


def _caplog(caplog, level: int, logger_name: str = "toolkit.core.perf_debug"):
    return caplog.at_level(level, logger=logger_name)


# ===========================================================================
# debug 开关
# ===========================================================================


class TestDebugToggle:
    def test_set_debug_enabled_toggle(self) -> None:
        assert pd.is_debug_enabled() is False
        pd.set_debug_enabled(True)
        assert pd.is_debug_enabled() is True
        pd.set_debug_enabled(False)
        assert pd.is_debug_enabled() is False

    def test_debug_default_false(self) -> None:
        assert pd.is_debug_enabled() is False


# ===========================================================================
# TimeIt
# ===========================================================================


class TestTimeIt:
    def test_slow_op_emits_warning(self, caplog) -> None:
        with _caplog(caplog, logging.WARNING):
            with pd.TimeIt("slow_op", min_ms=1):
                time.sleep(0.01)
        assert "slow_op" in caplog.text
        assert "超过阈值" in caplog.text

    def test_fast_op_debug_only_when_enabled(self, caplog) -> None:
        pd.set_debug_enabled(True)
        with _caplog(caplog, logging.DEBUG):
            with pd.TimeIt("fast_op", min_ms=1000):
                pass
        assert "fast_op" in caplog.text
        assert "超过阈值" not in caplog.text

    def test_fast_op_silent_when_disabled(self, caplog) -> None:
        with _caplog(caplog, logging.DEBUG):
            with pd.TimeIt("fast_op", min_ms=1000):
                pass
        assert "fast_op" not in caplog.text

    def test_fast_op_below_threshold_no_warning(self, caplog) -> None:
        pd.set_debug_enabled(True)
        with _caplog(caplog, logging.WARNING):
            with pd.TimeIt("fast_op", min_ms=1000):
                pass
        assert "超过阈值" not in caplog.text

    def test_timeit_does_not_swallow_exception(self) -> None:
        with pytest.raises(ValueError):
            with pd.TimeIt("raise_op", min_ms=1):
                raise ValueError("boom")


# ===========================================================================
# timed 装饰器
# ===========================================================================


class TestTimed:
    def test_decorator_preserves_result(self) -> None:
        @pd.timed(min_ms=1000)
        def add(a: int, b: int) -> int:
            return a + b

        assert add(1, 2) == 3

    def test_decorator_emits_warning_on_slow(self, caplog) -> None:
        @pd.timed(min_ms=1)
        def slow_fn() -> None:
            time.sleep(0.01)

        with _caplog(caplog, logging.WARNING):
            slow_fn()
        assert "slow_fn()" in caplog.text
        assert "超过阈值" in caplog.text

    def test_decorator_propagates_exception(self) -> None:
        @pd.timed(min_ms=1)
        def boom() -> None:
            raise RuntimeError("x")

        with pytest.raises(RuntimeError):
            boom()


# ===========================================================================
# 主线程心跳
# ===========================================================================


class TestHeartbeat:
    def test_touch_main_thread_heartbeat(self) -> None:
        pd.touch_main_thread_heartbeat()
        last, tick = pd._heartbeat_snapshot()
        assert last > 0
        assert tick >= 1

    def test_heartbeat_monotonic(self) -> None:
        pd.touch_main_thread_heartbeat()
        last1, tick1 = pd._heartbeat_snapshot()
        time.sleep(0.01)
        pd.touch_main_thread_heartbeat()
        last2, tick2 = pd._heartbeat_snapshot()
        assert last2 >= last1
        assert tick2 == tick1 + 1


# ===========================================================================
# MainThreadWatchdog
# ===========================================================================


class TestMainThreadWatchdog:
    def test_fresh_heartbeat_no_alert(self, caplog) -> None:
        pd.touch_main_thread_heartbeat()  # 心跳新鲜
        w = pd.MainThreadWatchdog(timeout_s=5.0, interval_s=0.2)
        with _caplog(caplog, logging.WARNING):
            w._check_once()
        assert "主线程疑似卡死" not in caplog.text

    def test_stale_heartbeat_alerts_with_stack(self, caplog) -> None:
        pd.touch_main_thread_heartbeat()
        w = pd.MainThreadWatchdog(timeout_s=5.0, interval_s=0.2)
        # 模拟主线程阻塞：把心跳时间戳拨回过去
        pd._heartbeat["last"] = time.monotonic() - 10
        with _caplog(caplog, logging.WARNING):
            w._check_once()
        assert "主线程疑似卡死" in caplog.text

    def test_same_stall_alerts_once(self, caplog) -> None:
        pd.touch_main_thread_heartbeat()
        w = pd.MainThreadWatchdog(timeout_s=5.0, interval_s=0.2)
        pd._heartbeat["last"] = time.monotonic() - 10
        with _caplog(caplog, logging.WARNING):
            w._check_once()
            caplog.clear()
            w._check_once()  # 同一 tick，不应重复告警
        assert "主线程疑似卡死" not in caplog.text

    def test_recovered_heartbeat_alerts_again(self, caplog) -> None:
        pd.touch_main_thread_heartbeat()
        w = pd.MainThreadWatchdog(timeout_s=5.0, interval_s=0.2)
        pd._heartbeat["last"] = time.monotonic() - 10
        with _caplog(caplog, logging.WARNING):
            w._check_once()
            assert "主线程疑似卡死" in caplog.text
        # 心跳恢复（tick 变化）后再次卡死 → 再次告警
        pd.touch_main_thread_heartbeat()
        pd._heartbeat["last"] = time.monotonic() - 10
        with _caplog(caplog, logging.WARNING):
            w._check_once()
        assert "主线程疑似卡死" in caplog.text

    def test_format_main_thread_stack(self) -> None:
        stack = pd.MainThreadWatchdog._format_main_thread_stack()
        assert "test_format_main_thread_stack" in stack

    def test_thread_start_stop(self) -> None:
        w = pd.MainThreadWatchdog(timeout_s=5.0, interval_s=0.2)
        w.start()
        assert w.isRunning()
        w.stop_watchdog()
        assert not w.isRunning()


# ===========================================================================
# start_main_thread_heartbeat（依赖 QCoreApplication）
# ===========================================================================


class TestStartHeartbeatTimer:
    def test_timer_starts_and_touches_heartbeat(self) -> None:
        from PyQt6.QtCore import QCoreApplication

        app = QCoreApplication.instance() or QCoreApplication([])
        before, _ = pd._heartbeat_snapshot()
        timer = pd.start_main_thread_heartbeat(app, interval_ms=50)
        assert timer.isActive()
        after, tick = pd._heartbeat_snapshot()
        assert after >= before
        assert tick >= 1
        timer.stop()
