# -*- coding: utf-8 -*-
"""文件型配置服务基类 — 统一封装 QFileSystemWatcher + 原子写入 + 变更通知。

使用方式:
    class MyService(FileConfigService):
        def __init__(self):
            super().__init__(config_path=Path("data/config/my.json"))
            self.load()
            self._start_watching()

        def _do_load(self):
            import json
            return json.loads(self.config_path.read_text("utf-8"))

        def _do_save(self, config):
            import json
            tmp = self.config_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False), "utf-8")
            tmp.replace(self.config_path)

消费者连接:
    service.config_changed.connect(self._on_config_changed)
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QFileSystemWatcher, QObject, pyqtSignal


class FileConfigService(QObject):
    """文件型配置服务基类。

    封装 QFileSystemWatcher + 原子写入 + 变更信号，子类只需实现 _do_load / _do_save。
    """

    config_changed = pyqtSignal()

    def __init__(self, config_path: Path | None = None) -> None:
        super().__init__()
        self.config_path = config_path
        self._watcher: QFileSystemWatcher | None = None
        self._config: object | None = None

    # ── 子类覆盖 ──

    def _do_load(self) -> object:
        """从磁盘加载配置，返回配置对象。子类 MUST override。"""
        raise NotImplementedError

    def _do_save(self, config: object) -> None:
        """保存配置到磁盘。子类 MUST override。"""
        raise NotImplementedError

    # ── 公共 API ──

    def load(self) -> object:
        """加载配置（首次调用从磁盘读取，后续返回缓存）。"""
        if self._config is None:
            self._config = self._do_load()
        return self._config

    def save(self) -> None:
        """保存配置 + 防抖：写入前暂停 watcher 避免自触发。"""
        if self._config is None:
            return
        self._pause_watcher()
        try:
            self._do_save(self._config)
        finally:
            self._resume_watcher()

    def reload(self) -> object:
        """强制重新加载（忽略缓存）。"""
        self._config = None
        return self.load()

    # ── Watcher ──

    def _start_watching(self) -> None:
        """启动 QFileSystemWatcher 监听配置文件外部变更。"""
        if self.config_path is None:
            return
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self.config_path.touch()
        self._watcher = QFileSystemWatcher([str(self.config_path)])
        self._watcher.fileChanged.connect(self._on_file_changed)

    def _pause_watcher(self) -> None:
        """临停 watcher（save 前调用）。"""
        if self._watcher:
            try:
                self._watcher.blockSignals(True)
            except Exception:
                pass

    def _resume_watcher(self) -> None:
        """恢复 watcher（save 后调用）。"""
        if self._watcher:
            try:
                self._watcher.blockSignals(False)
            except Exception:
                pass

    def _on_file_changed(self, path: str) -> None:
        """外部编辑 → reload → 通知消费者。"""
        try:
            self.reload()
            self.config_changed.emit()
        except Exception:
            pass
        # replace() 可能改变 inode → 重新添加 watch 路径
        if self._watcher and str(self.config_path) not in self._watcher.files():
            self._watcher.addPath(str(self.config_path))
