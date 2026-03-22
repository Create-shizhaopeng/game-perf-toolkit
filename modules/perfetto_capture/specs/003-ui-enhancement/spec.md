# 003-ui-enhancement: GUI 界面增强

## 目录

- [背景与动机](#背景与动机)
- [功能需求](#功能需求)
  - [FR-001: SpinBox 与配置行布局](#fr-001-spinbox-与配置行布局)
  - [FR-002: 手动 Buffer 与 Ftrace 开关同行](#fr-002-手动-buffer-与-ftrace-开关同行)
  - [FR-003: FlowWidget 分类与事件列表](#fr-003-flowwidget-分类与事件列表)
  - [FR-004: 配置导入按钮](#fr-004-配置导入按钮)
  - [FR-005: Ftrace Events 面板](#fr-005-ftrace-events-面板)
  - [FR-006: 底部固定栏](#fr-006-底部固定栏)
  - [FR-007: 停止时自动打开文件夹](#fr-007-停止时自动打开文件夹)
  - [FR-008: 断线重连与放弃会话](#fr-008-断线重连与放弃会话)
  - [FR-009: 抓取前陈旧会话清理](#fr-009-抓取前陈旧会话清理)
- [影响范围](#影响范围)
- [验收标准](#验收标准)

## Clarifications

### C-001: 配置导入交互方式 (2026-03-22)

**问题**：FR-004 原定义为"打开 data/ 目录让用户手动编辑"，用户实际需要的是"弹出文件选择对话框选择配置文件导入"。

**决策**：改用 `QFileDialog.getOpenFileName`，默认目录指向模块 `data/` 路径，筛选 `*.json`。选择后自动加载配置到 GUI，取消则不操作。

### C-002: Ftrace 可选事件来源 (2026-03-22)

**问题**：FR-005 原为 GUI 硬编码常见 ftrace 事件列表，用户要求从配置文件读取。

**决策**：在 `AdvancedConfig` 模型中新增 `available_ftrace_events: list[str]` 字段，默认值包含 16 个常见事件。GUI 从此字段渲染可选列表。用户可通过编辑配置文件增删可选事件。导入配置时动态重建 Ftrace 面板。

## 背景与动机

用户在验证 perfetto_capture 模块时反馈了多项 UI/UX 改进需求，
涉及输入框样式、配置便捷性、ftrace 可见性、导出体验，以及抓取中的断线恢复与引擎侧会话清理的配合展示。

## 功能需求

### FR-001: SpinBox 与配置行布局

- **Duration**、**Buffer**、**导入配置**控件置于**同一行**，各自使用**固定宽度**，避免窗口缩放时错位拥挤
- Duration 和 Buffer 两个 SpinBox 视觉宽度一致
- 单位文本 (s / KB) 放在输入框**外部**（作为 QLabel），而非 suffix
- 数值调整的上下箭头必须**清晰可见**

### FR-002: 手动 Buffer 与 Ftrace 开关同行

- 「手动设置 Buffer」与「启用 Ftrace 自定义」两个复选框置于**同一行**，与配置行区分清晰

### FR-003: FlowWidget 分类与事件列表

- **Atrace Categories** 与 **Ftrace Events** 勾选区域使用 `FlowWidget`（流式布局），列数随可用宽度自动换行
- 宽屏多列、窄屏少列，避免横向滚动条难以操作

### FR-004: 配置导入按钮

- 配置行内提供「📂 导入配置」按钮（与 Duration/Buffer 同行）
- 点击后弹出 **`QFileDialog` 文件选择对话框**，默认目录指向模块 `data/` 配置路径，筛选 `*.json`
- 用户选择 JSON 文件后自动加载到 GUI（Duration、Buffer、Atrace、Ftrace 等全部刷新）
- 取消选择不执行任何操作

### FR-005: Ftrace Events 面板

- 在 Atrace Categories 区域**下方**提供 Ftrace Events 面板
- 默认**隐藏**
- 「启用 Ftrace 自定义」勾选时面板**可见**；未勾选时面板隐藏
- 面板内的可选 ftrace 事件列表从配置文件 **`advanced.available_ftrace_events`** 读取（而非 GUI 硬编码）
- 配置文件默认包含 16 个常见事件（sched/sched_switch、power/cpu_frequency 等）
- 用户可通过编辑配置文件增删可选事件，导入配置后 Ftrace 面板动态重建
- 勾选结果写入 `advanced.ftrace_events` 配置

### FR-006: 底部固定栏

- **状态面板**、**开始/保存/停止等按钮**、**操作日志**固定在 Tab **底部**，**不参与**上方配置区的滚动
- 上方为可滚动区域：抓取配置、Categories、Ftrace（若展开）等
- 日志与按钮始终可见，避免长列表把控制区顶出视口

### FR-007: 停止时自动打开文件夹

- 点击「停止」并完成导出后，自动打开 trace **导出所在文件夹**
- 使用系统默认文件管理器打开
- 仅在有导出文件时打开（无文件时不打开空目录）

### FR-008: 断线重连与放弃会话

- **检测**：抓取过程中设备列表变为空（如 `on_devices_changed([])`），或 ADB 操作抛出 `DeviceUnavailableError`
- **状态**：显示「🟡 等待重连」；**禁用**保存、停止；显示「❌ 放弃会话」按钮
- **重连**：依赖全局 `DeviceMonitor` 轮询（约 2s）；恢复后由后台 worker 以 **reconnect** 动作在设备上重新拉起 perfetto，延续会话逻辑
- **放弃**：`session_abandon()` 无导出地清理会话状态
- **放弃后且无设备**：状态显示「🔴 设备断开」，**不得**显示「🟢 就绪」

### FR-009: 抓取前陈旧会话清理

- 引擎在**每次开始新 trace 前**调用 `cleanup_stale_sessions()`，在设备上执行 `pkill -f perfetto`（或等价策略），清理残留 perfetto 进程
- 用于避免设备端报错「Too many concurrent tracing sessions」
- GUI 无需单独按钮；若清理失败应在日志中可见

## 影响范围

| 文件 | 变更类型 |
|------|---------|
| `gui_tab.py` | 布局重构、FlowWidget、底栏固定、断线 UI |
| `styles.py` | SpinBox 箭头样式修复 |
| `service.py` | 断线重连、放弃会话、陈旧清理（与 UI 信号配合） |
| `ui-design.md` | 更新为单栏布局示意图 |

## 验收标准

| ID | 验收标准 | 通过条件 |
|----|---------|---------|
| AC-01 | Duration/Buffer/导入同一行 | 三者固定宽度、同一行对齐 |
| AC-02 | 单位在输入框外 | "s" 和 "KB" 作为 QLabel 显示在 SpinBox 右侧 |
| AC-03 | 调整箭头可见 | 上下箭头颜色与背景有明显对比 |
| AC-04 | 手动与 Ftrace 开关同行 | 两个复选框同一行 |
| AC-05 | FlowWidget 自适应 | 窗口变窄时标签自动换行 |
| AC-06 | 导入弹出文件对话框 | 点击后弹出 QFileDialog，默认指向 data/ 目录，筛选 *.json |
| AC-06a | 导入后刷新全部配置 | 选择 JSON 后 Duration/Buffer/Atrace/Ftrace 全部刷新 |
| AC-07 | Ftrace 默认隐藏 | 初始不可见；勾选「启用 Ftrace 自定义」后显示 |
| AC-07a | Ftrace 选项配置化 | Ftrace 可选事件从 advanced.available_ftrace_events 读取，非硬编码 |
| AC-07b | Ftrace 动态重建 | 导入含不同 available_ftrace_events 的配置后面板动态重建 |
| AC-08 | 底栏固定 | 配置区可滚动，状态+按钮+日志始终在底部可见 |
| AC-09 | 停止后打开文件夹 | 有导出文件时自动打开文件管理器 |
| AC-10 | 断线 UI | 断线时等待重连、禁用保存/停止、可放弃会话 |
| AC-11 | 放弃后无设备文案 | 无设备且已放弃时显示设备断开，非就绪 |
| AC-12 | 陈旧会话清理 | 连续多次开始抓取不因并发会话数报错 |
