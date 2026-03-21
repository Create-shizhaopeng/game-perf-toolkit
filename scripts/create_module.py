"""模块脚手架 — 根据模板自动生成新模块目录结构

用法:
    python scripts/create_module.py <module_name> [--display-name "显示名称"] [--cli-ns 命名空间]
"""

from __future__ import annotations

import argparse
import io
import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True,
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True,
    )

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / "scripts" / "templates"
MODULES_DIR = ROOT / "modules"


def _to_class_name(name: str) -> str:
    """snake_case -> PascalCase"""
    return "".join(word.capitalize() for word in name.split("_"))


def _render(template: str, variables: dict[str, str]) -> str:
    """简单的 {{key}} 模板替换。"""
    result = template
    for key, value in variables.items():
        result = result.replace("{{" + key + "}}", value)
    return result


def create_module(
    module_name: str,
    display_name: str | None = None,
    cli_namespace: str | None = None,
) -> Path:
    """生成模块骨架目录。"""
    if not re.match(r"^[a-z][a-z0-9_]*$", module_name):
        print(f"错误: 模块名 '{module_name}' 不合法，需为小写字母+下划线格式", file=sys.stderr)
        sys.exit(1)

    module_dir = MODULES_DIR / module_name
    if module_dir.exists():
        print(f"错误: 模块目录已存在: {module_dir}", file=sys.stderr)
        sys.exit(1)

    display = display_name or module_name.replace("_", " ").title()
    cli_ns = cli_namespace or module_name.replace("_", "-")
    class_name = _to_class_name(module_name)

    variables = {
        "module_name": module_name,
        "display_name": display,
        "cli_namespace": cli_ns,
        "class_name": class_name,
    }

    dirs = [
        module_dir / "src" / "migrations",
        module_dir / "tests",
        module_dir / "specs",
        module_dir / "fixtures",
        module_dir / "assets",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    manifest_tpl = (TEMPLATES_DIR / "manifest.json.tpl").read_text("utf-8")
    (module_dir / "manifest.json").write_text(
        _render(manifest_tpl, variables), encoding="utf-8"
    )

    plugin_tpl = (TEMPLATES_DIR / "plugin.py.tpl").read_text("utf-8")
    (module_dir / "src" / "plugin.py").write_text(
        _render(plugin_tpl, variables), encoding="utf-8"
    )

    agents_tpl = (TEMPLATES_DIR / "AGENTS.md.tpl").read_text("utf-8")
    (module_dir / "AGENTS.md").write_text(
        _render(agents_tpl, variables), encoding="utf-8"
    )

    (module_dir / "src" / "__init__.py").write_text("", encoding="utf-8")

    service_content = f'"""{ display } — 服务层"""\n\n\nclass {class_name}Service:\n    """{ display } 核心业务逻辑。"""\n\n    def get_service_info(self) -> dict:\n        return {{"name": "{module_name}", "display_name": "{display}"}}\n'
    (module_dir / "src" / "service.py").write_text(service_content, encoding="utf-8")

    cli_content = f'"""{ display } — CLI 子命令"""\n\nimport typer\n\n{cli_ns.replace("-", "_")}_app = typer.Typer(help="{display}")\n\n\n@{cli_ns.replace("-", "_")}_app.command("info")\ndef info():\n    """显示模块信息"""\n    typer.echo("{display} v0.1.0")\n'
    (module_dir / "src" / "cli_commands.py").write_text(cli_content, encoding="utf-8")

    gui_content = f'"""{ display } — GUI 页面"""\n\nfrom toolkit.gui.base_tab import BaseTab\n\n\nclass {class_name}Tab(BaseTab):\n    tab_title = "{display}"\n\n    def __init__(self, context=None, parent=None):\n        super().__init__(context, parent)\n'
    (module_dir / "src" / "gui_tab.py").write_text(gui_content, encoding="utf-8")

    (module_dir / "tests" / "__init__.py").write_text("", encoding="utf-8")
    test_content = f'"""{ display } 基础测试"""\n\nfrom modules.{module_name}.src.service import {class_name}Service\n\n\ndef test_service_info():\n    svc = {class_name}Service()\n    info = svc.get_service_info()\n    assert info["name"] == "{module_name}"\n'
    (module_dir / "tests" / f"test_{module_name}.py").write_text(
        test_content, encoding="utf-8"
    )

    print(f"模块骨架已创建: {module_dir}")
    print(f"  显示名称: {display}")
    print(f"  CLI 命名空间: {cli_ns}")
    print(f"  类名: {class_name}Plugin / {class_name}Service / {class_name}Tab")

    _init_speckit(module_dir, module_name, display, variables)

    print()
    print("下一步操作:")
    print("  1. 编辑 manifest.json 补充 description 和 author")
    print("  2. 实现 src/service.py 中的核心业务逻辑")
    print("  3. 使用 /speckit.specify 创建功能规格")

    return module_dir


def _init_speckit(module_dir: Path, module_name: str, display: str, variables: dict) -> None:
    """在模块目录下初始化 speckit 并生成模块级 constitution。"""
    uvx_path = shutil.which("uvx")
    if not uvx_path:
        print()
        print("⚠ 未检测到 uvx 命令，跳过 speckit 自动初始化。")
        print("  请手动执行:")
        print(f"    cd {module_dir}")
        print("    uvx --from git+https://github.com/github/spec-kit.git specify init --here --no-git --ai cursor-agent --script ps")
        return

    print()
    print("初始化 speckit...")
    try:
        result = subprocess.run(
            [
                uvx_path, "--from", "git+https://github.com/github/spec-kit.git",
                "specify", "init", "--here", "--no-git",
                "--ai", "cursor-agent", "--script", "ps",
            ],
            cwd=str(module_dir),
            input="y\n",
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print("✓ speckit 初始化成功")
        else:
            print(f"⚠ speckit 初始化返回非零码 ({result.returncode})，请检查输出")
            if result.stderr:
                print(f"  stderr: {result.stderr[:300]}")
    except FileNotFoundError:
        print("⚠ uvx 执行失败，请确认 uvx 已正确安装")
        return
    except subprocess.TimeoutExpired:
        print("⚠ speckit 初始化超时（120s），请手动执行")
        return

    _write_module_constitution(module_dir, module_name, display, variables)


def _write_module_constitution(
    module_dir: Path, module_name: str, display: str, variables: dict,
) -> None:
    """生成模块级 constitution，继承主 constitution 并添加模块边界约束。"""
    constitution_path = module_dir / ".specify" / "memory" / "constitution.md"
    if not constitution_path.parent.exists():
        constitution_path.parent.mkdir(parents=True, exist_ok=True)

    prefix = module_name[:2] if len(module_name) >= 2 else module_name
    short_prefixes = {
        "device_disguise": "dd",
        "game_perf": "gp",
        "log_analysis": "la",
        "trace_analysis": "ta",
        "strategy_report": "sr",
    }
    prefix = short_prefixes.get(module_name, prefix)

    content = f"""# {display}模块 Constitution

## 目录

- [继承关系](#继承关系)
- [模块边界约束](#模块边界约束)
- [技术约束](#技术约束)
- [开发规范](#开发规范)

## 继承关系

本模块 Constitution 继承自项目根 Constitution（`../../.specify/memory/constitution.md`），所有根 Constitution 中定义的原则、技术栈约束和开发流程均 MUST 适用于本模块。

以下仅补充模块级约束，不重复根级内容。

## 模块边界约束

- ✅ 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`
- ❌ 禁止修改：`toolkit/`、其他模块目录、项目根配置文件
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`
- ❌ 禁止导入：`toolkit.core` 内部实现（plugin_manager、db_manager 等）、其他模块的 `src/`
- 插件 context 键名 MUST 使用 `{prefix}_` 前缀（如 `{prefix}_service`、`{prefix}_adb`）

## 技术约束

[根据模块需求补充具体技术约束]

## 开发规范

- 遵循项目根 `scripts/doc/development-pitfalls.md` 中列出的踩坑指南
- 后台耗时操作 MUST 使用 `QThread` + `pyqtSignal` 与 GUI 线程通信
- service 层纯同步，MUST NOT 包含 PyQt6 代码

**Version**: 1.0.0 | **Last Updated**: auto-generated
"""
    constitution_path.write_text(content, encoding="utf-8")
    print(f"✓ 模块 constitution 已生成: {constitution_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="创建新模块骨架")
    parser.add_argument("module_name", help="模块名称（小写下划线格式，如 log_analysis）")
    parser.add_argument("--display-name", help="模块显示名称（如 '日志分析'）")
    parser.add_argument("--cli-ns", help="CLI 命名空间（如 log）")

    args = parser.parse_args()
    create_module(args.module_name, args.display_name, args.cli_ns)


if __name__ == "__main__":
    main()
