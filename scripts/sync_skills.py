"""模块 Skills 同步脚本 — 将各模块的 skills 同步到 .cursor/skills/ 供 Cursor 发现。

扫描 modules/*/skills/*/SKILL.md，复制到项目根目录 .cursor/skills/ 下对应目录。
已存在的同名目录会被覆盖（以模块目录为准）。
"""

from __future__ import annotations

import io
import shutil
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = ROOT / "modules"
CURSOR_SKILLS_DIR = ROOT / ".cursor" / "skills"

MARKER_FILE = ".module-synced"
GITIGNORE_HEADER = "# 以下条目由 sync_skills.py 自动管理，请勿手动编辑\n"


def _update_gitignore(synced_dirs: list[str]) -> None:
    """更新 .cursor/skills/.gitignore，忽略模块同步来的目录。"""
    gitignore_path = CURSOR_SKILLS_DIR / ".gitignore"
    existing_lines: list[str] = []
    if gitignore_path.is_file():
        content = gitignore_path.read_text(encoding="utf-8")
        header_idx = content.find(GITIGNORE_HEADER)
        if header_idx >= 0:
            existing_lines = content[:header_idx].rstrip("\n").split("\n")
            existing_lines = [l for l in existing_lines if l.strip()]
        else:
            existing_lines = [l for l in content.strip().split("\n") if l.strip()]

    auto_entries = sorted(set(synced_dirs))
    parts = existing_lines + ["", GITIGNORE_HEADER.rstrip()]
    for entry in auto_entries:
        parts.append(f"{entry}/")

    gitignore_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def sync_skills() -> None:
    """扫描所有模块的 skills 目录，同步到 .cursor/skills/。"""
    if not MODULES_DIR.exists():
        print("未找到 modules/ 目录")
        return

    synced = 0
    synced_dirs: list[str] = []
    for module_dir in sorted(MODULES_DIR.iterdir()):
        skills_dir = module_dir / "skills"
        if not skills_dir.is_dir():
            continue
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue

            target_dir = CURSOR_SKILLS_DIR / skill_dir.name
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(skill_dir, target_dir)
            (target_dir / MARKER_FILE).write_text(
                f"synced-from: {skill_dir.relative_to(ROOT)}\n",
                encoding="utf-8",
            )
            synced += 1
            synced_dirs.append(skill_dir.name)
            print(
                f"  已同步: {module_dir.name}/skills/{skill_dir.name} "
                f"→ .cursor/skills/{skill_dir.name}"
            )

    if synced == 0:
        print("未发现任何模块 Skills")
    else:
        _update_gitignore(synced_dirs)
        print(f"\n共同步 {synced} 个 Skill")


def clean_synced() -> None:
    """清理由本脚本同步到 .cursor/skills/ 的条目（包含标记文件的目录）。"""
    if not CURSOR_SKILLS_DIR.exists():
        return

    removed = 0
    for skill_dir in sorted(CURSOR_SKILLS_DIR.iterdir()):
        marker = skill_dir / MARKER_FILE
        if marker.is_file():
            shutil.rmtree(skill_dir)
            removed += 1
            print(f"  已清理: .cursor/skills/{skill_dir.name}")

    if removed == 0:
        print("无同步条目需要清理")
    else:
        print(f"\n共清理 {removed} 个同步条目")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if action == "sync":
        print("同步模块 Skills 到 .cursor/skills/ ...\n")
        sync_skills()
    elif action == "clean":
        print("清理同步条目 ...\n")
        clean_synced()
    else:
        print(f"用法: python {Path(__file__).name} [sync|clean]")
        sys.exit(1)
