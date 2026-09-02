# -*- coding: utf-8 -*-
"""便携版数据迁移对话框 — 首次启动引导用户迁移旧版数据。

继承 ToolkitDialog，遵循 ui-style-guide（objectName + 全局 QSS）与
string-extraction-gate（中文提取到 strings）。
"""
from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QWidget,
)

from toolkit.core.portable_migration import PortableMigrator
from toolkit.gui import strings as s
from toolkit.gui.toolkit_dialog import ToolkitDialog

logger = logging.getLogger(__name__)


class PortableMigrationDialog(ToolkitDialog):
    """便携版数据迁移对话框。

    让用户指定旧便携版目录，预览后将迁移，或跳过。
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(s.MIGRATION_DLG_TITLE, parent, min_width=480)
        self._migrator = PortableMigrator()
        self._source: Path | None = None
        self.setObjectName("portableMigrationDialog")

        # 说明
        msg = QLabel(s.MIGRATION_DLG_MSG)
        msg.setWordWrap(True)
        msg.setObjectName("dlgMsgLabel")
        self.content_layout.addWidget(msg)

        # 目录选择行
        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText(s.MIGRATION_DLG_NO_SOURCE)
        self._dir_edit.setReadOnly(True)
        browse_btn = QPushButton(s.MIGRATION_DLG_BROWSE)
        browse_btn.setObjectName("secondaryBtn")
        browse_btn.clicked.connect(self._on_browse)
        dir_row.addWidget(self._dir_edit, 1)
        dir_row.addWidget(browse_btn)
        self.content_layout.addLayout(dir_row)

        # 校验提示
        self._hint = QLabel("")
        self._hint.setObjectName("fieldHint")
        self.content_layout.addWidget(self._hint)

        # 进度条
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self.content_layout.addWidget(self._progress)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._skip_btn = QPushButton(s.MIGRATION_DLG_SKIP)
        self._skip_btn.setObjectName("secondaryBtn")
        self._skip_btn.clicked.connect(self._on_skip)
        self._migrate_btn = QPushButton(s.MIGRATION_DLG_MIGRATE)
        self._migrate_btn.setObjectName("primaryBtn")
        self._migrate_btn.setEnabled(False)
        self._migrate_btn.clicked.connect(self._on_migrate)
        btn_row.addWidget(self._skip_btn)
        btn_row.addWidget(self._migrate_btn)
        self.content_layout.addLayout(btn_row)

    def _on_browse(self) -> None:
        """选择旧便携版目录。"""
        chosen = QFileDialog.getExistingDirectory(self, s.MIGRATION_DLG_BROWSE, "")
        if not chosen:
            return
        self._source = Path(chosen)
        self._dir_edit.setText(chosen)
        if self._migrator.validate_source(self._source):
            self._hint.setText("")
            self._migrate_btn.setEnabled(True)
        else:
            self._hint.setText(s.MIGRATION_DLG_INVALID)
            self._migrate_btn.setEnabled(False)

    def _on_migrate(self) -> None:
        """执行迁移。"""
        if self._source is None:
            return
        self._migrate_btn.setEnabled(False)
        self._skip_btn.setEnabled(False)
        self._progress.setVisible(True)

        def on_progress(file: str, done: int, total: int) -> None:
            self._progress.setMaximum(total)
            self._progress.setValue(done)
            self._hint.setText(
                s.MIGRATION_DLG_PROGRESS_FMT.format(
                    done=done, total=total, file=Path(file).name
                )
            )

        result = self._migrator.migrate(self._source, on_progress=on_progress)
        if result.success:
            self._hint.setText(
                s.MIGRATION_DLG_SUCCESS_FMT.format(
                    migrated=len(result.migrated_files), skipped=len(result.skipped_files)
                )
            )
            logger.info("便携迁移成功: %s", self._source)
            self.accept()
        else:
            self._hint.setText(
                s.MIGRATION_DLG_FAILED_FMT.format(
                    migrated=len(result.migrated_files), failed=len(result.failed_files)
                )
            )
            logger.warning("便携迁移部分失败: %d 项", len(result.failed_files))
            self._skip_btn.setEnabled(True)

    def _on_skip(self) -> None:
        """跳过迁移并写标记防重复提示。"""
        self._migrator.write_skip_marker()
        self.reject()

    @staticmethod
    def should_show() -> bool:
        """是否应显示迁移对话框（供启动流程调用）。"""
        return PortableMigrator().is_migration_needed()
