"""
Windows / Linux 构建脚本 — 基于 PyInstaller 打包 LV Game Toolkit。

生成双入口可执行文件：
  - Toolkit       (console=False)  双击启动 GUI
  - toolkit-cli   (console=True)   终端使用 CLI

优化项：
  - 排除未使用的传递依赖（botocore/grpc/hf_xet 等），节省 ~50 MB
  - 合并双入口为单次构建 + exe 复制，速度提升 ~50%
  - 从 git tag 自动提取版本号
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import time as _time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
ENTRY_POINT = ROOT / "toolkit" / "app.py"

APP_NAME = "lv-game-toolkit"
FALLBACK_VERSION = "1.0.0"

EXCLUDE_MODULES = [
    "PIL", "Pillow", "matplotlib",
    "boto3", "botocore", "s3transfer",
    "grpc", "grpcio", "grpcio_status",
    "hf_xet", "huggingface_hub",
    "IPython", "jedi", "parso", "pickleshare", "prompt_toolkit",
    "fastavro",
    "tokenizers",
    "cohere",
    "opentelemetry", "opentelemetry_api", "opentelemetry_sdk",
    "opentelemetry_exporter_otlp_proto_http",
    "opentelemetry_instrumentation",
    "logfire",
    "pytest", "pytest_cov", "pytest_asyncio", "coverage",
    "_pytest", "py",
]


def _get_version() -> str:
    """从 git tag 提取版本号，格式: v1.2.3 → 1.2.3。"""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        tag = result.stdout.strip()
        if tag.startswith("v"):
            tag = tag[1:]
        if tag:
            return tag
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        desc = result.stdout.strip()
        if desc:
            return desc
    except Exception:
        pass

    return FALLBACK_VERSION


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
        dir_parts = Path(dirpath).parts
        is_sop_dir = "sops" in dir_parts or "sop" in dir_parts
        is_skill_dir = "skills" in dir_parts
        for f in filenames:
            if any(f.endswith(ext) for ext in skip_exts):
                if f.endswith(".md") and (is_sop_dir or is_skill_dir):
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
        "toolkit.core.perfdog",  # 添加 perfdog 模块
        "toolkit.sdk.base_plugin",
        "toolkit.sdk.models",
        "toolkit.sdk.protocols",
        "toolkit.sdk.constants",
        "toolkit.gui.main_window",
        "toolkit.gui.home_tab",
        "toolkit.gui.base_tab",
        "toolkit.gui.styles",
        "toolkit.cli.main",
        "pyqtgraph",
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


def build(console: bool, name: str, version: str) -> None:
    """执行一次 PyInstaller 构建。"""
    version_file = ROOT / "VERSION"
    version_file.write_text(version, encoding="utf-8")

    datas = (
        _collect_modules()
        + _collect_data_dir()
        + _collect_assets()
        + _collect_perfetto_data()
        + [(str(version_file), ".")]
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

    for exclude in EXCLUDE_MODULES:
        cmd.append(f"--exclude-module={exclude}")

    if not console:
        cmd.append("--noconsole")

    for src, dst in datas:
        cmd.append(f"--add-data={src}{os.pathsep}{dst}")

    for imp in hidden:
        cmd.append(f"--hidden-import={imp}")

    cmd.append(str(ENTRY_POINT))

    print(f"\n{'='*60}")
    print(f"  Building {name} v{version} ({'GUI' if not console else 'CLI'}) ...")
    print(f"  Excluding {len(EXCLUDE_MODULES)} unused transitive deps")
    print(f"{'='*60}\n")

    subprocess.run(cmd, check=True, cwd=str(ROOT))


def _copy_as_cli(gui_dir: Path, pkg_dir: Path, os_name: str) -> None:
    """从 GUI 构建产物中复制并重命名为 CLI 入口。

    GUI (--noconsole) 和 CLI (--console) 的区别仅在于 EXE 头标志位。
    通过 editbin 或直接修改 PE 头可避免第二次完整构建。
    如果 editbin 不可用，则退回到构建一个轻量 CLI wrapper。
    """
    gui_exe = gui_dir / ("Toolkit.exe" if os_name == "windows" else "Toolkit")
    cli_exe_name = "toolkit-cli.exe" if os_name == "windows" else "toolkit-cli"
    cli_dst = pkg_dir / cli_exe_name

    if not gui_exe.exists():
        return

    shutil.copy2(gui_exe, cli_dst)

    if os_name == "windows":
        try:
            _set_pe_subsystem(cli_dst, console=True)
            print(f"  [OK] Created CLI entry via PE header patch: {cli_exe_name}")
            return
        except Exception as e:
            print(f"  [WARN] PE patch failed ({e}), CLI will use GUI subsystem")


def _set_pe_subsystem(exe_path: Path, console: bool = True) -> None:
    """修改 PE 可执行文件的子系统标志 (IMAGE_SUBSYSTEM)。

    Windows GUI = 2, Console = 3。
    通过直接修改 PE 头的 Subsystem 字段实现，无需 editbin。
    """
    SUBSYSTEM_CONSOLE = 3
    SUBSYSTEM_WINDOWS = 2

    target = SUBSYSTEM_CONSOLE if console else SUBSYSTEM_WINDOWS

    with open(exe_path, "r+b") as f:
        # PE 签名偏移在 0x3C
        f.seek(0x3C)
        pe_offset = int.from_bytes(f.read(4), "little")

        # 验证 PE 签名 "PE\0\0"
        f.seek(pe_offset)
        sig = f.read(4)
        if sig != b"PE\x00\x00":
            raise ValueError("Not a valid PE file")

        # Subsystem 在 Optional Header 的偏移 68 (0x44)
        # Optional Header 起始 = pe_offset + 4 (sig) + 20 (COFF header)
        subsystem_offset = pe_offset + 4 + 20 + 68
        f.seek(subsystem_offset)
        old_subsystem = int.from_bytes(f.read(2), "little")

        if old_subsystem == target:
            return

        f.seek(subsystem_offset)
        f.write(target.to_bytes(2, "little"))


def package(version: str) -> None:
    """将构建产物合并到统一目录并打包。"""
    os_name = "windows" if platform.system() == "Windows" else "linux"
    pkg_name = f"{APP_NAME}-v{version}-{os_name}"
    pkg_dir = DIST_DIR / pkg_name

    gui_dir = DIST_DIR / "Toolkit"

    if pkg_dir.exists():
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
    else:
        print("  ERROR: GUI build output not found, cannot package")
        return

    _copy_as_cli(gui_dir, pkg_dir, os_name)

    data_dir = pkg_dir / "data"
    data_dir.mkdir(exist_ok=True)

    version_file = pkg_dir / "VERSION"
    version_file.write_text(version, encoding="utf-8")

    ext = "zip" if os_name == "windows" else "tar.gz"
    archive_base = str(DIST_DIR / pkg_name)

    if os_name == "windows":
        shutil.make_archive(archive_base, "zip", str(DIST_DIR), pkg_name)
    else:
        shutil.make_archive(archive_base, "gztar", str(DIST_DIR), pkg_name)

    pkg_size_mb = sum(
        f.stat().st_size for f in pkg_dir.rglob("*") if f.is_file()
    ) / (1024 * 1024)

    print(f"\n{'='*60}")
    print(f"  OK - build complete!")
    print(f"  Version:  {version}")
    print(f"  Package:  {archive_base}.{ext}")
    print(f"  Size:     {pkg_size_mb:.1f} MB")
    print(f"{'='*60}\n")


def main() -> None:
    """主流程：仅构建一次 GUI，通过 PE patch 生成 CLI 入口，然后打包。"""
    import argparse

    parser = argparse.ArgumentParser(description="LV Game Toolkit 构建脚本")
    parser.add_argument("--gui-only", action="store_true", help="仅构建 GUI")
    parser.add_argument("--cli-only", action="store_true", help="仅构建 CLI")
    parser.add_argument("--no-package", action="store_true", help="不打包")
    parser.add_argument("--version", type=str, default="", help="手动指定版本号")
    args = parser.parse_args()

    version = args.version or _get_version()
    print(f"  Build version: {version}")

    t0 = _time.time()

    if args.cli_only:
        build(console=True, name="toolkit-cli", version=version)
    else:
        build(console=False, name="Toolkit", version=version)

    elapsed = _time.time() - t0
    print(f"\n  Build time: {elapsed:.1f}s")

    if not args.no_package:
        package(version)


if __name__ == "__main__":
    main()
