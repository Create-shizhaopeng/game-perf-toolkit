"""集中式路径解析 — 用户数据三层分层 + 程序资源根统一路径管理。

基于 ``platformdirs`` 将用户数据按 OS 惯例三层分层：

- **config 层 (roaming)**: ``%APPDATA%\\Roaming\\game-perf-toolkit\\Game Perf Toolkit`` — 配置 JSON，跟随用户漫游
- **data 层 (local)**: ``%LOCALAPPDATA%\\game-perf-toolkit\\Game Perf Toolkit`` — db/logs/backup/cache，机器绑定
- **output 层 (Documents)**: ``Documents\\Game Perf Toolkit``（可配置） — trace/报告等用户产物

程序本体(只读)与用户数据(per-user 可写)彻底分离，安装到 ``Program Files`` 不会因 UAC 写失败。
所有模块 MUST 通过本模块解析路径，不再各自实现 ``sys.frozen`` 分支或直拼 ``get_exe_dir()/"data"``。

开发布局 (dev, 默认)::

    <root>/data/config/<module>_<file>     — 配置（dev 用 LV_TOOLKIT_DATA_DIR 覆盖到项目 data/）
    <root>/data/db/<module>_<db>.db        — 数据库
    <root>/data/output/<module>/           — 输出

Frozen 布局 (安装版)::

    %APPDATA%\\Roaming\\game-perf-toolkit\\Game Perf Toolkit\\<module>_<file>   — 配置
    %LOCALAPPDATA%\\game-perf-toolkit\\Game Perf Toolkit\\db\\<module>_<db>.db  — 数据库
    Documents\\Game Perf Toolkit\\<module>\\                              — 输出
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from platformdirs import (
    user_config_dir,
    user_data_dir,
    user_documents_dir,
)

APP_NAME = "Game Perf Toolkit"
APP_AUTHOR = "game-perf-toolkit"

# dev 模式下可通过环境变量覆盖 data 层根到项目本地目录（测试/开发便利）
_DEV_DATA_DIR_OVERRIDE = "LV_TOOLKIT_DATA_DIR"


def is_frozen() -> bool:
    """PyInstaller 打包环境则为 True。"""
    return getattr(sys, "frozen", False)


def get_exe_dir() -> Path:
    """只读程序资源根（不再用于写用户数据）。

    - frozen: exe 所在目录（如 ``Program Files\\Game Perf Toolkit`` 或 ``dist/Toolkit``）
    - 开发: 项目根目录（含 ``toolkit/``、``modules/``）

    .. note::

        本函数仅返回**只读程序资源根**，用于定位打包进程序的静态资源(图标、SKILL 模板等)。
        **MUST NOT** 用于写用户数据 —— 用户数据走三层根函数
        (:func:`get_user_config_dir` / :func:`get_user_data_dir` / :func:`get_user_output_dir`)。
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    # app_paths.py 在 toolkit/core/ 下，往上 3 层即项目根目录
    return Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# 三层用户数据根
# ---------------------------------------------------------------------------

def get_user_config_dir() -> Path:
    """配置层根（roaming，跟随用户）。

    - frozen: ``%APPDATA%\\Roaming\\game-perf-toolkit\\Game Perf Toolkit``
    - dev: 同 frozen（除非通过 :func:`get_user_data_dir` 的覆盖间接影响）

    存放各类 ``*.json`` 配置文件。
    """
    return Path(user_config_dir(APP_NAME, APP_AUTHOR, roaming=True))


def get_user_data_dir() -> Path:
    """数据层根（local，机器绑定）。

    - frozen: ``%LOCALAPPDATA%\\game-perf-toolkit\\Game Perf Toolkit``
    - dev: 若设置了 ``LV_TOOLKIT_DATA_DIR`` 环境变量，则覆盖为该目录（项目本地）；
      否则同 frozen 走 OS 标准路径。

    存放 db、logs、backup、cache 等机器绑定的数据。
    """
    if not is_frozen():
        override = os.environ.get(_DEV_DATA_DIR_OVERRIDE)
        if override:
            return Path(override).resolve()
    return Path(user_data_dir(APP_NAME, APP_AUTHOR))


def get_user_output_dir() -> Path:
    """产物层根（Documents，用户产物，可见可备份）。

    - 默认: ``Documents\\Game Perf Toolkit``
    - 可被 ``toolkit_config.json["output_dir"]`` 覆盖（由 :func:`get_output_dir` 处理）

    存放 trace、分析报告等用户主动产生的产物。
    """
    return Path(user_documents_dir()) / APP_NAME


# ---------------------------------------------------------------------------
# 配置路径
# ---------------------------------------------------------------------------

def get_config_path(module_name: str, filename: str) -> Path:
    """模块配置文件的绝对路径。

    - 开发: ``modules/<module_name>/config/<filename>``（只读模板，来自源码）
    - frozen: ``<user_config_dir>/<module_name>_<filename>`` (扁平命名，roaming 可写)
    """
    if is_frozen():
        return get_user_config_dir() / f"{module_name}_{filename}"
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
    存放目录：data 层根下 ``db/``（frozen 走 local APPDATA，dev 走 data 层根）。
    """
    db_file = f"{module_name}_{db_name}.db"
    base = get_user_data_dir() / "db"
    base.mkdir(parents=True, exist_ok=True)
    return base / db_file


# ---------------------------------------------------------------------------
# 备份路径
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 输出目录路径
# ---------------------------------------------------------------------------

def get_output_dir(module: str = "") -> Path:
    """模块输出目录的绝对路径。

    - dev: ``<user_data_dir>/output/<module>/``（受 LV_TOOLKIT_DATA_DIR 覆盖影响）
    - frozen: ``<user_output_dir>/<module>/``（默认 Documents\\Game Perf Toolkit，可被 config 覆盖）
    """
    if is_frozen():
        base = _resolve_output_root()
    else:
        base = get_user_data_dir() / "output"
    target = base / module if module else base
    target.mkdir(parents=True, exist_ok=True)
    return target


def _resolve_output_root() -> Path:
    """解析 frozen 模式下 output 根：优先读 config output_dir，否则默认 Documents。

    本函数仅在 frozen 模式调用。config 读取失败时回退默认，绝不抛异常。
    """
    default = get_user_output_dir()
    try:
        from toolkit.core.config_manager import ConfigManager  # 延迟导入避免循环

        cfg = ConfigManager(get_user_config_dir() / "toolkit_config.json")
        override = cfg.get("output_dir", "")
        if override:
            return Path(override).expanduser().resolve()
    except Exception:
        pass
    return default


def get_backup_path(module_name: str, filename: str = "") -> Path:
    """模块备份目录或文件的绝对路径。

    - 仅传入模块名：返回 data 层 ``backup/<module>/`` 目录并确保存在
    - 同时传入文件名：返回 ``backup/<module>/<filename>``
    """
    base = get_user_data_dir() / "backup" / module_name
    base.mkdir(parents=True, exist_ok=True)
    if filename:
        return base / filename
    return base
