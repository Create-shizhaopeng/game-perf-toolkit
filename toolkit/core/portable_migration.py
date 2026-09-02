"""便携版数据迁移 — 将旧便携(zip 解压)版 data/ 迁移到新三层路径。

纯业务逻辑，MUST NOT 包含 GUI 代码。GUI 层通过 PortableMigrator 的回调获取进度。

迁移映射规则:
    data/config/*.json  → config roaming 根 (扁平，但旧已是扁平命名)
    data/db/*.db         → data local db/
    data/backup/         → data local backup/
    data/logs/           → 跳过（日志无需迁移）
    output/trace/        → output 根 trace/
    output/trace_report/ → output 根 trace_report/

目标已存在且更新则不覆盖。迁移成功或跳过后写标记文件防重复。
迁移失败非致命：保留已复制文件，记录错误，允许重试。
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from toolkit.core.app_paths import (
    get_user_config_dir,
    get_user_data_dir,
    get_user_output_dir,
)

logger = logging.getLogger(__name__)

MIGRATION_MARKER = ".migrated_from_portable"


@dataclass
class MigrationResult:
    """迁移结果。"""

    migrated_files: list[str] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)
    failed_files: list[tuple[str, str]] = field(default_factory=list)  # (path, error)
    marker_written: bool = False
    source_path: str = ""

    @property
    def success(self) -> bool:
        return not self.failed_files

    @property
    def total(self) -> int:
        return len(self.migrated_files) + len(self.skipped_files) + len(self.failed_files)


class PortableMigrator:
    """便携版数据迁移器。

    从旧便携版目录（含 ``data/`` 子目录）迁移用户数据到新三层路径。
    """

    def __init__(self) -> None:
        self._config_dir = get_user_config_dir()
        self._data_dir = get_user_data_dir()
        self._output_dir = get_user_output_dir()

    # ── 公共 API ──

    def is_migration_needed(self) -> bool:
        """检测是否需要迁移：无标记文件且新 config 层为空（全新安装特征）。

        返回 True 表示可能从便携版升级，应提示用户。
        """
        marker = self._config_dir / MIGRATION_MARKER
        if marker.exists():
            return False
        # 新 config 层已有用户配置文件 → 非全新安装，不迁移
        existing_configs = (
            list(self._config_dir.glob("*.json")) if self._config_dir.exists() else []
        )
        if existing_configs:
            return False
        return True

    def validate_source(self, source: Path) -> bool:
        """校验源目录是否为有效旧便携版（含 data/ 子目录）。"""
        return source.is_dir() and (source / "data").is_dir()

    def migrate(
        self,
        source: Path,
        on_progress: "callable[[str, int, int], None] | None" = None,
    ) -> MigrationResult:
        """执行迁移。

        Args:
            source: 旧便携版根目录（含 data/）
            on_progress: 进度回调 (current_file, done, total)，可选

        Returns:
            MigrationResult
        """
        result = MigrationResult(source_path=str(source))
        if not self.validate_source(source):
            result.failed_files.append((str(source), "源目录无效：缺少 data/ 子目录"))
            return result

        tasks = self._build_task_list(source)
        total = len(tasks)
        for idx, (src, dst) in enumerate(tasks):
            try:
                self._copy_if_needed(src, dst, result)
            except Exception as e:  # noqa: BLE001
                result.failed_files.append((str(src), str(e)))
                logger.warning("迁移失败 %s: %s", src, e)
            if on_progress:
                on_progress(str(src), idx + 1, total)

        # 写迁移标记
        if not result.failed_files or result.migrated_files:
            self._write_marker(source)
            result.marker_written = True

        logger.info(
            "迁移完成: %d 迁移, %d 跳过, %d 失败 (源: %s)",
            len(result.migrated_files),
            len(result.skipped_files),
            len(result.failed_files),
            source,
        )
        return result

    def write_skip_marker(self) -> None:
        """用户选择跳过时写标记，避免重复提示。"""
        self._write_marker(Path("(skipped)"))

    def read_marker(self) -> dict | None:
        """读取迁移标记内容，返回 {timestamp, source} 或 None。"""
        marker = self._config_dir / MIGRATION_MARKER
        if not marker.exists():
            return None
        try:
            text = marker.read_text(encoding="utf-8").strip()
            # 格式: timestamp|source
            if "|" in text:
                ts, src = text.split("|", 1)
                return {"timestamp": ts, "source": src}
            return {"timestamp": text, "source": ""}
        except Exception:
            return None

    # ── 内部 ──

    def _build_task_list(self, source: Path) -> list[tuple[Path, Path]]:
        """构建 (src, dst) 复制任务列表。"""
        tasks: list[tuple[Path, Path]] = []
        data_dir = source / "data"

        # config 层：data/config/*.json → config roaming
        config_src = data_dir / "config"
        if config_src.is_dir():
            for f in config_src.glob("*.json"):
                tasks.append((f, self._config_dir / f.name))

        # db 层：data/db/*.db → data local/db/
        db_src = data_dir / "db"
        if db_src.is_dir():
            for f in db_src.glob("*.db"):
                tasks.append((f, self._data_dir / "db" / f.name))

        # backup 层：data/backup/** → data local/backup/
        backup_src = data_dir / "backup"
        if backup_src.is_dir():
            for f in backup_src.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(backup_src)
                    tasks.append((f, self._data_dir / "backup" / rel))

        # logs 跳过

        # output 层：output/trace/ → output 根 trace/
        #           output/trace_report/ → output 根 trace_report/
        output_src = source / "output"
        if output_src.is_dir():
            for sub in ("trace", "trace_report"):
                sub_src = output_src / sub
                if sub_src.is_dir():
                    for f in sub_src.rglob("*"):
                        if f.is_file():
                            rel = f.relative_to(sub_src)
                            tasks.append((f, self._output_dir / sub / rel))

        return tasks

    def _copy_if_needed(self, src: Path, dst: Path, result: MigrationResult) -> None:
        """复制文件，目标已存在且更新则跳过。"""
        if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
            result.skipped_files.append(str(dst))
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        result.migrated_files.append(str(dst))

    def _write_marker(self, source: Path) -> None:
        """写迁移标记文件。"""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        marker = self._config_dir / MIGRATION_MARKER
        ts = datetime.now().isoformat(timespec="seconds")
        marker.write_text(f"{ts}|{source}", encoding="utf-8")
