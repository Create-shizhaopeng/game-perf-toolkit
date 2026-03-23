# UI Design: Perfetto 解析分析模块

## 目录

- [设计约束](#设计约束)
- [已选定布局（左右分栏）](#已选定布局左右分栏)
  - [左侧面板](#左侧面板)
  - [右侧面板](#右侧面板)
- [通用组件](#通用组件)
- [交互流程](#交互流程)
- [版本变更记录](#版本变更记录)

**Created**: 2026-03-23
**Last Updated**: 2026-03-23
**Design Style**: 与主框架 VS Code 风格一致（Catppuccin Mocha/Latte 主题），与 perfetto_capture / game_perf 风格统一
**选定方案**: **左右分栏** — 左侧固定宽度（配置+控制+历史），右侧自适应（结果+日志）

---

## 设计约束

1. 模块 Tab 嵌入 MainWindow 右侧内容区（QStackedWidget），与其他模块平级
2. 风格与主框架一致（QSS 深色/浅色主题）
3. 不可修改主框架代码
4. 需容纳：Trace 文件选择、目标进程配置、分析模式选择、维度选择、分析进度/控制、结果预览、分析历史管理、操作日志
5. 分析为耗时操作（可能数分钟），需通过 QThread 后台执行，GUI 实时展示进度

---

## 已选定布局（左右分栏）

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         Perfetto 解析分析                                   │
├──────────────────────────────┬─────────────────────────────────────────────┤
│  左侧 (固定 580px)           │  右侧 (自适应宽度)                           │
│                              │                                             │
│  📁 Trace 文件               │  📋 分析结果（分析完成后显示）                  │
│  [____trace.perfetto__][浏览] │  ┌─────────────────────────────────────┐    │
│                              │  │ 目标进程: com.tencent.xxx            │    │
│  ⚙ 分析配置                  │  │ 报告路径: data/output/trace_report/  │    │
│  目标进程 [___com.xxx___]     │  │ 丢帧次数: 12  | 总帧: 8450          │    │
│  App类型[▼auto]              │  │ 刷新率: 120Hz | 类型: game          │    │
│  分析模式[▼完整] [全部维度▾]   │  │ 分析耗时: 45.2s                     │    │
│                              │  │ 维度完成: cpu, thread, binder ...    │    │
│  ● 就绪 [▶开始分析] [⏹停止]   │  └─────────────────────────────────────┘    │
│  ████████████░░░░░░          │                                             │
│  Phase 2: cpu 维度...        │                                             │
│                              │                                             │
│  📜 分析历史                  │            (stretch 留白)                    │
│  ┌────┬────┬──┬────┬─┬───┐  │                                             │
│  │Trace│进程│模式│时间│状态│操作│  │  ─────────────────────────────────────── │
│  ├────┼────┼──┼────┼─┼───┤  │  📋 操作日志 (固定高度 150px)               │
│  │PD24│xxx │完整│09:30│✅ │🔄📄📁🗑│  │  [09:35:12] ✓ Phase 1 完成               │
│  │TB52│yyy │维度│15:30│✅ │🔄📄📁🗑│  │  [09:35:15] → Phase 2: cpu...            │
│  └────┴────┴──┴────┴─┴───┘  │  [09:35:22] ✓ 报告已生成                    │
└──────────────────────────────┴─────────────────────────────────────────────┘
```

### 左侧面板

固定宽度 `580px`（`_LEFT_PANEL_W` 常量），不随窗口缩放变化。QSplitter 的 `stretchFactor(0)` 设为 0，仅右侧面板自适应。

**1. Trace 文件选择区**（QGroupBox "Trace 文件"）
- QLineEdit（固定 320px） + QPushButton("浏览", 60px)
- 支持拖拽 `.perfetto-trace`、`.perfetto` 文件
- 文本变更时自动更新 tooltip 显示完整路径

**2. 分析配置区**（QGroupBox "分析配置"）
- Row 1: 目标进程 QLineEdit（固定 240px，placeholder "留空自动识别"）
- Row 2: App 类型 QComboBox（100px, auto/app/game/camera）→ 分析模式 QComboBox（100px, 完整分析/仅解析/独立维度）→ 维度多选 _DimensionSelector（120px, 仅"独立维度"模式可见）
- 已移除: ~~Top N QSpinBox~~、~~Binder 阈值 QDoubleSpinBox~~、~~调度延迟 QDoubleSpinBox~~（使用 config.json 默认值）

**3. 控制区**（位于配置区与历史区之间）
- 状态指示 QLabel（"● 就绪" / "● 分析中..."）
- 开始分析 QPushButton（100px, SP_MediaPlay 图标）
- 停止 QPushButton（100px, SP_MediaStop 图标）
- 进度条 QProgressBar（不确定模式，分析中可见）
- 进度文字 QLabel（阶段提示）

**4. 分析历史区**（QLabel "📜 分析历史" + QTableWidget）
- 6 列固定宽度表格，不随窗口缩放：

| 列 | 宽度 | 说明 |
|----|------|------|
| Trace | 140px | 文件名，超出部分 tooltip 显示 |
| 目标进程 | 120px | 分析结束后自动填充检测到的进程名 |
| 模式 | 60px | 完整/仅解析/独立维度，独立维度 tooltip 显示具体维度 |
| 时间 | 80px | MM-DD HH:MM 格式 |
| 状态 | 36px | ✅（报告存在）/ ⚠（目录存在无报告）/ —（无） |
| 操作 | 120px | 4 个操作按钮（见下方说明） |

**操作按钮**（每个 26×22px）：
- 🔄 **重新生成**: 从数据库中已有数据重新生成 Markdown 报告（不重新分析 trace）。trace 文件不存在时禁用。
- 📄 **打开报告**: 打开 `jank_report.md` 文件。报告不存在时禁用。
- 📁 **打开目录**: 打开报告所在目录。目录不存在时禁用。
- 🗑 **删除**: 删除该条分析记录。红色样式，hover 时白底红字。仅删除当前记录，若同一 trace 无其他模式记录则同时清理磁盘文件和模块数据库。

**历史数据来源**：
- 优先从共享 DB `pa_analysis_tasks` 读取
- 同时扫描 `output/trace_report/` 磁盘目录，补充未入库的历史报告
- 去重策略：trace_path + mode 组合唯一

### 右侧面板

自适应宽度（QSplitter stretchFactor=1）。

**1. 分析结果预览区**（QGroupBox "分析结果"，分析完成后显示）
- 只读 QTextEdit 显示：
  - 目标进程（自动检测的进程名）
  - 报告路径
  - 丢帧概览：jank_times / frame_num / refresh_rate_hz / app_type / elapsed_seconds
  - 维度分析状态：已完成/已跳过的维度列表

**2. 操作日志区**（固定高度 150px，底部吸附）
- QLabel "📋 操作日志" + QTextEdit (readonly, font-size 11px)
- 与左侧历史区底部视觉对齐

---

## 通用组件

### _DimensionSelector（维度多选控件）

- 继承 QPushButton（非 QComboBox，避免 Windows COM 线程问题导致崩溃）
- 点击弹出 `_PersistentMenu`（QMenu 子类，点击可勾选项后不自动关闭）
- 10 个维度：CPU / 线程 / Binder / IO / GC / GPU / SF / Input / Lock / 整体
- 按钮文字动态更新："全部维度 ▾" / "N 个维度 ▾" / "未选维度 ▾"
- 菜单底部含"全选" / "全不选"快捷操作
- 仅在分析模式为"独立维度"时可见

### _AnalysisWorker（后台分析线程）

- 继承 QThread，通过 `pyqtSignal` 通信
- progress / finished / error 三个信号
- 支持 abort() 安全中止（在 on_progress 回调中检查 _abort 标志）
- 中止后已完成的 Phase 1 数据保留在 DB 中

### 文件拖拽

- Tab 级 dragEnterEvent / dropEvent 支持
- 自动填入文件路径到输入框

---

## 交互流程

### 分析流程

```
用户选择 trace → 配置参数 → 点击"开始分析"
  → 按钮禁用 + 进度条启动 + 状态切换为"● 分析中..."
  → QThread 调用 service.analyze/parse_only/analyze_dimensions
  → progress signal 更新进度文字和操作日志
  → 完成 → 结果预览区展开，显示概览
  → 分析历史自动刷新，显示新记录
```

### 停止流程

```
用户点击"停止"
  → 设置 _abort 标志
  → QThread 在 on_progress 回调中检查并抛出 _AbortedError
  → 已完成的 Phase 1 结果保留
  → 状态回到"● 就绪"
```

### 重新生成报告流程

```
用户在历史中点击 🔄 或双击行
  → 调用 service.regenerate_report(trace_path)
  → 从模块数据库读取已有分析数据（trace_run, trace_summary, jank_record）
  → 使用 export 模块重新生成 Markdown 报告
  → 历史列表刷新
```

### 删除记录流程

```
用户点击 🗑 删除按钮
  → 调用 service.delete_analysis_record(task_id, trace_path, report_dir)
  → 仅删除该条 task_id 对应的共享 DB 记录
  → 检查同一 trace_path 是否还有其他模式记录：
    - 有其他记录 → 仅删除 DB 记录，保留磁盘文件
    - 无其他记录 → 同时清理模块 DB 数据和磁盘文件
  → 使用 QTimer.singleShot(100ms) 延迟刷新历史（避免 UI 竞态）
```

---

## 版本变更记录

| 日期 | 变更内容 |
|------|---------|
| 2026-03-23 | 初始设计：左右分栏布局 |
| 2026-03-23 | 移除右侧"报告文件"区，打开报告功能集成到左侧历史操作列 |
| 2026-03-23 | 控制区（开始/停止按钮）从底部移至配置与历史之间 |
| 2026-03-23 | 移除 Top N / Binder 阈值 / 调度延迟配置项（使用默认值） |
| 2026-03-23 | 历史表增加"目标进程"和"模式"列，共 6 列 |
| 2026-03-23 | 维度选择器从 QComboBox 改为 QPushButton + _PersistentMenu（修复 Windows 崩溃） |
| 2026-03-23 | 左侧面板固定宽度 580px，不随窗口缩放 |
| 2026-03-23 | 历史操作增加"重新生成"（基于 DB 数据）和"删除"（智能清理） |
