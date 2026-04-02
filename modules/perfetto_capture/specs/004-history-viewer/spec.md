# Feature Specification: 历史抓取记录查看

**Feature Branch**: `004-history-viewer`  
**Spec Location**: `modules/perfetto_capture/specs/004-history-viewer/`  
**Created**: 2026-04-02  
**Status**: Draft  
**Input**: 支持查看和管理历史抓取的 trace 文件

## 目录

- [背景与动机](#背景与动机)
- [User Scenarios & Testing](#user-scenarios--testing)
- [Requirements](#requirements)
- [Clarifications](#clarifications)
- [Success Criteria](#success-criteria)

## 背景与动机

当前 perfetto_capture 模块支持抓取 trace 并导出到本地目录，但缺少查看历史抓取记录的入口。用户需要手动定位文件夹才能找到之前的 trace 文件。

本需求旨在提供一个便捷的历史记录查看界面，让用户能够：
1. 浏览所有历史抓取会话
2. 查看每个会话中的 trace 文件列表
3. 快速打开 trace 文件或其所在目录
4. 清理过期的历史记录

## User Scenarios & Testing

### User Story 1 — 浏览历史抓取会话 (Priority: P1)

作为测试工程师，我希望在 GUI 中查看所有历史抓取会话，以便快速找到之前的 trace 文件。

**Why this priority**: 核心功能，解决用户无法快速定位历史 trace 的痛点

**Independent Test**: 打开历史记录面板，确认能看到所有历史会话列表

**Acceptance Scenarios**:

1. **Given** 存在多个历史抓取会话, **When** 打开历史记录面板, **Then** 按时间倒序显示所有会话
2. **Given** 每个会话, **When** 展示时, **Then** 显示会话时间、设备信息、trace 数量
3. **Given** 无历史记录, **When** 打开历史记录面板, **Then** 显示「暂无历史记录」提示

---

### User Story 2 — 查看会话详情 (Priority: P1)

作为测试工程师，我希望能展开某个会话查看其中包含的所有 trace 文件。

**Independent Test**: 点击展开某个会话，确认能看到该会话下的所有 trace 文件

**Acceptance Scenarios**:

1. **Given** 一个包含多个 trace 的会话, **When** 点击展开, **Then** 显示每个 trace 的文件名和大小
2. **Given** trace 文件, **When** 点击「打开目录」, **Then** 使用文件管理器打开文件所在目录
3. **Given** trace 文件, **When** 点击「分析」, **Then** 联动 perfetto_analysis 模块进行分析

---

### User Story 3 — 打开目录或分析 trace (Priority: P1)

作为测试工程师，我希望能快速打开 trace 所在目录或直接分析 trace。

**Acceptance Scenarios**:

1. **Given** 选中一个 trace, **When** 点击「打开目录」, **Then** 使用文件管理器打开文件所在目录并选中该文件
2. **Given** 选中一个会话, **When** 点击「打开目录」, **Then** 使用文件管理器打开会话目录
3. **Given** 选中一个 trace, **When** 点击「分析」, **Then** 联动 perfetto_analysis 模块分析该 trace
4. **Given** 文件已被外部删除, **When** 尝试操作, **Then** 显示文件不存在提示并自动刷新列表

---

### User Story 4 — 清理历史记录 (Priority: P2)

作为测试工程师，我希望能清理过期的历史记录以释放磁盘空间。

**Acceptance Scenarios**:

1. **Given** 选中一个或多个会话, **When** 点击「删除」, **Then** 确认后删除会话目录及其中的 trace 文件
2. **Given** 配置了自动清理策略, **When** 超过保留份数/时长, **Then** 自动清理最旧的会话
3. **Given** 删除操作, **When** 确认删除, **Then** 从列表中移除并更新磁盘占用统计

---

### Edge Cases

- 会话目录被外部删除时，刷新列表应自动移除无效条目
- 多个同名设备的会话应能通过时间戳区分
- 大量历史记录时列表应支持滚动且性能良好

## Requirements

### Functional Requirements

#### 数据扫描与索引

- **FR-001**: 系统 MUST 在打开历史面板时扫描 `output_dir/trace/` 目录，发现所有会话目录
- **FR-002**: 系统 MUST 解析会话目录名（格式：`YYYYMMDD_HHMMSS`）提取时间信息
- **FR-003**: 系统 MUST 扫描每个会话目录中的 `.perfetto-trace` 文件，提取文件名、大小、设备信息

#### 界面展示

- **FR-004**: 系统 MUST 提供「📂 历史记录」按钮/入口，打开历史面板
- **FR-005**: 历史面板 MUST 显示会话列表，包含：会话时间、设备型号、trace 数量、总大小
- **FR-006**: 系统 MUST 支持展开会话查看其中的 trace 文件列表
- **FR-007**: 系统 MUST 支持对 trace 文件的操作：打开目录、分析、删除
- **FR-008**: 系统 SHOULD 显示磁盘占用统计（总大小、文件数量）

#### 清理策略

- **FR-009**: 系统 SHOULD 支持配置自动清理策略：
  - `max_history_days`: 保留天数（默认 30 天）
  - `max_history_count`: 最大保留会话数（默认 50）
- **FR-010**: 系统 SHOULD 在启动时自动执行清理策略
- **FR-011**: 系统 MUST 支持手动删除单个会话

### Key Entities

- **HistorySession**: 历史会话数据结构（时间、目录路径、trace 列表）
- **HistoryTrace**: trace 文件数据结构（文件名、路径、大小、设备信息）
- **HistoryConfig**: 历史记录配置（清理策略参数）

### UI Layout

历史面板作为模态对话框或侧边面板，包含：
- 顶部：标题 + 刷新按钮 + 关闭按钮
- 中部：会话列表（可展开的树形结构）
- 底部：磁盘占用统计 + 清理按钮

## Clarifications

### C1: 历史面板入口位置

**问题**：历史记录入口放在哪里？
**决策**：在当前 Tab 底部按钮行增加「📂 历史记录」按钮（与开始/保存/停止并排）

### C2: 与 perfetto_analysis 集成

**问题**：是否支持从历史面板直接触发分析？
**决策**：增加「📊 分析」按钮，联动 perfetto_analysis 模块

### C3: 索引持久化

**问题**：是否将历史索引持久化到数据库？
**决策**：索引持久化到 SQLite，增量更新（性能更好）

### C4: 面板交互方式

**问题**：历史面板如何展示？
**决策**：使用**覆盖式（Overlay）右侧滑出面板**
- 面板从右侧滑出，浮在主界面上方
- 主界面布局**不发生任何变形**
- 面板带半透明遮罩，点击遮罩可关闭面板
- 宽度固定 320px

### C5: trace 文件打开方式

**问题**：双击 trace 文件使用什么方式打开？
**决策**：**不支持双击打开**，原因是 .perfetto-trace 文件无系统关联程序，且 Perfetto UI 无法直接通过 URL 打开本地文件（浏览器安全限制）
- 只提供两个按钮：「📂 打开目录」和「📊 分析」
- 用户可在文件管理器中拖拽文件到 Perfetto UI

### C6: 搜索功能范围

**问题**：搜索功能支持哪些字段？
**决策**：支持多字段搜索，包括：
- 设备型号
- SoC 型号
- 日期/时间
- 简单文本匹配（包含即显示）

### C7: 自动清理触发时机

**问题**：自动清理策略何时执行？
**决策**：应用程序启动时执行自动清理

### C8: 抓取中是否允许打开历史面板

**问题**：正在抓取 trace 时是否允许打开历史记录面板？
**决策**：**允许**，可以边抓取边浏览历史记录

### C9: 删除确认方式

**问题**：删除会话/trace 时如何确认？
**决策**：弹窗确认对话框，显示将删除的会话/文件信息和大小

### C10: 刷新时机

**问题**：历史记录列表何时刷新？
**决策**：
- 打开面板时自动刷新
- 提供手动刷新按钮

### C11: 空会话目录处理

**问题**：如果会话目录存在但没有 .perfetto-trace 文件如何处理？
**决策**：自动清理空目录，不在列表中显示

## Success Criteria

### Measurable Outcomes

- **SC-001**: 历史面板在 500ms 内完成加载（≤100 个会话）
- **SC-002**: 用户可在 3 次点击内分析或打开任意历史 trace 所在目录
- **SC-003**: 自动清理功能正确删除超期会话，保留最新的 N 个
- **SC-004**: 删除操作正确清理磁盘空间，无残留文件
