# Implementation Plan: 历史抓取记录查看

## 目录

- [技术上下文](#技术上下文)
- [架构设计](#架构设计)
- [数据模型](#数据模型)
- [实现阶段](#实现阶段)
- [关键决策](#关键决策)
- [风险评估](#风险评估)

**Feature Branch**: `004-history-viewer`  
**Created**: 2026-04-02  
**Spec Reference**: `spec.md`  

---

## 技术上下文

### 现有技术栈

- **GUI 框架**: PyQt6
- **数据存储**: SQLite（共享数据库 + 模块数据库）
- **配置管理**: Pydantic 模型 + JSON
- **ADB 操作**: `toolkit.core.adb_manager`
- **事件通信**: EventBus

### 依赖项

| 依赖 | 版本 | 用途 |
|-----|-----|-----|
| PyQt6 | >=6.5 | GUI 组件（QWidget, QTreeWidget, QPropertyAnimation） |
| SQLite3 | 内置 | 历史索引存储 |
| Pydantic | >=2.0 | 数据模型定义 |

### 现有代码入口

| 文件 | 说明 |
|-----|-----|
| `src/gui_tab.py` | GUI Tab 实现，需新增历史按钮和面板 |
| `src/service.py` | 业务逻辑，需新增历史扫描和索引方法 |
| `src/models.py` | 数据模型，需新增历史相关模型 |
| `data/output/trace/` | trace 会话存储目录 |

---

## 架构设计

### 组件关系

```
┌───────────────────────────────────────────────────────────────┐
│                        GUI Layer                               │
│  ┌─────────────┐     ┌──────────────────────────────────────┐ │
│  │ PerfettoTab │────▶│ HistoryPanel (QWidget, Overlay)      │ │
│  │  [📂 历史]  │     │  ├─ SearchBar                        │ │
│  └─────────────┘     │  ├─ SessionTreeWidget                │ │
│                      │  ├─ StatsFooter                      │ │
│                      │  └─ AnimationController              │ │
│                      └──────────────────────────────────────┘ │
└────────────────────────────────┬──────────────────────────────┘
                                 │ signals/slots
┌────────────────────────────────▼──────────────────────────────┐
│                      Service Layer                             │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ HistoryService                                            │ │
│  │  ├─ scan_sessions() → List[HistorySession]                │ │
│  │  ├─ get_session_traces(session_id) → List[HistoryTrace]   │ │
│  │  ├─ delete_session(session_id) → bool                     │ │
│  │  ├─ delete_trace(trace_path) → bool                       │ │
│  │  ├─ get_stats() → HistoryStats                            │ │
│  │  └─ cleanup_expired() → int                               │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────┬──────────────────────────────┘
                                 │
┌────────────────────────────────▼──────────────────────────────┐
│                      Data Layer                                │
│  ┌──────────────────────┐  ┌───────────────────────────────┐  │
│  │ SQLite (history.db)  │  │ File System                   │  │
│  │  ├─ sessions         │  │  └─ data/output/trace/        │  │
│  │  └─ traces           │  │      ├─ 20260402_201530/      │  │
│  └──────────────────────┘  │      │  └─ *.perfetto-trace   │  │
│                            │      └─ ...                    │  │
│                            └───────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

### 面板动画实现

使用 `QPropertyAnimation` 实现滑出效果：

```python
class HistoryPanel(QWidget):
    def __init__(self, parent):
        self.setFixedWidth(320)
        self.animation = QPropertyAnimation(self, b"pos")
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    
    def show_animated(self):
        # 从右侧滑入
        start_x = self.parent().width()
        end_x = self.parent().width() - 320
        self.animation.setStartValue(QPoint(start_x, 0))
        self.animation.setEndValue(QPoint(end_x, 0))
        self.show()
        self.animation.start()
```

### 遮罩层实现

```python
class OverlayMask(QWidget):
    def __init__(self, parent):
        self.setStyleSheet("background: rgba(0,0,0,0.3)")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def mousePressEvent(self, event):
        self.parent().close_history_panel()
```

---

## 数据模型

### SQLite 表结构

```sql
-- sessions 表：会话索引
CREATE TABLE IF NOT EXISTS pe_history_sessions (
    id TEXT PRIMARY KEY,
    dir_path TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,  -- ISO 8601 格式
    device_model TEXT,
    device_soc TEXT,
    trace_count INTEGER DEFAULT 0,
    total_size_bytes INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);

-- traces 表：trace 文件索引
CREATE TABLE IF NOT EXISTS pe_history_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    file_name TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    device_model TEXT,
    device_soc TEXT,
    captured_at TEXT,  -- 从文件名解析
    FOREIGN KEY (session_id) REFERENCES pe_history_sessions(id) ON DELETE CASCADE
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON pe_history_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_session_id ON pe_history_traces(session_id);
```

### Pydantic 模型

```python
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path

class HistoryTrace(BaseModel):
    id: int | None = None
    session_id: str
    file_path: Path
    file_name: str
    file_size_bytes: int
    device_model: str | None = None
    device_soc: str | None = None
    captured_at: datetime | None = None

class HistorySession(BaseModel):
    id: str
    dir_path: Path
    created_at: datetime
    device_model: str | None = None
    device_soc: str | None = None
    trace_count: int = 0
    total_size_bytes: int = 0
    traces: list[HistoryTrace] = []

class HistoryStats(BaseModel):
    total_sessions: int
    total_traces: int
    total_size_bytes: int
    oldest_session: datetime | None = None
    newest_session: datetime | None = None

class HistoryConfig(BaseModel):
    max_history_days: int = 30
    max_history_count: int = 50
    auto_cleanup_on_start: bool = True
```

---

## 实现阶段

### Phase 1: 数据层实现

1. 新建 `src/history_storage.py`：SQLite 表创建和 CRUD 操作
2. 新建 `src/history_service.py`：扫描目录、更新索引、清理过期
3. 扩展 `src/models.py`：添加历史相关 Pydantic 模型
4. 扩展 `src/config_manager.py`：添加历史配置字段

### Phase 2: GUI 组件实现

1. 新建 `src/history_panel.py`：覆盖式面板组件
   - `HistoryPanel`：主面板容器
   - `SessionTreeWidget`：会话列表树
   - `OverlayMask`：半透明遮罩
2. 扩展 `src/gui_tab.py`：添加历史按钮、集成面板

### Phase 3: 交互与动画

1. 实现面板滑出/收起动画
2. 实现会话展开/折叠
3. 实现搜索过滤
4. 实现右键上下文菜单

### Phase 4: 分析模块集成

1. 实现「分析」按钮点击事件
2. 通过 EventBus 发布 `open_trace_for_analysis` 事件
3. perfetto_analysis 模块监听事件并处理

### Phase 5: 测试与文档

1. 编写单元测试
2. 更新模块文档

---

## 关键决策

### D1: 索引更新策略

**决策**：增量更新 + 一致性校验

- 首次打开：全量扫描目录，写入 SQLite
- 后续打开：
  1. 扫描目录获取当前会话列表
  2. 对比 SQLite 索引，找出新增/删除的会话
  3. 仅处理差异部分
- 每次打开时校验：检查索引中的路径是否仍存在，清理无效条目

### D2: 与 analysis 模块的通信方式

**决策**：通过 EventBus + Tab 切换

1. capture 模块发布事件：`{"type": "open_trace_for_analysis", "trace_path": "/path/to/trace"}`
2. analysis 模块监听事件后：
   - 获取主窗口 Tab 控制器，切换到 perfetto_analysis Tab
   - 自动填入 trace 路径到输入框
   - 不自动触发分析，等待用户确认
3. 如果 analysis 模块不可用，capture 模块需：
   - 禁用「分析」按钮
   - 鼠标悬停时显示提示"perfetto_analysis 模块未加载"

### D3: 文件名解析策略

**决策**：使用正则匹配已知格式，降级为文件属性

```python
# 标准格式: trace_{model}_{soc}_{timestamp}_001.perfetto-trace
FILENAME_PATTERN = r"trace_(?P<model>\w+)_(?P<soc>\w+)_(?P<ts>\d{8}_\d{6})_\d+\.perfetto-trace"

def parse_trace_filename(filename: str) -> dict:
    match = re.match(FILENAME_PATTERN, filename)
    if match:
        return match.groupdict()
    # 降级：使用文件修改时间
    return {"model": None, "soc": None, "ts": None}
```

### D4: trace 文件操作方式

**决策**：不支持双击打开，只提供「打开目录」和「分析」按钮

- .perfetto-trace 文件无系统关联程序
- Perfetto UI 无法直接通过 URL 打开本地文件（浏览器安全限制）
- 用户可通过「打开目录」后手动拖拽到 Perfetto UI

### D5: 搜索实现

**决策**：多字段简单文本匹配

- 支持字段：设备型号、SoC、日期/时间
- 匹配方式：包含即显示（大小写不敏感）
- 使用防抖（300ms）避免频繁刷新

### D6: 空目录处理

**决策**：自动清理

- 扫描时发现空的会话目录自动删除
- 不在列表中显示无 trace 文件的会话

### D7: 自动清理时机

**决策**：应用程序启动时执行，通过 `auto_cleanup_on_start` 配置控制

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|-----|-----|---------|
| 大量历史文件导致扫描慢 | 打开面板卡顿 | 使用 SQLite 索引 + 增量更新 |
| 外部删除文件导致索引不一致 | 点击打开报错 | 每次打开校验，自动清理无效条目 |
| analysis 模块不可用 | 分析按钮无效 | 检测模块可用性，不可用时禁用按钮 |
| 遮罩层事件穿透 | 误操作主界面 | 使用 `raise_()` 确保面板在最上层 |
| 空目录占用空间 | 目录混乱 | 扫描时自动清理空目录 |
