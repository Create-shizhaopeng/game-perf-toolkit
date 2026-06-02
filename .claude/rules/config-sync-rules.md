# 配置实时同步规范

防止配置文件外部编辑导致内存状态不同步。本规则适用于所有从磁盘 JSON/YAML 文件加载配置并缓存在内存的服务。

## 目录

- [核心原则](#核心原则)
- [可复用基类](#可复用基类)
- [硬约束](#硬约束)
- [项目现状与待修复](#项目现状与待修复)
- [检查清单](#检查清单)
- [关联规则](#关联规则)

## 核心原则

**配置文件是真相源，内存是缓存。任何时刻外部编辑配置文件，所有消费者 MUST 在可感知的时间内获得最新值。**

当前项目已具备 `EventBus`（`toolkit.core.event_bus`）和 `pyqtSignal`（Qt 组件通信），但缺少将 **OS 文件变更事件 → 应用通知** 的标准化桥接。本规范填补这个空缺。

## 可复用基类

以下基类封装了 watcher + 防抖 + 信号的标准模式。新服务直接继承即可：

```python
# toolkit/core/config_service.py
"""文件型配置服务基类 — 统一封装 QFileSystemWatcher + 原子写入 + 变更通知。"""
from __future__ import annotations

from pathlib import Path
from PyQt6.QtCore import QFileSystemWatcher, QObject, pyqtSignal


class FileConfigService(QObject):
    """文件型配置服务基类。

    子类只需：
      1. 设置 self.config_path
      2. 实现 _do_load() → 返回配置对象
      3. 实现 _do_save(config) → 写入磁盘
      4. 可选：在 __init__ 中调用 super().__init__() 后调用 self._start_watching()
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
        if self._config is None:
            self._config = self._do_load()
        return self._config

    def save(self) -> None:
        """保存 + 防抖：写入前暂停 watcher 避免自触发。"""
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
        if self.config_path is None:
            return
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self.config_path.touch()
        self._watcher = QFileSystemWatcher([str(self.config_path)])
        self._watcher.fileChanged.connect(self._on_file_changed)

    def _pause_watcher(self) -> None:
        if self._watcher:
            try:
                self._watcher.blockSignals(True)
            except Exception:
                pass

    def _resume_watcher(self) -> None:
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
```

**使用示例**：

```python
class MyService(FileConfigService):
    def __init__(self):
        super().__init__(config_path=Path("data/config/my.json"))
        self.load()       # 首次加载
        self._start_watching()

    def _do_load(self):
        import json
        return json.loads(self.config_path.read_text("utf-8"))

    def _do_save(self, config):
        import json
        tmp = self.config_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False), "utf-8")
        tmp.replace(self.config_path)
```

## 硬约束

### 1. 文件型配置服务 MUST 使用 FileConfigService 基类

所有从磁盘文件加载配置并缓存在内存的服务 MUST 继承 `FileConfigService`（或等价实现 QObject + QFileSystemWatcher + config_changed 三板斧）。

### 2. 消费者 MUST 通过信号获取更新，禁止轮询

```python
# ✅ 正确
service.config_changed.connect(self._on_config_changed)

# ❌ 错误：仅打开时加载一次，后续外部编辑不感知
def open_dialog(self):
    service.reload()
    self._load_ui()
```

### 3. MUST NOT 绕过 Service 直接读文件

```python
# ❌ 错误
cfg = json.loads(Path("data/config/foo.json").read_text())

# ✅ 正确
cfg = service.load()
```

## 项目现状与待修复

| 服务 | 文件 | 继承 QObject | 有 watcher | 状态 |
|------|------|-------------|-----------|------|
| `LLMManagerService` | `llm_providers.json` | ✅ | ✅ | 已修复 |
| `ConfigManager` | `toolkit_config.json` | ❌ | ❌ | **待修复** |
| `MCPRegistry` | `mcp_servers.json` | ❌ | ❌ | **待修复** |
| `TokenTracker` | `llm_token_usage.db` | N/A | N/A | 无需（仅写入端） |

> `AgentConfig.load/save_config()` 是函数而非服务类，调用频次低（每次 save 时重写全量），暂不纳入。

## 检查清单

新服务或配置改造上线前 MUST 确认：

```
[ ] 继承 FileConfigService（或等价实现）
[ ] 构造函数中 config_path 已设置
[ ] 构造函数中调用 _start_watching()
[ ] 所有消费者通过 config_changed 信号连接
[ ] 没有代码绕过 Service 直接读配置文件的 Path
```

## 关联规则

- 技术选型门禁: [tech-selection-gate.md](tech-selection-gate.md)
- 代码质量门禁: [code-quality-gate.md](code-quality-gate.md)
