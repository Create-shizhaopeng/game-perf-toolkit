"""插件管理器 — 基于 pluggy 的模块发现、加载和生命周期管理"""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Any

import pluggy

from .hookspecs import PROJECT_NAME, ToolkitHookSpec

logger = logging.getLogger(__name__)

RESERVED_CLI_NAMESPACES = frozenset({
    "config", "plugin", "workflow", "version", "help", "gui",
})


class PluginLoadError(Exception):
    """模块加载失败异常。"""


class PluginConflictError(Exception):
    """模块冲突异常（如 CLI 命名空间重复）。"""


class PluginManager:
    """模块发现、加载和生命周期管理。

    扫描 modules/ 目录，读取每个模块的 manifest.json，
    按依赖顺序加载模块并注册到 pluggy。
    """

    def __init__(self, modules_dir: Path) -> None:
        self.pm = pluggy.PluginManager(PROJECT_NAME)
        self.pm.add_hookspecs(ToolkitHookSpec)
        self.modules_dir = modules_dir
        self.loaded_modules: dict[str, dict[str, Any]] = {}
        self._cli_namespaces: dict[str, str] = {}

    def discover_modules(self) -> list[dict[str, Any]]:
        """扫描 modules/ 目录，返回按依赖排序的模块清单列表。"""
        manifests: list[dict[str, Any]] = []
        if not self.modules_dir.exists():
            logger.warning("模块目录不存在: %s", self.modules_dir)
            return manifests

        for module_dir in sorted(self.modules_dir.iterdir()):
            manifest_path = module_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text("utf-8"))
                manifest["_path"] = module_dir
                manifests.append(manifest)
                logger.debug("发现模块: %s (%s)", manifest["name"], module_dir)
            except (json.JSONDecodeError, KeyError) as e:
                logger.error("模块清单解析失败: %s — %s", manifest_path, e)

        return self._sort_by_dependencies(manifests)

    def _sort_by_dependencies(
        self, manifests: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """按模块间依赖关系做拓扑排序。"""
        by_name = {m["name"]: m for m in manifests}
        visited: set[str] = set()
        result: list[dict[str, Any]] = []

        def visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            manifest = by_name.get(name)
            if manifest is None:
                return
            for dep in manifest.get("dependencies", {}).get("toolkit_modules", []):
                visit(dep)
            result.append(manifest)

        for m in manifests:
            visit(m["name"])
        return result

    def _validate_cli_namespace(self, manifest: dict[str, Any]) -> None:
        """检查 CLI 命名空间是否冲突。"""
        ns = manifest.get("cli_namespace")
        if ns is None:
            return
        if ns in RESERVED_CLI_NAMESPACES:
            raise PluginConflictError(
                f"CLI 命名空间 '{ns}' 为框架预留，"
                f"模块 '{manifest['name']}' 不可使用。"
            )
        if ns in self._cli_namespaces:
            raise PluginConflictError(
                f"CLI 命名空间冲突: '{ns}' 同时被 "
                f"'{self._cli_namespaces[ns]}' 和 '{manifest['name']}' 使用。"
            )
        self._cli_namespaces[ns] = manifest["name"]

    def _ensure_parent_packages(self, name: str, module_path: Path, entry: str) -> None:
        """确保父包已注册到 sys.modules，使模块内相对导入正常工作。"""
        import types

        parts = entry.split(".")
        package_parts = [f"modules", f"modules.{name}"]
        package_dirs = [self.modules_dir, module_path]

        for i, part in enumerate(parts[:-1]):
            full_name = f"modules.{name}.{'.'.join(parts[:i + 1])}"
            package_parts.append(full_name)
            package_dirs.append(module_path / "/".join(parts[:i + 1]))

        for pkg_name, pkg_dir in zip(package_parts, package_dirs):
            if pkg_name not in sys.modules:
                pkg = types.ModuleType(pkg_name)
                pkg.__path__ = [str(pkg_dir)]
                pkg.__package__ = pkg_name
                sys.modules[pkg_name] = pkg

    def load_module(self, manifest: dict[str, Any]) -> None:
        """加载单个模块：动态导入 plugin.py 并注册到 pluggy。"""
        name = manifest["name"]
        module_path: Path = manifest["_path"]
        entry = manifest["entry"]

        self._validate_cli_namespace(manifest)

        plugin_file = module_path / entry.replace(".", "/")
        plugin_file = plugin_file.with_suffix(".py")
        if not plugin_file.exists():
            raise PluginLoadError(f"插件入口不存在: {plugin_file}")

        self._ensure_parent_packages(name, module_path, entry)

        full_module_name = f"modules.{name}.{entry}"
        spec = importlib.util.spec_from_file_location(
            full_module_name,
            plugin_file,
            submodule_search_locations=[],
        )
        if spec is None or spec.loader is None:
            raise PluginLoadError(f"无法创建模块规范: {plugin_file}")

        mod = importlib.util.module_from_spec(spec)
        mod.__package__ = f"modules.{name}.{'.'.join(entry.split('.')[:-1])}"
        sys.modules[full_module_name] = mod
        spec.loader.exec_module(mod)

        plugin_cls = self._find_plugin_class(mod)
        if plugin_cls is None:
            raise PluginLoadError(f"在 {plugin_file} 中未找到 BasePlugin 子类")

        plugin_instance = plugin_cls()
        self.pm.register(plugin_instance, name=name)
        self.loaded_modules[name] = manifest
        logger.info("模块已加载: %s v%s", manifest.get("display_name", name), manifest.get("version"))

    @staticmethod
    def _find_plugin_class(mod: Any) -> type | None:
        """在模块中查找 BasePlugin 的子类。"""
        from toolkit.sdk.base_plugin import BasePlugin

        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BasePlugin)
                and attr is not BasePlugin
            ):
                return attr
        return None

    def load_all(self) -> None:
        """发现并加载所有模块。"""
        manifests = self.discover_modules()
        for manifest in manifests:
            try:
                self.load_module(manifest)
            except (PluginLoadError, PluginConflictError):
                logger.exception("模块加载失败: %s", manifest.get("name", "unknown"))

    def get_module_info(self, name: str) -> dict[str, Any] | None:
        return self.loaded_modules.get(name)

    def list_loaded(self) -> list[str]:
        return list(self.loaded_modules.keys())
