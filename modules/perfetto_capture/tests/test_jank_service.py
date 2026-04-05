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

    SF_LIST_OUTPUT_OLD = (
        "Task=24#2450\n"
        "Background for 74ba9e0 SurfaceView[com.tencent.lolm/com.tencent.lolm.lgame]#2539\n"
        "74ba9e0 SurfaceView[com.tencent.lolm/com.tencent.lolm.lgame]#2537\n"
        "74ba9e0 SurfaceView[com.tencent.lolm/com.tencent.lolm.lgame](BLAST)#2538\n"
        "Display 0 name=\"内置屏幕\"#47\n"
    )

    SF_LIST_OUTPUT_RLS = (
        "RequestedLayerState{Task=24#2450 parentId=10 z=4}\n"
        "RequestedLayerState{Background for 74ba9e0 SurfaceView[com.tencent.lolm/com.tencent.lolm.lgame]#2539 parentId=2537}\n"
        "RequestedLayerState{74ba9e0 SurfaceView[com.tencent.lolm/com.tencent.lolm.lgame]#2537 parentId=2536}\n"
        "RequestedLayerState{74ba9e0 SurfaceView[com.tencent.lolm/com.tencent.lolm.lgame](BLAST)#2538 parentId=2537}\n"
        "RequestedLayerState{Display 0 name=\"内置屏幕\"#47}\n"
    )

    SF_LIST_OUTPUT_ANDROID16 = (
        "RequestedLayerState{Task=24 04-05 15:26:34.887#2450 parentId=10 z=4}\n"
        "RequestedLayerState{Background for 76aea0c SurfaceView[com.tencent.af/com.tencent.af.AFActivity] 04-05 15:36:50.170#4820 parentId=4818 relativeParentId=4814 z=-2147483648}\n"
        "RequestedLayerState{76aea0c SurfaceView[com.tencent.af/com.tencent.af.AFActivity] 04-05 15:36:50.170#4818 parentId=4817 relativeParentId=4814 z=-2}\n"
        "RequestedLayerState{76aea0c SurfaceView[com.tencent.af/com.tencent.af.AFActivity](BLAST) 04-05 15:36:50.170#4819 parentId=4818}\n"
    )

    SF_LATENCY_OUTPUT = (
        "16666666\n"
        "131811512451956\t131811560559820\t131811531662477\n"
        "131811579070133\t131811627226487\t131811598477581\n"
        "131811645839977\t131811693893153\t131811665196852\n"
        "131811712430758\t131811760559768\t131811731731070\n"
        "131811779176695\t131811827226487\t131811798513675\n"
    )

    SF_LATENCY_ONLY_REFRESH = "8333333\n"

    def test_find_surface_layer_old_format(self):
        """旧格式（无 RequestedLayerState 包裹）正确解析。"""
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT_OLD)

        svc = JankMonitorService(adb, TEST_SERIAL)
        layer = svc._find_surface_layer("com.tencent.lolm")

        assert layer is not None
        assert "(BLAST)" in layer
        assert layer == "74ba9e0 SurfaceView[com.tencent.lolm/com.tencent.lolm.lgame](BLAST)#2538"

    def test_find_surface_layer_rls_format(self):
        """RequestedLayerState 包裹格式（无时间戳）正确解析。"""
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT_RLS)

        svc = JankMonitorService(adb, TEST_SERIAL)
        layer = svc._find_surface_layer("com.tencent.lolm")

        assert layer is not None
        assert "(BLAST)" in layer
        assert layer == "74ba9e0 SurfaceView[com.tencent.lolm/com.tencent.lolm.lgame](BLAST)#2538"

    def test_find_surface_layer_android16(self):
        """Android 16 新格式（时间戳插入 BLAST 和 # 之间）正确解析完整图层名。"""
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT_ANDROID16)

        svc = JankMonitorService(adb, TEST_SERIAL)
        layer = svc._find_surface_layer("com.tencent.af")

        assert layer is not None
        assert "(BLAST)" in layer
        assert "04-05" in layer
        assert layer == "76aea0c SurfaceView[com.tencent.af/com.tencent.af.AFActivity](BLAST) 04-05 15:36:50.170#4819"

    def test_find_surface_layer_android16_fallback(self):
        """Android 16 非 BLAST 图层作为 fallback。"""
        sf_list = (
            "RequestedLayerState{76aea0c SurfaceView[com.tencent.af/com.tencent.af.AFActivity] "
            "04-05 15:36:50.170#4818 parentId=4817 relativeParentId=4814 z=-2}\n"
        )
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys SurfaceFlinger --list", sf_list)

        svc = JankMonitorService(adb, TEST_SERIAL)
        layer = svc._find_surface_layer("com.tencent.af")

        assert layer is not None
        assert "(BLAST)" not in layer
        assert "04-05" in layer
        assert "#4818" in layer

    def test_find_surface_layer_not_found(self):
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys SurfaceFlinger --list", "RequestedLayerState{Task=1}\n")

        svc = JankMonitorService(adb, TEST_SERIAL)
        layer = svc._find_surface_layer("com.nonexistent.app")

        assert layer is None

    def test_sf_layer_cache(self):
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT_RLS)

        svc = JankMonitorService(adb, TEST_SERIAL)
        layer1 = svc._find_surface_layer("com.tencent.lolm")
        layer2 = svc._find_surface_layer("com.tencent.lolm")

        assert layer1 == layer2

    def test_sf_layer_cache_invalidation(self):
        """invalidate_sf_layer_cache 清除缓存后重新查询。"""
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT_RLS)

        svc = JankMonitorService(adb, TEST_SERIAL)
        svc._find_surface_layer("com.tencent.lolm")
        svc.invalidate_sf_layer_cache()

        assert svc._cached_sf_layer is None
        assert svc._sf_layer_pkg is None

    def test_sf_empty_poll_triggers_invalidation(self):
        """连续 SF 空帧超过阈值触发缓存失效。"""
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT_RLS)

        svc = JankMonitorService(adb, TEST_SERIAL)
        svc._find_surface_layer("com.tencent.lolm")
        assert svc._cached_sf_layer is not None

        for i in range(9):
            assert svc.notify_sf_empty_poll() is False

        assert svc.notify_sf_empty_poll() is True
        assert svc._cached_sf_layer is None

    def test_sf_empty_count_reset(self):
        """有效数据重置空帧计数。"""
        adb = MockAdbManager()
        svc = JankMonitorService(adb, TEST_SERIAL)

        for _ in range(5):
            svc.notify_sf_empty_poll()
        assert svc._sf_empty_count == 5

        svc.reset_sf_empty_count()
        assert svc._sf_empty_count == 0

    def test_get_sf_latency(self):
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT_RLS)
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
        adb.set_shell_response("getprop", "14")

        svc = JankMonitorService(adb, TEST_SERIAL)
        source = svc.detect_frame_source("com.normal.app")

        assert source == "gfxinfo"
        assert svc.using_sf_latency is False

    def test_detect_frame_source_sf_latency_with_validation(self):
        """SF latency 选择前验证帧数据有效性。"""
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys gfxinfo", "Profile data in ms:\n")
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT_RLS)
        adb.set_shell_response("dumpsys SurfaceFlinger --latency", self.SF_LATENCY_OUTPUT)
        adb.set_shell_response("getprop", "14")

        svc = JankMonitorService(adb, TEST_SERIAL)
        source = svc.detect_frame_source("com.tencent.lolm")

        assert source == "sf_latency"
        assert svc.using_sf_latency is True

    def test_detect_frame_source_sf_only_refresh_rate(self):
        """SF latency 只返回刷新率时不应选择 sf_latency。"""
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys gfxinfo", "Profile data in ms:\n")
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT_RLS)
        adb.set_shell_response("dumpsys SurfaceFlinger --latency", self.SF_LATENCY_ONLY_REFRESH)
        adb.set_shell_response("getprop", "16")

        svc = JankMonitorService(adb, TEST_SERIAL)
        source = svc.detect_frame_source("com.tencent.lolm")

        assert source == "gfxinfo"
        assert svc.using_sf_latency is False

    def test_detect_frame_source_no_source(self):
        """gfxinfo 和 SF 均无有效数据时回退到 gfxinfo。"""
        adb = MockAdbManager()
        adb.set_shell_response("dumpsys gfxinfo", "")
        adb.set_shell_response("dumpsys SurfaceFlinger --list", "no layers\n")
        adb.set_shell_response("getprop", "14")

        svc = JankMonitorService(adb, TEST_SERIAL)
        source = svc.detect_frame_source("com.example.app")

        assert source == "gfxinfo"
        assert svc.using_sf_latency is False

    def test_detect_frame_source_empty_profiledata(self):
        """gfxinfo 有 PROFILEDATA 标记但无帧数据，降级到 SF。"""
        adb = MockAdbManager()
        empty_profile = (
            "---PROFILEDATA---\n"
            "Flags,IntendedVsync\n"
            "---PROFILEDATA---\n"
        )
        adb.set_shell_response("dumpsys gfxinfo", empty_profile)
        adb.set_shell_response("dumpsys SurfaceFlinger --list", self.SF_LIST_OUTPUT_RLS)
        adb.set_shell_response("dumpsys SurfaceFlinger --latency", self.SF_LATENCY_OUTPUT)
        adb.set_shell_response("getprop", "14")

        svc = JankMonitorService(adb, TEST_SERIAL)
        source = svc.detect_frame_source("com.tencent.lolm")

        assert source == "sf_latency"
        assert svc.using_sf_latency is True
