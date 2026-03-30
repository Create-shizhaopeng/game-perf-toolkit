"""
Windows / Linux 构建脚本 — 基于 PyInstaller 打包 LV Game Toolkit。

生成双入口可执行文件：
  - Toolkit       (console=False)  双击启动 GUI
  - toolkit-cli   (console=True)   终端使用 CLI
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
ENTRY_POINT = ROOT / "toolkit" / "app.py"

APP_NAME = "lv-game-toolkit"
VERSION = "1.0.0"


def _collect_modules() -> list[tuple[str, str]]:
    """收集 modules/ 下运行时所需文件（排除开发文档、测试、IDE 配置等）。"""
    datas: list[tuple[str, str]] = []
    modules_dir = ROOT / "modules"

    skip_dirs = {
        "__pycache__", "data", ".pytest_cache", "out",
        ".cursor", ".specify", "specs", "tests", "fixtures",
        "image",
    }
    skip_exts = {".pyc", ".pyo", ".md"}

    for dirpath, dirnames, filenames in os.walk(modules_dir):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]

        rel = Path(dirpath).relative_to(ROOT)
        is_sop_dir = "sops" in Path(dirpath).parts
        for f in filenames:
            if any(f.endswith(ext) for ext in skip_exts):
                if f.endswith(".md") and is_sop_dir:
                    pass
                else:
                    continue
            src = str(Path(dirpath) / f)
            dst = str(rel)
            datas.append((src, dst))

    return datas


def _collect_data_dir() -> list[tuple[str, str]]:
    """收集 data/ 目录结构（仅 .gitkeep 和必要模板）。"""
    datas: list[tuple[str, str]] = []
    data_dir = ROOT / "data"
    if data_dir.exists():
        for dirpath, _, filenames in os.walk(data_dir):
            for f in filenames:
                if f == ".gitkeep":
                    src = str(Path(dirpath) / f)
                    dst = str(Path(dirpath).relative_to(ROOT))
                    datas.append((src, dst))
    return datas


def _collect_assets() -> list[tuple[str, str]]:
    """收集 assets/ 目录（图标、Logo 等资源文件）。"""
    datas: list[tuple[str, str]] = []
    assets_dir = ROOT / "assets"
    if assets_dir.exists():
        for dirpath, _, filenames in os.walk(assets_dir):
            rel = Path(dirpath).relative_to(ROOT)
            for f in filenames:
                if f.endswith((".pyc", ".pyo")):
                    continue
                datas.append((str(Path(dirpath) / f), str(rel)))
    return datas


def _collect_perfetto_data() -> list[tuple[str, str]]:
    """收集 perfetto 包的非 Python 数据文件（descriptor 等）。"""
    import importlib.util
    datas: list[tuple[str, str]] = []
    spec = importlib.util.find_spec("perfetto")
    if spec and spec.submodule_search_locations:
        pkg_dir = Path(spec.submodule_search_locations[0])
        data_exts = {".descriptor", ".proto"}
        for dirpath, _, filenames in os.walk(pkg_dir):
            rel = Path(dirpath).relative_to(pkg_dir.parent)
            for f in filenames:
                if any(f.endswith(ext) for ext in data_exts):
                    datas.append((str(Path(dirpath) / f), str(rel)))
    return datas


def _hidden_imports() -> list[str]:
    """动态模块的 hidden imports。"""
    imports = [
        "toolkit.core.config_manager",
        "toolkit.core.db_manager",
        "toolkit.core.event_bus",
        "toolkit.core.plugin_manager",
        "toolkit.core.service_registry",
        "toolkit.core.adb_manager",
        "toolkit.core.process_bridge",
        "toolkit.core.logger",
        "toolkit.core.hookspecs",
        "toolkit.sdk.base_plugin",
        "toolkit.sdk.models",
        "toolkit.sdk.protocols",
        "toolkit.sdk.constants",
        "toolkit.gui.main_window",
        "toolkit.gui.home_tab",
        "toolkit.gui.base_tab",
        "toolkit.gui.styles",
        "toolkit.cli.main",
        "perfetto",
        "perfetto.trace_processor",
        "perfetto.trace_processor.api",
        "perfetto.trace_processor.http",
        "perfetto.trace_processor.shell",
        "perfetto.trace_processor.platform",
        "perfetto.trace_processor.protos",
        "perfetto.common",
        "perfetto.common.exceptions",
        "perfetto.common.query_result_iterator",
        "perfetto.trace_uri_resolver",
        "perfetto.trace_uri_resolver.path",
        "perfetto.trace_uri_resolver.registry",
        "perfetto.trace_uri_resolver.resolver",
    ]

    modules_dir = ROOT / "modules"
    for mod_dir in sorted(modules_dir.iterdir()):
        if not mod_dir.is_dir():
            continue
        manifest = mod_dir / "manifest.json"
        if not manifest.exists():
            continue
        mod_name = mod_dir.name
        src_dir = mod_dir / "src"
        if not src_dir.exists():
            continue
        for py_file in src_dir.rglob("*.py"):
            rel = py_file.relative_to(mod_dir)
            parts = list(rel.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            if parts:
                imports.append(f"modules.{mod_name}.{'.'.join(parts)}")

    for optional in ["zhipuai", "anthropic", "yaml", "jwt"]:
        try:
            __import__(optional)
            imports.append(optional)
        except ImportError:
            print(f"  [INFO] Optional dependency '{optional}' not installed, skipping")

    return imports


def build(console: bool, name: str) -> None:
    """执行一次 PyInstaller 构建。"""
    datas = (
        _collect_modules()
        + _collect_data_dir()
        + _collect_assets()
        + _collect_perfetto_data()
    )
    hidden = _hidden_imports()

    icon_path = ROOT / "assets" / "app.ico"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        f"--name={name}",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        "--clean",
    ]

    if icon_path.exists():
        cmd.append(f"--icon={icon_path}")

    for exclude in ["PIL", "Pillow", "matplotlib"]:
        cmd.append(f"--exclude-module={exclude}")

    if not console:
        cmd.append("--noconsole")

    for src, dst in datas:
        cmd.append(f"--add-data={src}{os.pathsep}{dst}")

    for imp in hidden:
        cmd.append(f"--hidden-import={imp}")

    cmd.append(str(ENTRY_POINT))

    print(f"\n{'='*60}")
    print(f"  Building {name} ({'GUI' if not console else 'CLI'}) ...")
    print(f"{'='*60}\n")

    subprocess.run(cmd, check=True, cwd=str(ROOT))


def package() -> None:
    """将两个构建产物合并到统一目录并打包。"""
    os_name = "windows" if platform.system() == "Windows" else "linux"
    pkg_name = f"{APP_NAME}-v{VERSION}-{os_name}"
    pkg_dir = DIST_DIR / pkg_name

    gui_dir = DIST_DIR / "Toolkit"
    cli_dir = DIST_DIR / "toolkit-cli"

    if pkg_dir.exists():
        import time as _time
        removed = False
        for attempt in range(3):
            try:
                shutil.rmtree(pkg_dir)
                removed = True
                break
            except PermissionError:
                if attempt < 2:
                    print(f"  Retry {attempt + 1}/3: waiting for locked files...")
                    _time.sleep(3)
        if not removed:
            suffix = _time.strftime("%H%M%S")
            alt_name = f"{pkg_name}-{suffix}"
            print(f"  WARNING: Cannot remove old package dir, using: {alt_name}")
            pkg_dir = DIST_DIR / alt_name
            pkg_name = alt_name

    if gui_dir.exists():
        shutil.copytree(gui_dir, pkg_dir)
    elif cli_dir.exists():
        shutil.copytree(cli_dir, pkg_dir)

    if cli_dir.exists() and gui_dir.exists():
        cli_exe = "toolkit-cli.exe" if os_name == "windows" else "toolkit-cli"
        cli_src = cli_dir / cli_exe
        if cli_src.exists():
            shutil.copy2(cli_src, pkg_dir / cli_exe)

    data_dir = pkg_dir / "data"
    data_dir.mkdir(exist_ok=True)

    ext = "zip" if os_name == "windows" else "tar.gz"
    archive_base = str(DIST_DIR / pkg_name)

    if os_name == "windows":
        shutil.make_archive(archive_base, "zip", str(DIST_DIR), pkg_name)
    else:
        shutil.make_archive(archive_base, "gztar", str(DIST_DIR), pkg_name)

    print(f"\n{'='*60}")
    print(f"  OK - build complete: {archive_base}.{ext}")
    print(f"{'='*60}\n")


def main() -> None:
    """主流程：构建 GUI + CLI 双入口，然后打包。"""
    import argparse

    parser = argparse.ArgumentParser(description="LV Game Toolkit 构建脚本")
    parser.add_argument("--gui-only", action="store_true", help="仅构建 GUI")
    parser.add_argument("--cli-only", action="store_true", help="仅构建 CLI")
    parser.add_argument("--no-package", action="store_true", help="不打包")
    args = parser.parse_args()

    if not args.cli_only:
        build(console=False, name="Toolkit")

    if not args.gui_only:
        build(console=True, name="toolkit-cli")

    if not args.no_package:
        package()


if __name__ == "__main__":
    main()
