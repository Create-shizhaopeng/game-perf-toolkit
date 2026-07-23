"""
Windows / Linux 定制构建脚本 — 仅打包指定模块生成 EXE。

用法:
  python scripts/build_subset.py --modules device_disguise,perfetto_capture
  python scripts/build_subset.py --modules device_disguise,perfetto_capture --no-package
  python scripts/build_subset.py --modules device_disguise,perfetto_capture --name "DD_Perfetto"

生成产物:
  dist/Toolkit_<modules>/           # 可运行目录
  dist/lv-game-toolkit-<modules>-v{version}-windows.zip  # 分发包
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


def _validate_modules(module_names: list[str]) -> list[str]:
    """验证模块名称是否有效，返回有效模块列表。"""
    valid = []
    for name in module_names:
        mod_dir = ROOT / "modules" / name
        manifest = mod_dir / "manifest.json"
        if mod_dir.is_dir() and manifest.exists():
            valid.append(name)
        else:
            print(f"  [WARN] Module '{name}' not found or missing manifest.json, skipping")
    return valid


def _collect_modules(module_names: list[str]) -> list[tuple[str, str]]:
    """仅收集指定模块的运行时文件（排除开发文档、测试、IDE 配置等）。"""
    datas: list[tuple[str, str]] = []
    modules_dir = ROOT / "modules"

    skip_dirs = {
        "__pycache__", "data", ".pytest_cache", "out",
        ".cursor", ".specify", "specs", "tests", "fixtures",
        "image",
    }
    skip_exts = {".pyc", ".pyo", ".md"}

    for mod_name in module_names:
        mod_dir = modules_dir / mod_name
        if not mod_dir.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(mod_dir):
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


def _hidden_imports(module_names: list[str]) -> list[str]:
    """仅生成指定模块的 hidden imports。"""
    imports = [
        # 核心框架
        "toolkit.core.config_manager",
        "toolkit.core.db_manager",
        "toolkit.core.event_bus",
        "toolkit.core.plugin_manager",
        "toolkit.core.service_registry",
        "toolkit.core.adb_manager",
        "toolkit.core.process_bridge",
        "toolkit.core.logger",
        "toolkit.core.hookspecs",
        "toolkit.core.perfdog",
        "toolkit.core.mcp_server",
        "toolkit.core.skill_registry",
        "toolkit.sdk.base_plugin",
        "pyqtgraph",
    ]

    # 仅包含指定模块的导入
    modules_dir = ROOT / "modules"
    for mod_name in module_names:
        mod_dir = modules_dir / mod_name
        if not mod_dir.is_dir():
            continue
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

    # perfetto 相关（perfetto_capture 模块需要）
    if "perfetto_capture" in module_names:
        imports.extend([
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
        ])

    # 可选依赖
    for optional in ["zhipuai", "anthropic", "yaml", "jwt"]:
        try:
            __import__(optional)
            imports.append(optional)
        except ImportError:
            print(f"  [INFO] Optional dependency '{optional}' not installed, skipping")

    return imports


def _write_spec(name: str, datas: list[tuple[str, str]], hidden: list[str],
                excludes: list[str], icon: str, console: bool) -> Path:
    """生成 PyInstaller .spec 文件。"""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    spec_path = BUILD_DIR / f"{name}.spec"

    datas_repr = "[\n"
    for src, dst in datas:
        datas_repr += f"        ({src!r}, {dst!r}),\n"
    datas_repr += "    ]"

    hidden_repr = "[\n"
    for imp in hidden:
        hidden_repr += f"        {imp!r},\n"
    hidden_repr += "    ]"

    excludes_repr = "[\n"
    for exc in excludes:
        excludes_repr += f"        {exc!r},\n"
    excludes_repr += "    ]"

    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    [{str(ENTRY_POINT)!r}],
    pathex=[],
    binaries=[],
    datas={datas_repr},
    hiddenimports={hidden_repr},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes={excludes_repr},
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe_kwargs = dict(
    name={name!r},
    icon={icon!r} if {icon!r} else None,
)
if {console!r}:
    exe_kwargs["console"] = True
else:
    exe_kwargs["console"] = False

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    **exe_kwargs,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name={name!r},
)
'''
    spec_path.write_text(spec_content, encoding="utf-8")
    return spec_path


def build(console: bool, name: str, version: str, module_names: list[str]) -> str:
    """执行 PyInstaller 构建，仅包含指定模块。"""
    version_file = ROOT / "VERSION"
    version_file.write_text(version, encoding="utf-8")

    datas = (
        _collect_modules(module_names)
        + _collect_assets()
        + _collect_perfetto_data()
        + [(str(version_file), ".")]
    )
    hidden = _hidden_imports(module_names)
    icon_path = str(ROOT / "assets" / "app.ico")

    ts = _time.strftime("%H%M%S")
    build_name = f"{name}_{ts}"

    spec = _write_spec(build_name, datas, hidden, EXCLUDE_MODULES, icon_path, console)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        str(spec),
    ]

    modules_str = ", ".join(module_names)
    print(f"\n{'='*60}")
    print(f"  Building {name} v{version} ({'GUI' if not console else 'CLI'}) -> {build_name}")
    print(f"  Modules: {modules_str}")
    print(f"  Excluding {len(EXCLUDE_MODULES)} unused transitive deps")
    print(f"{'='*60}\n")

    try:
        subprocess.run(cmd, check=True, cwd=str(ROOT))
    finally:
        if spec.exists():
            spec.unlink()

    # 创建 data/config/ + data/db/ 目录，仅复制指定模块的配置文件
    out_dir = DIST_DIR / build_name
    config_dir = out_dir / "data" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    db_dir = out_dir / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)

    modules_dir = ROOT / "modules"
    for mod_name in module_names:
        mod_dir = modules_dir / mod_name
        if not mod_dir.is_dir():
            continue
        src_config_dir = mod_dir / "config"
        if not src_config_dir.is_dir():
            continue
        for f in src_config_dir.iterdir():
            if f.is_file() and not f.name.endswith((".pyc", ".pyo")):
                dest = config_dir / f"{mod_name}_{f.name}"
                if not dest.exists():
                    shutil.copy2(f, dest)
    print(f"  [OK] Created data/config/ + data/db/ directories with module configs in {out_dir}")
    return build_name


def package(version: str, module_names: list[str], gui_dir_name: str) -> None:
    """将构建产物合并到统一目录并打包。"""
    os_name = "windows" if platform.system() == "Windows" else "linux"
    modules_slug = "-".join(module_names[:2])
    if len(module_names) > 2:
        modules_slug += f"-plus{len(module_names) - 2}"
    pkg_name = f"{APP_NAME}-{modules_slug}-v{version}-{os_name}"
    pkg_dir = DIST_DIR / pkg_name

    gui_dir = DIST_DIR / gui_dir_name

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
    print(f"  Modules:  {', '.join(module_names)}")
    print(f"  Version:  {version}")
    print(f"  Package:  {archive_base}.{ext}")
    print(f"  Size:     {pkg_size_mb:.1f} MB")
    print(f"{'='*60}\n")


def main() -> None:
    """主流程。"""
    import argparse

    parser = argparse.ArgumentParser(
        description="LV Game Toolkit 定制构建脚本 — 仅打包指定模块",
    )
    parser.add_argument(
        "--modules", type=str, required=True,
        help="要打包的模块名称，逗号分隔 (e.g. device_disguise,perfetto_capture)",
    )
    parser.add_argument(
        "--name", type=str, default="Toolkit_Subset",
        help="输出 EXE 名称 (默认: Toolkit_Subset)",
    )
    parser.add_argument("--gui-only", action="store_true", help="仅构建 GUI")
    parser.add_argument("--no-package", action="store_true", help="不打包为 zip")
    parser.add_argument("--version", type=str, default="", help="手动指定版本号")
    args = parser.parse_args()

    # 解析并验证模块名称
    raw_names = [n.strip() for n in args.modules.split(",") if n.strip()]
    module_names = _validate_modules(raw_names)

    if not module_names:
        print("ERROR: No valid modules specified. Aborting.")
        sys.exit(1)

    version = args.version or _get_version()
    modules_str = ", ".join(module_names)
    print(f"  Build version: {version}")
    print(f"  Modules: {modules_str}")

    t0 = _time.time()

    gui_dir_name = build(
        console=False,
        name=args.name,
        version=version,
        module_names=module_names,
    )

    elapsed = _time.time() - t0
    print(f"\n  Build time: {elapsed:.1f}s")

    if not args.no_package:
        package(version, module_names, gui_dir_name=gui_dir_name)


if __name__ == "__main__":
    main()
