"""
Windows / Linux 构建脚本 — 基于 PyInstaller 打包 Game Perf Toolkit。

生成 GUI 可执行文件：
  - Toolkit       (console=False)  双击启动 GUI

优化项：
  - 排除未使用的传递依赖（botocore/grpc/hf_xet 等），节省 ~50 MB
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

APP_NAME = "game-perf-toolkit"
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

    # 不打包的模块（内部模块，发布产物排除）
    exclude_modules = {"game_perf"}

    skip_dirs = {
        "__pycache__", "data", ".pytest_cache", "out",
        ".cursor", ".specify", "specs", "tests", "fixtures",
        "image",
    }
    skip_exts = {".pyc", ".pyo", ".md"}

    for dirpath, dirnames, filenames in os.walk(modules_dir):
        # 跳过整个排除模块的顶级目录
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and d not in exclude_modules]

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
        "toolkit.core.perfdog",
        "toolkit.core.mcp_server",
        "toolkit.core.skill_registry",
        "toolkit.sdk.base_plugin",
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
        if mod_name in {"game_perf"}:
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

    for optional in ["zhipuai", "anthropic", "yaml", "jwt"]:
        try:
            __import__(optional)
            imports.append(optional)
        except ImportError:
            print(f"  [INFO] Optional dependency '{optional}' not installed, skipping")

    return imports


def _write_spec(name: str, datas: list[tuple[str, str]], hidden: list[str],
                excludes: list[str], icon: str, console: bool) -> Path:
    """生成 PyInstaller .spec 文件到 build/ 目录，避免 Windows 命令行长度限制 (32768 字符)。"""
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


def build(console: bool, name: str, version: str) -> str:
    """执行一次 PyInstaller 构建，返回实际输出目录名（含时间戳以避免锁定冲突）。"""
    version_file = ROOT / "VERSION"
    version_file.write_text(version, encoding="utf-8")

    datas = (
        _collect_modules()
        + _collect_assets()
        + _collect_perfetto_data()
        + [(str(version_file), ".")]
    )
    hidden = _hidden_imports()
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

    print(f"\n{'='*60}")
    print(f"  Building {name} v{version} ({'GUI' if not console else 'CLI'}) -> {build_name}")
    print(f"  Excluding {len(EXCLUDE_MODULES)} unused transitive deps")
    print(f"{'='*60}\n")

    try:
        subprocess.run(cmd, check=True, cwd=str(ROOT))
    finally:
        # 清理临时 spec 文件
        if spec.exists():
            spec.unlink()

    # 在构建产物中创建 data/config/ + data/db/ 目录，从 modules/*/config/ 复制默认配置文件
    out_dir = DIST_DIR / build_name
    config_dir = out_dir / "data" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    db_dir = out_dir / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    modules_dir = ROOT / "modules"
    if modules_dir.exists():
        for mod_dir in sorted(modules_dir.iterdir()):
            src_config_dir = mod_dir / "config"
            if not src_config_dir.is_dir():
                continue
            mod_name = mod_dir.name
            if mod_name in {"game_perf"}:
                continue
            for f in src_config_dir.iterdir():
                if f.is_file() and not f.name.endswith((".pyc", ".pyo")):
                    dest = config_dir / f"{mod_name}_{f.name}"
                    if not dest.exists():
                        shutil.copy2(f, dest)
    print(f"  [OK] Created data/config/ + data/db/ directories with default configs in {out_dir}")

    # 规整产物到 dist/publish/（Velopack 要求 onedir 标准布局）
    publish_dir = DIST_DIR / "publish"
    if publish_dir.exists():
        shutil.rmtree(publish_dir, ignore_errors=True)
    shutil.copytree(out_dir, publish_dir)
    # 主 exe 重命名为固定名 Toolkit.exe（PyInstaller 产出带时间戳，Velopack --mainExe 需固定名）
    ts_exe = next((f for f in publish_dir.glob("Toolkit_*.exe")), None)
    if ts_exe:
        target_exe = publish_dir / "Toolkit.exe"
        if target_exe.exists():
            target_exe.unlink()
        ts_exe.rename(target_exe)
        print(f"  [OK] Renamed {ts_exe.name} -> Toolkit.exe")
    print(f"  [OK] Staged onedir output to {publish_dir}")
    return build_name


def package(version: str, gui_dir_name: str = "Toolkit") -> None:
    """将构建产物合并到统一目录并打包。"""
    os_name = "windows" if platform.system() == "Windows" else "linux"
    pkg_name = f"{APP_NAME}-v{version}-{os_name}"
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


def _resolve_vpk() -> str | None:
    """解析 vpk 可执行路径：优先 PATH，回退 ~/.dotnet/tools/vpk.exe。

    vpk 通过 ``dotnet tool install -g vpk`` 安装到用户级 tools 目录，
    新装后当前 shell 的 PATH 可能未刷新，故额外检查默认安装位置。
    """
    import shutil as _sh

    path = _sh.which("vpk")
    if path:
        return path
    # 回退：dotnet 全局工具默认安装位置
    tools_dir = Path(os.path.expanduser("~")) / ".dotnet" / "tools"
    for name in ("vpk.exe", "vpk"):
        candidate = tools_dir / name
        if candidate.exists():
            return str(candidate)
    return None


def pack_velopack(version: str) -> None:
    """用 Velopack vpk 打包 dist/publish/ 为 Setup.exe + delta 更新包。

    需 .NET SDK 全局工具 vpk（``dotnet tool install -g vpk``）。
    代码签名通过环境变量 VP_SIGNING_* 配置，未配置则跳过签名（内部 dev 构建）。
    """
    vpk_path = _resolve_vpk()
    if vpk_path is None:
        print("  [WARN] vpk CLI 未安装，跳过 Velopack 打包")
        print("  [INFO] 安装: dotnet tool install -g vpk")
        return

    publish_dir = DIST_DIR / "publish"
    if not publish_dir.exists():
        print("  [ERROR] dist/publish/ 不存在，请先运行 PyInstaller 构建")
        return

    cmd = [
        vpk_path, "pack",
        "--packId", "GamePerfToolkit",
        "--packVersion", version,
        "--packDir", str(publish_dir),
        "--mainExe", "Toolkit.exe",
    ]

    # 代码签名（可选）：环境变量 VP_SIGNING_* 存在则传签名参数
    sign_args: list[str] = []
    for env_key, vpk_flag in (
        ("VP_SIGNING_CERT", "--signParams"),
    ):
        val = os.environ.get(env_key)
        if val:
            sign_args.extend([vpk_flag, val])
    if not sign_args:
        print("  [INFO] 未配置签名凭证（VP_SIGNING_CERT），产出未签名（Windows SmartScreen 会警告）")
    else:
        cmd.extend(sign_args)

    print(f"\n{'='*60}")
    print(f"  Velopack pack v{version} -> Setup.exe + delta (vpk: {vpk_path})")
    print(f"{'='*60}\n")
    # vpk 默认输出到 cwd/Releases。指定 --outputDir 跨目录 MoveFile 在 Windows 上
    # 易触发文件锁竞态（杀软扫描），故用默认 Releases 后再用 Python 移到 dist/。
    releases_tmp = ROOT / "Releases"
    try:
        subprocess.run(cmd, check=True, cwd=str(ROOT))
        # 移动产物到 dist/Releases
        releases_dst = DIST_DIR / "Releases"
        if releases_dst.exists():
            shutil.rmtree(releases_dst, ignore_errors=True)
        if releases_tmp.exists():
            shutil.move(str(releases_tmp), str(releases_dst))
        print(f"  [OK] Velopack 打包完成，产物见 {releases_dst}")
    except subprocess.CalledProcessError as e:
        print(f"  [ERROR] vpk pack 失败: {e}")
    except FileNotFoundError:
        print("  [WARN] vpk 命令未找到，请确认 dotnet tool install -g vpk 已执行")


def main() -> None:
    """主流程：构建 GUI 可执行文件，然后打包。"""
    import argparse

    parser = argparse.ArgumentParser(description="Game Perf Toolkit 构建脚本")
    parser.add_argument("--gui-only", action="store_true", help="仅构建 GUI")
    parser.add_argument("--no-package", action="store_true", help="不打包（仅构建）")
    parser.add_argument(
        "--zip",
        action="store_true",
        help="额外产出便携 zip 包（过渡期兼容；默认仅 Velopack Setup.exe）",
    )
    parser.add_argument("--version", type=str, default="", help="手动指定版本号")
    args = parser.parse_args()

    version = args.version or _get_version()
    print(f"  Build version: {version}")

    t0 = _time.time()

    gui_dir_name = build(console=False, name="Toolkit", version=version)

    elapsed = _time.time() - t0
    print(f"\n  Build time: {elapsed:.1f}s")

    if args.no_package:
        return

    # 默认走 Velopack 打包（Setup.exe + delta 更新包）
    pack_velopack(version)

    # 过渡期：--zip 额外产出便携 zip
    if args.zip:
        package(version, gui_dir_name=gui_dir_name)


if __name__ == "__main__":
    main()
