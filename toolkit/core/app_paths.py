"""集中式路径解析 — 配置文件、数据库、备份文件统一路径管理。

所有模块必须通过此模块解析路径，不再各自实现 ``sys.frozen`` 分支。

开发布局::

    modules/<name>/config/<file>        — 配置文件模板
    data/db/<module>_<db>.db           — 数据库
    data/backup/<module>/<file>        — 备份文件

Frozen 布局 (exe 同级目录)::

    data/config/<module>_<file>        — 构建时从 modules/*/config/ 复制（扁平命名）
    data/db/<module>_<db>.db           — 数据库
    data/backup/<module>/<file>        — 备份文件
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    """PyInstaller 打包环境则为 True。"""
    return getattr(sys, "frozen", False)


def get_exe_dir() -> Path:
    """应用基准目录。

    - frozen: exe 所在目录（如 ``dist/Toolkit/``）
    - 开发: 项目根目录（含 ``toolkit/``、``modules/``）
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    # app_paths.py 在 toolkit/core/ 下，往上 3 层即项目根目录
    return Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# 配置路径
# ---------------------------------------------------------------------------

def get_config_path(module_name: str, filename: str) -> Path:
    """模块配置文件的绝对路径。

    - 开发: ``modules/<module_name>/config/<filename>``
    - frozen: ``<exe_dir>/data/config/<module_name>_<filename>`` (扁平命名)
    """
    if is_frozen():
        return get_exe_dir() / "data" / "config" / f"{module_name}_{filename}"
    return get_exe_dir() / "modules" / module_name / "config" / filename


def ensure_config_dir(module_name: str) -> Path:
    """确保模块配置目录存在并返回路径。"""
    p = get_config_path(module_name, ".placeholder").parent
    p.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# 数据库路径
# ---------------------------------------------------------------------------

def get_db_path(module_name: str, db_name: str) -> Path:
    """模块数据库文件的绝对路径。

    命名规范：``<module_name>_<db_name>.db``
    存放目录（dev 与 frozen 同构）：``data/db/``
    """
    db_file = f"{module_name}_{db_name}.db"
    base = get_exe_dir() / "data" / "db"
    base.mkdir(parents=True, exist_ok=True)
    return base / db_file


# ---------------------------------------------------------------------------
# 备份路径
# ---------------------------------------------------------------------------

def get_backup_path(module_name: str, filename: str = "") -> Path:
    """模块备份目录或文件的绝对路径。

    - 仅传入模块名：返回 ``data/backup/<module>/`` 目录并确保存在
    - 同时传入文件名：返回 ``data/backup/<module>/<filename>``
    """
    base = get_exe_dir() / "data" / "backup" / module_name
    base.mkdir(parents=True, exist_ok=True)
    if filename:
        return base / filename
    return base
