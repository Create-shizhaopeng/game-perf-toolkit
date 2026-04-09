import sys as _sys
from pathlib import Path as _Path


def _read_version() -> str:
    """从构建产物 VERSION 文件或 git 读取版本号。"""
    # PyInstaller 打包后 _MEIPASS 所在目录
    base = _Path(getattr(_sys, "_MEIPASS", _Path(__file__).parent.parent))
    version_file = base / "VERSION"
    if version_file.exists():
        try:
            return version_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass

    # 开发环境从 git 读取
    try:
        import subprocess
        result = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            capture_output=True, text=True,
            cwd=str(_Path(__file__).parent.parent),
        )
        tag = result.stdout.strip()
        if tag.startswith("v"):
            tag = tag[1:]
        if tag:
            return tag
    except Exception:
        pass

    return "0.1.1"


__version__ = _read_version()
