"""统一测试运行脚本 — 依次运行主项目与各模块的测试。

解决 pytest 同名测试文件跨目录冲突的问题，将每组测试作为独立
的 pytest 会话运行，避免模块名碰撞。
"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PYTHON = str(ROOT / ".venv" / "Scripts" / "python.exe")

TEST_GROUPS: list[tuple[str, str]] = [
    ("主项目", "tests/"),
    ("device_disguise 模块", "modules/device_disguise/tests/"),
    ("game_perf 模块", "modules/game_perf/tests/"),
    ("perfdog_insights 模块", "modules/perfdog_insights/tests/"),
    ("perfetto_capture 模块", "modules/perfetto_capture/tests/"),
    ("perfetto_analysis 模块", "modules/perfetto_analysis/tests/"),
    ("workspace_tools 模块", "modules/workspace_tools/tests/"),
    ("agent_chat 模块", "modules/agent_chat/tests/"),
    ("llm_manager 模块", "modules/llm_manager/tests/"),
]


def main() -> int:
    total_pass = 0
    total_fail = 0
    failed_groups: list[str] = []

    for label, path in TEST_GROUPS:
        full_path = ROOT / path
        if not full_path.exists():
            print(f"\n⚠ [{label}] 目录不存在：{path}，跳过")
            continue

        print(f"\n{'=' * 60}")
        print(f"  [{label}] {path}")
        print("=" * 60)

        # 空测试目录（无 test_*.py）跳过，不因 pytest 返回码 5（0 tests）误判失败
        if not list(full_path.glob("test_*.py")):
            print("  （无测试文件，跳过）")
            continue

        result = subprocess.run(
            [PYTHON, "-m", "pytest", str(full_path), "-v", "--tb=short"],
            cwd=str(ROOT),
        )

        if result.returncode == 0:
            total_pass += 1
        else:
            total_fail += 1
            failed_groups.append(label)

    print(f"\n{'=' * 60}")
    print(f"  汇总: {total_pass} 组通过, {total_fail} 组失败")
    if failed_groups:
        for g in failed_groups:
            print(f"    ✗ {g}")
    else:
        print("  ✓ 全部通过")
    print("=" * 60)

    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
