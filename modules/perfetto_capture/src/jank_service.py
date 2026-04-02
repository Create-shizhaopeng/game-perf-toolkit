"""Perfetto Capture 模块 — Jank 监控服务

提供帧率监控、前台应用检测、刷新率查询等服务。
支持 gfxinfo framestats（HWUI 应用）和 SurfaceFlinger --latency（SurfaceView 游戏）
两种帧数据采集方式。
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from .jank_parser import get_default_jank_threshold
from .models import AppInfo

if TYPE_CHECKING:
    from toolkit.core.adb_manager import AdbManager

logger = logging.getLogger(__name__)

_SF_LAYER_PATTERN = re.compile(r"SurfaceView\[([^\]]+)\]")


class JankMonitorService:
    """Jank 监控服务。"""

    def __init__(self, adb: AdbManager, serial: str) -> None:
        self._adb = adb
        self._serial = serial
        self._cached_refresh_rate: int | None = None
        self._cached_sf_layer: str | None = None
        self._sf_layer_pkg: str | None = None
        self._use_sf_latency: bool = False

    def get_running_apps(self) -> list[AppInfo]:
        """获取第三方应用列表。"""
        try:
            output = self._adb.shell(self._serial, "pm list packages -3")
        except Exception:
            return []

        if not output:
            return []

        apps: list[AppInfo] = []
        foreground_pkg = self._get_foreground_package()

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                pkg_name = line[8:]
                apps.append(
                    AppInfo(
                        package_name=pkg_name,
                        is_foreground=(pkg_name == foreground_pkg),
                    )
                )

        apps.sort(key=lambda a: (not a.is_foreground, a.package_name))
        return apps

    def get_display_refresh_rate(self, use_cache: bool = True) -> int:
        """获取屏幕刷新率。默认 60 Hz。"""
        if use_cache and self._cached_refresh_rate is not None:
            return self._cached_refresh_rate

        refresh_rate = 60
        try:
            output = self._adb.shell(
                self._serial,
                "dumpsys display | grep -E 'mActiveMode|refreshRate'",
            )
            if output:
                match = re.search(r"(\d+(?:\.\d+)?)\s*[Hh]z", output)
                if match:
                    refresh_rate = round(float(match.group(1)))
        except Exception:
            pass

        self._cached_refresh_rate = refresh_rate
        return refresh_rate

    def get_default_threshold(self) -> int:
        """获取基于当前刷新率的默认 Jank 阈值。"""
        refresh_rate = self.get_display_refresh_rate()
        return get_default_jank_threshold(refresh_rate)

    def is_app_foreground(self, package: str) -> bool:
        """检测应用是否在前台。"""
        foreground_pkg = self._get_foreground_package()
        return foreground_pkg == package

    def _get_foreground_package(self) -> str | None:
        """获取当前前台应用包名。"""
        try:
            output = self._adb.shell(
                self._serial,
                "dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity'",
            )
        except Exception:
            return None

        if not output:
            return None

        match = re.search(r"(\S+)/\S+ [tu]\d+", output)
        if match:
            component = match.group(1)
            if "/" in component:
                return component.split("/")[0]
            return component

        match = re.search(r"u0 (\S+)/", output)
        if match:
            return match.group(1)

        return None

    def get_framestats(self, package: str) -> str | None:
        """获取应用的帧统计数据（gfxinfo framestats）。"""
        try:
            output = self._adb.shell(
                self._serial,
                f"dumpsys gfxinfo {package} framestats",
            )
            return output if output else None
        except Exception:
            return None

    def get_sf_latency(self, package: str) -> str | None:
        """通过 SurfaceFlinger --latency 获取帧时间戳。

        适用于使用 SurfaceView 渲染的游戏应用。
        """
        layer_name = self._find_surface_layer(package)
        if not layer_name:
            logger.debug("未找到 %s 的 SurfaceView 图层", package)
            return None

        try:
            output = self._adb.shell(
                self._serial,
                f"dumpsys SurfaceFlinger --latency '{layer_name}'",
            )
            return output if output else None
        except Exception:
            logger.warning("获取 SF latency 失败: %s", package, exc_info=True)
            return None

    def _find_surface_layer(self, package: str) -> str | None:
        """查找应用对应的 SurfaceView 图层名。

        优先匹配 (BLAST) 图层（活跃渲染层），回退到非 BLAST 图层。
        图层名需包含完整前缀（如 hash 前缀），否则 SF latency 查询无结果。
        """
        if self._sf_layer_pkg == package and self._cached_sf_layer:
            return self._cached_sf_layer

        try:
            output = self._adb.shell(
                self._serial, "dumpsys SurfaceFlinger --list"
            )
        except Exception:
            return None

        if not output:
            return None

        blast_pattern = re.compile(
            r"(\w+ SurfaceView\[" + re.escape(package) + r"/[^\]]+\]\(BLAST\)#\d+)"
        )
        fallback_pattern = re.compile(
            r"(\w+ SurfaceView\[" + re.escape(package) + r"/[^\]]+\]#\d+)"
        )

        blast_match = None
        fallback_match = None

        for line in output.splitlines():
            if f"SurfaceView[{package}/" not in line:
                continue
            if "Background for" in line:
                continue

            m = blast_pattern.search(line)
            if m and blast_match is None:
                blast_match = m.group(1)
                break

            m = fallback_pattern.search(line)
            if m and fallback_match is None:
                fallback_match = m.group(1)

        result = blast_match or fallback_match
        if result:
            self._cached_sf_layer = result
            self._sf_layer_pkg = package
            logger.info("找到 SF 图层: %s", result)

        return result

    @property
    def using_sf_latency(self) -> bool:
        """是否正在使用 SurfaceFlinger latency 模式。"""
        return self._use_sf_latency

    def detect_frame_source(self, package: str) -> str:
        """检测应用适合的帧数据来源。

        优先尝试 gfxinfo framestats，如果没有 PROFILEDATA 则回退到 SF latency。

        Returns:
            "gfxinfo" 或 "sf_latency"
        """
        output = self.get_framestats(package)
        if output and "---PROFILEDATA---" in output:
            self._use_sf_latency = False
            logger.info("%s 使用 gfxinfo framestats 采集帧数据", package)
            return "gfxinfo"

        layer = self._find_surface_layer(package)
        if layer:
            self._use_sf_latency = True
            logger.info("%s 使用 SurfaceFlinger latency 采集帧数据 (layer=%s)", package, layer)
            return "sf_latency"

        self._use_sf_latency = False
        logger.warning("%s 未找到可用的帧数据来源", package)
        return "gfxinfo"

    def reset_framestats(self, package: str) -> bool:
        """重置应用的帧统计数据。"""
        try:
            self._adb.shell(self._serial, f"dumpsys gfxinfo {package} reset")
            return True
        except Exception:
            return False

    def reset_sf_latency(self, package: str) -> bool:
        """清除 SurfaceFlinger latency 历史数据。"""
        layer_name = self._find_surface_layer(package)
        if not layer_name:
            return False
        try:
            self._adb.shell(
                self._serial,
                f"dumpsys SurfaceFlinger --latency-clear '{layer_name}'",
            )
            return True
        except Exception:
            return False

    def invalidate_sf_layer_cache(self) -> None:
        """使 SurfaceFlinger 图层缓存失效。

        在应用前后台切换时调用，因为图层 ID 可能变化。
        """
        self._cached_sf_layer = None
        self._sf_layer_pkg = None

    def clear_cache(self) -> None:
        """清除所有缓存数据。"""
        self._cached_refresh_rate = None
        self._cached_sf_layer = None
        self._sf_layer_pkg = None
        self._use_sf_latency = False
