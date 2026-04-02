"""Jank 监控服务测试"""

import pytest

from modules.perfetto_capture.src.jank_service import JankMonitorService

TEST_SERIAL = "test-device-001"


class MockAdbManager:
    """模拟 ADB 管理器。"""

    def __init__(self):
        self._shell_responses = {}

    def set_shell_response(self, cmd_pattern: str, output: str):
        self._shell_responses[cmd_pattern] = output

    def shell(self, serial: str, cmd: str) -> str:
        for pattern, output in self._shell_responses.items():
            if pattern in cmd:
                return output
        return ""


class TestJankMonitorService:
    """测试 Jank 监控服务。"""

    def test_get_running_apps_empty(self):
        adb = MockAdbManager()
        adb.set_shell_response("pm list packages -3", "")

        svc = JankMonitorService(adb, TEST_SERIAL)
        apps = svc.get_running_apps()

        assert len(apps) == 0

    def test_get_running_apps_with_packages(self):
        adb = MockAdbManager()
        adb.set_shell_response(
            "pm list packages -3",
            "package:com.example.app1\npackage:com.example.app2\npackage:com.test.game\n",
        )
        adb.set_shell_response("dumpsys activity activities", "")

        svc = JankMonitorService(adb, TEST_SERIAL)
        apps = svc.get_running_apps()

        assert len(apps) == 3
        assert apps[0].package_name == "com.example.app1"
        assert apps[1].package_name == "com.example.app2"
        assert apps[2].package_name == "com.test.game"

    def test_get_running_apps_with_foreground(self):
        adb = MockAdbManager()
        adb.set_shell_response(
            "pm list packages -3",
            "package:com.example.app1\npackage:com.example.app2\n",
        )
        adb.set_shell_response(
            "dumpsys activity activities",
            "mResumedActivity: ActivityRecord{abc123 u0 com.example.app2/MainActivity t123}",
        )

        svc = JankMonitorService(adb, TEST_SERIAL)
        apps = svc.get_running_apps()

        assert apps[0].package_name == "com.example.app2"
        assert apps[0].is_foreground is True
        assert apps[1].is_foreground is False


class TestDisplayRefreshRate:
    """测试屏幕刷新率检测。"""

    def test_parse_60hz(self):
        adb = MockAdbManager()
        adb.set_shell_response(
            "dumpsys display",
            "mActiveMode: {id=1, width=1080, height=2340, fps=60.0Hz}",
        )

        svc = JankMonitorService(adb, TEST_SERIAL)
        rate = svc.get_display_refresh_rate(use_cache=False)

        assert rate == 60

    def test_parse_90hz(self):
        adb = MockAdbManager()
        adb.set_shell_response(
            "dumpsys display",
            "refreshRate: 90.00Hz",
        )

        svc = JankMonitorService(adb, TEST_SERIAL)
        rate = svc.get_display_refresh_rate(use_cache=False)

        assert rate == 90

    def test_parse_120hz(self):
        adb = MockAdbManager()
        adb.set_shell_response(
            "dumpsys display",
            "mActiveMode: {id=2, width=1440, height=3200, fps=120Hz}",
        )

        svc = JankMonitorService(adb, TEST_SERIAL)
        rate = svc.get_display_refresh_rate(use_cache=False)

        assert rate == 120

    def test_fallback_to_60hz(self):
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys display", "no valid data here")

        svc = JankMonitorService(adb, TEST_SERIAL)
        rate = svc.get_display_refresh_rate(use_cache=False)

        assert rate == 60

    def test_cache_refresh_rate(self):
        adb = MockAdbManager()
        adb.set_shell_response(
            "dumpsys display",
            "refreshRate: 90Hz",
        )

        svc = JankMonitorService(adb, TEST_SERIAL)
        rate1 = svc.get_display_refresh_rate(use_cache=False)
        adb.set_shell_response("dumpsys display", "refreshRate: 60Hz")
        rate2 = svc.get_display_refresh_rate(use_cache=True)

        assert rate1 == 90
        assert rate2 == 90

    def test_clear_cache(self):
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys display", "refreshRate: 90Hz")

        svc = JankMonitorService(adb, TEST_SERIAL)
        svc.get_display_refresh_rate(use_cache=False)
        svc.clear_cache()
        adb.set_shell_response("dumpsys display", "refreshRate: 60Hz")
        rate = svc.get_display_refresh_rate(use_cache=True)

        assert rate == 60


