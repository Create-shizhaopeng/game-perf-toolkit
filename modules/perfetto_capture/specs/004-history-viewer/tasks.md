# Task Breakdown: 历史抓取记录查看

## 目录

- [任务总览](#任务总览)
- [Phase 1: 数据层](#phase-1-数据层)
- [Phase 2: 服务层](#phase-2-服务层)
- [Phase 3: GUI 组件](#phase-3-gui-组件)
- [Phase 4: 集成与交互](#phase-4-集成与交互)
- [Phase 5: 测试](#phase-5-测试)

**Feature Branch**: `004-history-viewer`  
**Created**: 2026-04-02  
**Plan Reference**: `plan.md`  
**Est. Total Tasks**: 18

---

## 任务总览

```
Phase 1: 数据层          [T01-T04]  ████░░░░░░░░░░░░░░  4 tasks
Phase 2: 服务层          [T05-T08]  ████████░░░░░░░░░░  4 tasks
Phase 3: GUI 组件        [T09-T13]  ████████████░░░░░░  5 tasks
Phase 4: 集成与交互      [T14-T16]  ██████████████░░░░  3 tasks
Phase 5: 测试            [T17-T18]  ████████████████░░  2 tasks
```

---

## Phase 1: 数据层

### T01: 新增历史相关 Pydantic 模型

**文件**: `src/models.py`

**任务**:
- [ ] 添加 `HistoryTrace` 模型（file_path, file_name, file_size_bytes, device_model, device_soc, captured_at）
- [ ] 添加 `HistorySession` 模型（id, dir_path, created_at, device_model, device_soc, trace_count, total_size_bytes, traces）
- [ ] 添加 `HistoryStats` 模型（total_sessions, total_traces, total_size_bytes）
- [ ] 添加 `HistoryConfig` 模型（max_history_days, max_history_count, auto_cleanup_on_start）

**验收**: 模型类可实例化，字段类型正确

---

### T02: 新建历史存储模块

**文件**: `src/history_storage.py`（新建）

**任务**:
- [ ] 创建 `HistoryStorage` 类
- [ ] 实现 `_ensure_tables()` 方法：创建 `pe_history_sessions` 和 `pe_history_traces` 表
- [ ] 实现 `insert_session(session)` 方法
- [ ] 实现 `insert_trace(trace)` 方法
- [ ] 实现 `get_all_sessions()` 方法
- [ ] 实现 `get_traces_by_session(session_id)` 方法
- [ ] 实现 `delete_session(session_id)` 方法（级联删除 traces）
- [ ] 实现 `delete_trace(trace_id)` 方法
- [ ] 实现 `get_stats()` 方法

**依赖**: T01

**验收**: CRUD 操作单元测试通过

---

### T03: 扩展配置管理

**文件**: `src/config_manager.py`

**任务**:
- [ ] 在配置模型中添加 `history: HistoryConfig` 字段
- [ ] 设置默认值：max_history_days=30, max_history_count=50, auto_cleanup_on_start=True
- [ ] 确保 `load_config()` 和 `save_config()` 兼容新字段

**依赖**: T01

**验收**: 配置加载保存后历史配置字段不丢失

---

### T04: 实现文件名解析工具

**文件**: `src/utils.py`

**任务**:
- [ ] 添加 `parse_trace_filename(filename: str) -> dict` 函数
- [ ] 支持标准格式：`trace_{model}_{soc}_{timestamp}_001.perfetto-trace`
- [ ] 支持 legacy 格式降级（返回 None 字段）
- [ ] 添加 `parse_session_dirname(dirname: str) -> datetime | None` 函数

**验收**: 对多种格式的测试用例通过

---

## Phase 2: 服务层

### T05: 新建历史服务模块

**文件**: `src/history_service.py`（新建）

**任务**:
- [ ] 创建 `HistoryService` 类
- [ ] 注入 `HistoryStorage` 和 `output_dir` 依赖
- [ ] 实现 `scan_sessions() -> list[HistorySession]` 方法：扫描目录 + 更新索引

**依赖**: T02, T04

**验收**: 扫描包含多个会话目录的 output/trace 返回正确结果

---

### T06: 实现索引增量更新

**文件**: `src/history_service.py`

**任务**:
- [ ] 实现 `_sync_index()` 方法：
  1. 获取目录中的会话列表
  2. 对比 SQLite 索引
  3. 添加新会话、删除无效会话
- [ ] 实现 `_validate_index()` 方法：检查索引路径是否仍存在
- [ ] 实现 `_cleanup_empty_dirs()` 方法：自动清理无 trace 文件的空会话目录

**依赖**: T05

**验收**: 删除目录后重新打开，索引自动清理无效条目；空目录被自动删除

---

### T07: 实现删除功能

**文件**: `src/history_service.py`

**任务**:
- [ ] 实现 `delete_session(session_id) -> bool`：删除目录 + 更新索引
- [ ] 实现 `delete_trace(trace_path) -> bool`：删除文件 + 更新索引
- [ ] 处理删除失败的情况（权限不足等）

**依赖**: T05

**验收**: 删除后目录/文件被清理，索引更新，磁盘空间释放

---

### T08: 实现自动清理

**文件**: `src/history_service.py`

**任务**:
- [ ] 实现 `cleanup_expired() -> int`：根据配置清理过期会话
- [ ] 支持按天数清理（max_history_days）
- [ ] 支持按数量清理（max_history_count，保留最新 N 个）
- [ ] 返回清理的会话数

**依赖**: T05, T03

**验收**: 配置 max_history_count=5，存在 10 个会话时清理掉最旧的 5 个

---

## Phase 3: GUI 组件

### T09: 创建历史面板容器

**文件**: `src/history_panel.py`（新建）

**任务**:
- [ ] 创建 `HistoryPanel(QWidget)` 类
- [ ] 设置固定宽度 320px
- [ ] 添加标题栏（标题 + 刷新按钮 + 关闭按钮）
- [ ] 添加搜索框 `QLineEdit`
- [ ] 添加会话树 `QTreeWidget` 占位
- [ ] 添加底部统计栏（总大小、会话数、清理按钮）
- [ ] 应用 Catppuccin 主题样式

**依赖**: 无

**验收**: 面板组件可独立渲染，样式与主界面一致

---

### T10: 创建遮罩层组件

**文件**: `src/history_panel.py`

**任务**:
- [ ] 创建 `OverlayMask(QWidget)` 类
- [ ] 设置半透明背景 `rgba(0,0,0,0.3)`
- [ ] 实现 `mousePressEvent` 关闭面板
- [ ] 随父组件大小自动调整

**依赖**: T09

**验收**: 点击遮罩区域触发关闭信号

---

### T11: 实现面板动画

**文件**: `src/history_panel.py`

**任务**:
- [ ] 使用 `QPropertyAnimation` 实现滑出动画
- [ ] 动画时长 250ms，缓动曲线 OutCubic
- [ ] 实现 `show_animated()` 方法：从右侧滑入
- [ ] 实现 `hide_animated()` 方法：向右侧滑出
- [ ] 动画结束后调用 `hide()` 释放资源

**依赖**: T09

**验收**: 打开/关闭面板有平滑动画效果

---

### T12: 实现会话树组件

**文件**: `src/history_panel.py`

**任务**:
- [ ] 实现 `SessionTreeWidget(QTreeWidget)` 类
- [ ] 会话节点显示：时间、设备、trace 数、大小
- [ ] 会话节点附带操作按钮：打开目录、删除会话
- [ ] trace 子节点显示：文件名、大小
- [ ] trace 节点附带操作按钮：打开目录、分析、删除（不支持双击打开）
- [ ] 实现展开/折叠交互
- [ ] 实现 `refresh(sessions: list[HistorySession])` 方法

**依赖**: T09

**验收**: 传入会话数据正确渲染树形结构

---

### T13: 实现搜索过滤

**文件**: `src/history_panel.py`

**任务**:
- [ ] 搜索框输入变化时过滤会话列表
- [ ] 支持按设备型号、SoC、日期搜索
- [ ] 无匹配结果时显示提示文本
- [ ] 使用防抖（300ms）避免频繁刷新

**依赖**: T12

**验收**: 输入关键词后列表正确过滤

---

## Phase 4: 集成与交互

### T14: 集成历史面板到 GUI Tab

**文件**: `src/gui_tab.py`

**任务**:
- [ ] 在底部按钮行添加「📂 历史」按钮
- [ ] 创建 `HistoryPanel` 实例（延迟初始化）
- [ ] 创建 `OverlayMask` 实例
- [ ] 实现 `_toggle_history_panel()` 方法
- [ ] 实现 `_close_history_panel()` 方法
- [ ] 处理 Esc 键关闭面板

**依赖**: T09, T10, T11, T12

**验收**: 点击历史按钮打开面板，点击遮罩/关闭按钮/Esc 关闭面板

---

### T15: 连接服务层数据

**文件**: `src/gui_tab.py`, `src/history_panel.py`

**任务**:
- [ ] 面板打开时调用 `HistoryService.scan_sessions()`
- [ ] 将结果传递给 `SessionTreeWidget.refresh()`
- [ ] 实现刷新按钮点击事件
- [ ] 实现删除操作（弹窗确认对话框 + 调用服务）
- [ ] 实现打开目录操作（`QDesktopServices.openUrl`，文件级别选中该文件）
- [ ] 实现清理按钮点击事件
- [ ] 实现应用启动时自动清理（配置 auto_cleanup_on_start）

**依赖**: T05-T08, T14

**验收**: 面板显示真实历史数据，操作生效

---

### T16: 实现分析模块联动

**文件**: `src/gui_tab.py`

**任务**:
- [ ] 检测 perfetto_analysis 模块是否可用
- [ ] 分析按钮不可用时禁用并显示提示
- [ ] 实现「分析」按钮点击：发布 EventBus 事件
- [ ] 事件格式：`{"type": "open_trace_for_analysis", "trace_path": str}`

**依赖**: T14

**验收**: 点击分析按钮后切换到 analysis Tab 并填入路径

---

## Phase 5: 测试

### T17: 数据层单元测试

**文件**: `tests/test_history_storage.py`（新建）

**任务**:
- [ ] 测试 `HistoryStorage` CRUD 操作
- [ ] 测试 `parse_trace_filename()` 多种格式
- [ ] 测试 `parse_session_dirname()` 解析

**依赖**: T01-T04

---

### T18: 服务层单元测试

**文件**: `tests/test_history_service.py`（新建）

**任务**:
- [ ] 测试 `scan_sessions()` 扫描结果
- [ ] 测试索引增量更新
- [ ] 测试 `cleanup_expired()` 清理逻辑
- [ ] 测试删除功能

**依赖**: T05-T08

---

## 任务依赖图

```
T01 ─┬─▶ T02 ─┬─▶ T05 ─┬─▶ T06 ─▶ T07 ─▶ T08
     │        │        │
     └─▶ T03  └─▶ T04  └─────────────────────┐
                                              │
T09 ─▶ T10 ─▶ T11                            │
  │                                           │
  └─▶ T12 ─▶ T13                             │
                                              │
T14 ◀─────────────────────────────────────────┘
  │
  └─▶ T15 ─▶ T16
                │
T17 ◀───────────┘
  │
  └─▶ T18
```
