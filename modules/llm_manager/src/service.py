"""LLMManagerService — Provider 配置管理 + Token 记录 + 文件监听。"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from PyQt6.QtCore import QFileSystemWatcher, QObject, pyqtSignal

from toolkit.core.app_paths import (
    get_config_path,
    get_exe_dir,
    get_user_config_dir,
    get_user_data_dir,
)
from toolkit.core.db_manager import DatabaseManager
from .models import LLMProvidersConfig, ProviderConfig, ModelConfig

LOGGER = logging.getLogger("llm_manager.service")


class LLMConfigError(Exception):
    """LLM 配置异常基类。"""


class LLMConfigValidationError(LLMConfigError):
    """Pydantic 验证失败。"""


class LLMConfigNotFoundError(LLMConfigError):
    """配置文件不存在且无法重建。"""


class LLMManagerService(QObject):
    """LLM Provider 配置管理服务（QObject，支持文件监听 + 信号通知）。

    通过 ServiceRegistry 注册为 "llm_manager_service"。
    负责 llm_providers.json 的读写、Provider CRUD、配置迁移。
    内置 QFileSystemWatcher 监听配置文件外部变更，自动 reload 并通知消费者。
    """

    config_changed = pyqtSignal()

    def __init__(self, db_manager: DatabaseManager | None = None) -> None:
        super().__init__()
        self._config_path = get_config_path("llm_manager", "llm_providers.json")
        self._config: LLMProvidersConfig | None = None
        self._db_manager = db_manager
        self._token_tracker: "TokenTracker | None" = None
        self._watcher: QFileSystemWatcher | None = None
        self._start_watching()

    # ------------------------------------------------------------------
    # 配置加载 / 保存
    # ------------------------------------------------------------------

    def load(self) -> LLMProvidersConfig:
        """加载配置。首次调用时若文件不存在，自动迁移旧配置。"""
        if self._config is not None:
            return self._config

        if not self._config_path.exists():
            self._migrate_from_old_config()

        try:
            raw = self._config_path.read_text(encoding="utf-8")
            self._config = LLMProvidersConfig.model_validate_json(raw)
            LOGGER.info("LLM Provider 配置已加载: %d 个 Provider", len(self._config.providers))
        except Exception:
            LOGGER.warning("llm_providers.json 损坏，使用内置默认配置")
            self._config = self._default_config()
            self.save()

        return self._config

    def save(self) -> None:
        """保存配置（原子写入 + 防抖：写前暂停 watcher 避免自触发）。"""
        if self._config is None:
            return
        self._pause_watcher()
        tmp = self._config_path.with_suffix(".tmp")
        try:
            tmp.write_text(
                self._config.model_dump_json(indent=2, exclude_none=True),
                encoding="utf-8",
            )
            tmp.replace(self._config_path)
            LOGGER.info("LLM Provider 配置已保存")
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise LLMConfigError("Failed to write config")
        finally:
            self._resume_watcher()

    def reload(self) -> LLMProvidersConfig:
        """强制重新加载（忽略缓存）。"""
        self._config = None
        return self.load()

    # ------------------------------------------------------------------
    # Provider CRUD
    # ------------------------------------------------------------------

    def list_providers(self, enabled_only: bool = True) -> list[ProviderConfig]:
        cfg = self.load()
        if enabled_only:
            return [p for p in cfg.providers if p.enabled]
        return list(cfg.providers)

    def get_provider(self, provider_id: str) -> ProviderConfig | None:
        return self.load().get_provider(provider_id)

    def add_provider(self, provider: ProviderConfig) -> None:
        cfg = self.load()
        existing = cfg.get_provider(provider.id)
        if existing:
            cfg.providers.remove(existing)
        cfg.providers.append(provider)
        self.save()
        LOGGER.info("已添加 Provider: %s", provider.id)

    def remove_provider(self, provider_id: str) -> None:
        cfg = self.load()
        target = cfg.get_provider(provider_id)
        if target is None:
            raise LLMConfigNotFoundError(f"Provider 不存在: {provider_id}")
        cfg.providers.remove(target)
        if cfg.active_provider == provider_id:
            cfg.active_provider = cfg.providers[0].id if cfg.providers else ""
        self.save()
        LOGGER.info("已删除 Provider: %s", provider_id)

    def update_provider(self, provider: ProviderConfig) -> None:
        cfg = self.load()
        existing = cfg.get_provider(provider.id)
        if existing:
            cfg.providers.remove(existing)
        cfg.providers.append(provider)
        self.save()
        LOGGER.info("已更新 Provider: %s", provider.id)

    def set_active_provider(self, provider_id: str) -> None:
        cfg = self.load()
        if cfg.get_provider(provider_id) is None:
            raise LLMConfigNotFoundError(f"Provider 不存在: {provider_id}")
        cfg.active_provider = provider_id
        self.save()

    def set_active_model(self, model_name: str) -> None:
        cfg = self.load()
        prov = cfg.get_active()
        if prov is None:
            raise LLMConfigNotFoundError("未设置活跃 Provider")
        if prov.get_model(model_name) is None:
            raise LLMConfigValidationError(f"Model not found: {model_name}")
        prov.default_model = model_name
        self.save()

    # ------------------------------------------------------------------
    # 活跃配置获取
    # ------------------------------------------------------------------

    def get_active_provider_config(self) -> tuple[ProviderConfig, ModelConfig]:
        """返回 (ProviderConfig, ModelConfig) 供 LLMManager 初始化。"""
        cfg = self.load()
        prov = cfg.get_active()
        if prov is None:
            raise LLMConfigNotFoundError("未设置活跃 Provider")
        model = prov.get_model()
        if model is None:
            raise LLMConfigNotFoundError("No model configured")
        return prov, model

    def get_context_window_size(self) -> int:
        """当前活跃模型上下文窗口大小。"""
        _, model = self.get_active_provider_config()
        return model.context_window

    # ------------------------------------------------------------------
    # Token tracker
    # ------------------------------------------------------------------

    def get_token_tracker(self) -> "TokenTracker":
        if self._token_tracker is None:
            self._token_tracker = TokenTracker(self._db_manager)
        return self._token_tracker

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _default_config(self) -> LLMProvidersConfig:
        """内置默认配置（GLM + Claude）。"""
        default_path = (
            get_exe_dir() / "modules" / "llm_manager" / "config" / "llm_providers.json"
        )
        if default_path.exists():
            try:
                return LLMProvidersConfig.model_validate_json(
                    default_path.read_text(encoding="utf-8")
                )
            except Exception:
                pass
        from .models import ModelConfig

        return LLMProvidersConfig(
            providers=[
                ProviderConfig(
                    id="glm",
                    name="GLM (智谱)",
                    base_url="https://open.bigmodel.cn/api/paas/v4/",
                    litellm_prefix="zai/",
                    models=[
                        ModelConfig(name="glm-4-plus", context_window=128000),
                        ModelConfig(name="glm-4-flash", context_window=128000),
                        ModelConfig(name="glm-4-long", context_window=1000000),
                    ],
                    default_model="glm-4-plus",
                ),
                ProviderConfig(
                    id="claude",
                    name="Claude (Anthropic)",
                    base_url="https://api.anthropic.com/",
                    thinking=True,
                    models=[
                        ModelConfig(name="claude-sonnet-4-20250514", context_window=200000),
                        ModelConfig(name="claude-opus-4-7", context_window=1000000),
                    ],
                    default_model="claude-sonnet-4-20250514",
                ),
            ],
            active_provider="glm",
        )

    def _migrate_from_old_config(self) -> None:
        """从 toolkit_config.json["llm"] 迁移旧 API Key。"""
        try:
            cfg_path = get_user_config_dir() / "toolkit_config.json"
            if not cfg_path.exists():
                self._generate_default_config()
                return

            import json

            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
            llm = raw.get("llm", {})
            if not llm or llm.get("_migrated_to_llm_providers"):
                self._generate_default_config()
                return

            config = self._default_config()
            glm_key = llm.get("glm_api_key", "")
            claude_key = llm.get("claude_api_key", "")
            old_provider = llm.get("provider", "glm")

            for p in config.providers:
                if p.id == "glm" and glm_key:
                    p.api_key = glm_key
                elif p.id == "claude" and claude_key:
                    p.api_key = claude_key

            config.active_provider = old_provider
            self._config = config
            self.save()

            raw["llm"]["_migrated_to_llm_providers"] = True
            cfg_path.write_text(
                json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            LOGGER.info("已从旧配置迁移 LLM API Key")
        except Exception:
            self._generate_default_config()

    # ------------------------------------------------------------------
    # 文件监听（实时感知外部编辑）
    # ------------------------------------------------------------------

    def _start_watching(self) -> None:
        """启动 QFileSystemWatcher 监听配置文件外部变更。"""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            if not self._config_path.exists():
                self._config_path.touch()
            self._watcher = QFileSystemWatcher([str(self._config_path)])
            self._watcher.fileChanged.connect(self._on_file_changed)
            LOGGER.debug("LLM 配置文件监听已启动: %s", self._config_path)
        except Exception:
            LOGGER.warning("无法监听 LLM 配置文件", exc_info=True)

    def _pause_watcher(self) -> None:
        """临停 watcher，防止 save() 触发自己。"""
        if self._watcher:
            try:
                self._watcher.blockSignals(True)
            except Exception:
                pass

    def _resume_watcher(self) -> None:
        """恢复 watcher（save 完成后调用）。"""
        if self._watcher:
            try:
                self._watcher.blockSignals(False)
            except Exception:
                pass

    def _on_file_changed(self, path: str) -> None:
        """配置文件被外部编辑 → reload 并通知消费者。"""
        LOGGER.info("检测到 LLM 配置文件变更，自动 reload")
        try:
            self.reload()
            self.config_changed.emit()
        except Exception:
            LOGGER.warning("LLM 配置热重载失败", exc_info=True)
        # 重新添加 watcher（原子写入 replace 后 inode 可能变化）
        if self._watcher:
            try:
                paths = self._watcher.files()
                if str(self._config_path) not in paths:
                    self._watcher.addPath(str(self._config_path))
            except Exception:
                pass

    def _generate_default_config(self) -> None:
        self._config = self._default_config()
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self.save()


class TokenTracker:
    """Token 用量后台记录器 — 写入 SQLite。"""

    def __init__(self, db_manager: DatabaseManager | None = None) -> None:
        self._db = db_manager
        self._table = "llm_token_usage"

    def record(
        self,
        request_id: str = "",
        provider: str = "",
        model: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        conversation_id: str | None = None,
        trace_id: str | None = None,
    ) -> None:
        """记录一次 LLM 请求的 Token 用量。"""
        rid = request_id or uuid.uuid4().hex[:12]
        try:
            import sqlite3

            db_path = get_user_data_dir() / "db" / "llm_token_usage.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                """CREATE TABLE IF NOT EXISTS llm_token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    conversation_id TEXT,
                    trace_id TEXT,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    timestamp TEXT NOT NULL DEFAULT (datetime('now'))
                )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_llm_token_conv ON llm_token_usage(conversation_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_llm_token_trace ON llm_token_usage(trace_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_llm_token_timestamp ON llm_token_usage(timestamp)"
            )
            conn.execute(
                "INSERT INTO llm_token_usage "
                "(request_id, conversation_id, trace_id, provider, model, prompt_tokens, completion_tokens) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (rid, conversation_id, trace_id, provider, model, prompt_tokens, completion_tokens),
            )
            conn.commit()
            conn.close()
            LOGGER.debug("Token 用量已记录: %s/%s, %d+%d tokens", provider, model, prompt_tokens, completion_tokens)
        except Exception:
            LOGGER.warning("Token record failed", exc_info=True)

    def get_usage_by_conversation(self, conversation_id: str) -> dict:
        return self._aggregate("conversation_id = ?", [conversation_id])

    def get_usage_by_trace(self, trace_id: str) -> dict:
        return self._aggregate("trace_id = ?", [trace_id])

    def get_total_usage(self, provider: str | None = None) -> dict:
        if provider:
            return self._aggregate("provider = ?", [provider])
        return self._aggregate("1=1", [])

    def _aggregate(self, where: str, params: list) -> dict:
        try:
            import sqlite3

            db_path = get_user_data_dir() / "db" / "llm_token_usage.db"
            conn = sqlite3.connect(str(db_path))
            row = conn.execute(
                f"SELECT SUM(prompt_tokens), SUM(completion_tokens), COUNT(*) "
                f"FROM llm_token_usage WHERE {where}",
                params,
            ).fetchone()
            conn.close()
            if row and row[0] is not None:
                return {
                    "prompt_tokens": int(row[0]),
                    "completion_tokens": int(row[1]),
                    "total_tokens": int(row[0]) + int(row[1]),
                    "request_count": int(row[2]),
                }
        except Exception:
            pass
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "request_count": 0}