class TestForegroundDetection:
    """测试前台应用检测。"""

    def test_is_foreground_true(self):
        adb = MockAdbManager()
        adb.set_shell_response(
            "dumpsys activity activities",
            "mResumedActivity: ActivityRecord{abc u0 com.example.game/MainActivity t1}",
        )

        svc = JankMonitorService(adb, TEST_SERIAL)
        result = svc.is_app_foreground("com.example.game")

        assert result is True

    def test_is_foreground_false(self):
        adb = MockAdbManager()
        adb.set_shell_response(
            "dumpsys activity activities",
            "mResumedActivity: ActivityRecord{abc u0 com.other.app/MainActivity t1}",
        )

        svc = JankMonitorService(adb, TEST_SERIAL)
        result = svc.is_app_foreground("com.example.game")

        assert result is False

    def test_is_foreground_no_resumed(self):
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys activity activities", "")

        svc = JankMonitorService(adb, TEST_SERIAL)
        result = svc.is_app_foreground("com.example.game")

        assert result is False


class TestDefaultThreshold:
    """测试默认阈值计算。"""

    def test_get_default_threshold(self):
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys display", "refreshRate: 60Hz")

        svc = JankMonitorService(adb, TEST_SERIAL)
        threshold = svc.get_default_threshold()

        assert threshold == 3

    def test_get_default_threshold_90hz(self):
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys display", "refreshRate: 90Hz")

        svc = JankMonitorService(adb, TEST_SERIAL)
        threshold = svc.get_default_threshold()

        assert threshold == 5


class TestSurfaceLayerDetection:
    """测试 SurfaceFlinger 图层发现。"""

    SF_LIST_OUTPUT = (
        "RequestedLayerState{Task=24#2450 parentId=10 z=4}\n"
        "RequestedLayerState{Background for 74ba9e0 SurfaceView[com.tencent.lolm/com.tencent.lolm.lgame]#2539 parentId=2537}\n"
        "RequestedLayerState{74ba9e0 SurfaceView[com.tencent.lolm/com.tencent.lolm.lgame]#2537 parentId=2536}\n"
        "RequestedLayerState{74ba9e0 SurfaceView[com.tencent.lolm/com.tencent.lolm.lgame](BLAST)#2538 parentId=2537}\n"
        "RequestedLayerState{Display 0 name=\"内置屏幕\"#47}\n"
    )

    SF_LATENCY_OUTPUT = (
        "16666666\n"
        "131811512451956\t131811560559820\t131811531662477\n"
        "131811579070133\t131811627226487\t131811598477581\n"
        "131811645839977\t131811693893153\t131811665196852\n"
        "131811712430758\t131811760559768\t131811731731070\n"
        "131811779176695\t131811827226487\t131811798513675\n"
    )

    def test_find_surface_layer(self):
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT)

        svc = JankMonitorService(adb, TEST_SERIAL)
        layer = svc._find_surface_layer("com.tencent.lolm")

        assert layer is not None
        assert "(BLAST)" in layer
        assert layer == "74ba9e0 SurfaceView[com.tencent.lolm/com.tencent.lolm.lgame](BLAST)#2538"

    def test_find_surface_layer_not_found(self):
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys SurfaceFlinger --list", "RequestedLayerState{Task=1}\n")

        svc = JankMonitorService(adb, TEST_SERIAL)
        layer = svc._find_surface_layer("com.nonexistent.app")

        assert layer is None

    def test_sf_layer_cache(self):
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT)

        svc = JankMonitorService(adb, TEST_SERIAL)
        layer1 = svc._find_surface_layer("com.tencent.lolm")
        layer2 = svc._find_surface_layer("com.tencent.lolm")

        assert layer1 == layer2

    def test_get_sf_latency(self):
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT)
        adb.set_shell_response("dumpsys SurfaceFlinger --latency", self.SF_LATENCY_OUTPUT)

        svc = JankMonitorService(adb, TEST_SERIAL)
        output = svc.get_sf_latency("com.tencent.lolm")

        assert output is not None
        assert "16666666" in output

    def test_detect_frame_source_gfxinfo(self):
        adb = MockAdbManager()
        profiledata = (
            "---PROFILEDATA---\n"
            "Flags,IntendedVsync\n"
            "0,123456\n"
            "---PROFILEDATA---\n"
        )
        adb.set_shell_response("dumpsys gfxinfo", profiledata)

        svc = JankMonitorService(adb, TEST_SERIAL)
        source = svc.detect_frame_source("com.normal.app")

        assert source == "gfxinfo"
        assert svc.using_sf_latency is False

    def test_detect_frame_source_sf_latency(self):
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys gfxinfo", "Profile data in ms:\n")
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT)

        svc = JankMonitorService(adb, TEST_SERIAL)
        source = svc.detect_frame_source("com.tencent.lolm")

        assert source == "sf_latency"
        assert svc.using_sf_latency is True
