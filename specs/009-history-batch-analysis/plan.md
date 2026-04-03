# Implementation Plan: 历史面板批量操作与 Perfetto AI 分析接入

**Branch**: `009-history-batch-analysis` | **Date**: 2026-04-03 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/009-history-batch-analysis/spec.md`

## 目录

- [Summary](#summary)
- [Technical Context](#technical-context)
- [Constitution Check](#constitution-check)
- [Project Structure](#project-structure)
- [Implementation Phases](#implementation-phases)
  - [Phase A — 历史面板 UI 重构](#phase-a--历史面板-ui-重构)
  - [Phase B — Pydantic AI 多 Agent 引擎](#phase-b--pydantic-ai-多-agent-引擎)
  - [Phase C — 对话式分析集成](#phase-c--对话式分析集成)
  - [Phase D — 批量分析与报告系统](#phase-d--批量分析与报告系统)
  - [Phase E — 数据管理与收尾](#phase-e--数据管理与收尾)
- [Complexity Tracking](#complexity-tracking)

## Summary

将历史面板从单列管理升级为**左右双栏分析管理中心**（左栏：trace 管理 + 分析历史；右栏：AI 对话），引入 **Pydantic AI** 框架构建 Main/Sub/Review 三角色多 Agent 编排引擎，通过 LLM 驱动 Perfetto trace 分析，生成 HTML 报告供浏览器查看。同时移除现有的 Perfetto 分析 tab，统一分析入口到历史面板。

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: PyQt6, Pydantic AI (pydantic-ai), pydantic-ai-litellm, LiteLLM, Jinja2  
**Storage**: SQLite (history.db 扩展) + JSON (config.json) + 文件系统 (报告/原始数据)  
**Testing**: pytest, unittest.mock  
**Target Platform**: Windows 桌面 (PyInstaller 打包)  
**Project Type**: desktop-app (PyQt6 + pluggy 插件架构)  
**Performance Goals**: 首 token 延迟 <500ms, 单次分析超时 5 分钟  
**Constraints**: GUI 后台线程通过 pyqtSignal 通信; 分析 Agent 上下文隔离; 全局 token 预算控制  
**Scale/Scope**: 同时管理数百个 trace 文件, 批量分析最多 ~20 个 trace

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 状态 | 说明 |
|---|---|---|
| I. Plugin-First | ✅ PASS | 分析引擎作为 perfetto_analysis 模块的扩展，UI 变更在 perfetto_capture 模块内 |
| II. Three-Surface Unity | ✅ PASS | 分析逻辑通过 service 层暴露，GUI/CLI/Agent 三端可用 |
| III. Agent-Driven Design | ✅ PASS | 核心功能就是 Agent 驱动分析 |
| IV. Dependency Inversion | ✅ PASS | 模块通过 `context` 字典和 EventBus 交互 |
| V. Presentation Separation | ✅ PASS | 分析引擎在 service 层，对话 UI 在 gui_tab.py |
| VI. Open-Closed | ⚠️ WARN | 移除 PerfettoAnalysisTab 需修改 plugin.py 的 `register_gui_tab` 钩子 |
| VII. Spec-Driven | ✅ PASS | 遵循 speckit 完整工作流 |

**WARN 说明**: 移除 `register_gui_tab` 是模块内部变更（修改 plugin.py 返回 None 或空），不涉及核心框架修改，符合 Open-Closed 原则。

## Project Structure

### Documentation (this feature)

```text
specs/009-history-batch-analysis/
├── spec.md
├── plan.md              # 本文件
├── research.md          # Pydantic AI 集成研究
├── data-model.md        # 数据模型设计
├── checklists/
│   └── requirements.md
└── tasks.md             # 后续由 speckit-tasks 生成
```

### Source Code (变更范围)

```text
# === perfetto_capture 模块 (主要 UI 变更) ===
modules/perfetto_capture/src/
├── history_panel.py      # 重构：左右双栏布局
├── analysis_chat.py      # 新增：右栏对话组件
├── drag_drop_area.py     # 新增：拖入区域组件
├── models.py             # 扩展：HistoryTrace 增加分析状态字段
├── history_storage.py    # 扩展：分析任务存储
└── gui_tab.py            # 修改：集成新历史面板

# === perfetto_analysis 模块 (Agent 引擎 + 架构调整) ===
modules/perfetto_analysis/src/
├── agent/                # 新增目录：多 Agent 引擎
│   ├── __init__.py
│   ├── orchestrator.py   # AnalysisOrchestrator（编排器）
│   ├── agents.py         # MainAgent / SubAgent / ReviewAgent 定义
│   ├── tools.py          # pa_* 工具注册为 Pydantic AI 工具
│   ├── prompts.py        # Agent system prompts（加载 SOP）
│   └── report.py         # HTML 报告生成（Jinja2）
├── plugin.py             # 修改：移除 register_gui_tab，注册 agent 编排器
├── service.py            # 保持不变（Agent 工具的底层支撑）
└── templates/            # 新增：HTML 报告模板
    └── report.html

# === perfetto_analysis 数据 ===
modules/perfetto_analysis/data/
├── package_mappings.json  # 包名数据库
└── analysis_config.json   # 分析配置

# === 框架层 (最小修改) ===
toolkit/gui/main_window.py  # 修改：EventBus 监听 open_trace_for_analysis
```

**Structure Decision**: 遵循 Plugin-First 原则，UI 变更在 perfetto_capture 模块，Agent 引擎在 perfetto_analysis 模块。跨模块通信通过 EventBus。

## Implementation Phases

### Phase A — 历史面板 UI 重构

**目标**: 将历史面板从单栏 320px 升级为左右双栏可拖宽布局。

**变更范围**: `modules/perfetto_capture/src/history_panel.py`, `gui_tab.py`

**关键设计**:

1. **左右双栏布局** (QSplitter horizontal)
   - 左栏 (min 280px): 上半部 trace 列表 + 下半部分析历史 (QSplitter vertical)
   - 右栏 (min 320px): AI 对话区域（AnalysisChatWidget）
   - 面板整体最小宽度 600px，支持拖动左边缘加宽

2. **多选支持**
   - `SessionTreeWidget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)`
   - `_get_selected_items_data()` 返回 `list[dict]` 而非 `dict | None`
   - 操作按钮文字动态更新（"删除" → "删除 3 项"）

3. **拖入区域** (QWidget with dragEnterEvent/dropEvent)
   - 位于左栏顶部，接受 `.perfetto-trace` 文件
   - 拖入后移动到 `user_traces/` 托管目录
   - 自动刷新列表

4. **分析历史** (下半部)
   - 与 trace 历史共享 `SessionTreeWidget` 组件风格
   - 数据源从 `analysis_tasks` 表读取
   - 双击打开 HTML 报告

**依赖**: 无外部依赖

---

### Phase B — Pydantic AI 多 Agent 引擎

**目标**: 构建 Main/Sub/Review 三角色分析引擎。

**变更范围**: `modules/perfetto_analysis/src/agent/` (新目录)

**关键设计**:

1. **AnalysisOrchestrator** (非 Agent，纯 Python 编排器)
   ```
   async def analyze_single(trace_path, user_intent, process_name) -> AnalysisReport
   async def analyze_batch(tasks: list[AnalysisTask]) -> list[AnalysisReport]
   ```
   - 持有 LLMManager 引用，创建 `LiteLLMModel` 实例
   - 管理分析任务生命周期（状态转换、超时监控）
   - 通过 callback 函数通知 GUI 状态变化

2. **MainAgent** (Pydantic AI Agent)
   - System prompt: 场景路由指令 + 可用场景列表
   - 工具: `route_scene()` — 分析 trace 概览后返回场景类型
   - 输出: `AnalysisRouting(scene: str, sop_name: str, process_name: str)`

3. **SubAgent** (Pydantic AI Agent, per-trace 实例)
   - System prompt: 从 `skills/perfetto-analysis/sop/{scene}.md` 动态加载
   - 工具: pa_* 工具集 (14 个，通过 `build_analysis_tools()` 注册)
   - 输出: 结构化分析结论 (Pydantic model)
   - 上下文隔离: 每次创建新实例，不共享 conversation history

4. **ReviewAgent** (Pydantic AI Agent)
   - System prompt: 交叉评审指令
   - 输入: 所有 SubAgent 的结论摘要
   - 工具: 无（纯推理）
   - 输出: 评审意见 + 修正建议

5. **工具注册** (`tools.py`)
   - 封装 `PerfettoAnalysisService` 的 14 个 pa_* 方法为 Pydantic AI 工具函数
   - 每个工具有清晰的 docstring 和类型注解

**依赖**: `pydantic-ai`, `pydantic-ai-litellm`

---

### Phase C — 对话式分析集成

**目标**: 将 Agent 引擎与历史面板右栏对话区域连接。

**变更范围**: `modules/perfetto_capture/src/analysis_chat.py` (新文件), `gui_tab.py`

**关键设计**:

1. **AnalysisChatWidget** (QWidget)
   - 上方: 对话历史显示区域 (QTextBrowser, Markdown 渲染)
   - 下方: 输入框 (QLineEdit) + 发送按钮
   - trace 选中后自动填入输入框（支持多选：列出所有 trace 路径）
   - 有/无元数据的 trace 使用不同的 placeholder 文字

2. **AnalysisWorker** (QThread)
   - 在工作线程中运行 `asyncio.run(orchestrator.analyze_single(...))`
   - 通过 `pyqtSignal(str, str)` 传递流式输出：(role, content)
   - 通过 `pyqtSignal(str)` 传递状态更新：status_changed
   - 支持取消（设置 abort flag，Agent 在工具调用间检查）

3. **流式对话展示**
   - 用户消息: 蓝色气泡
   - AI 思考/推理: 灰色区域
   - 工具调用: 折叠面板（点击展开看原始数据）
   - 结论: 高亮文本
   - 报告链接: 可点击按钮（打开浏览器）

4. **跨模块通信**
   - `perfetto_capture` 通过 EventBus 发送 `perfetto_capture.request_analysis`
   - `perfetto_analysis` 插件监听事件，调用 `AnalysisOrchestrator`
   - 或者：直接通过 `context["pa_orchestrator"]` 调用（更简单）

---

### Phase D — 批量分析与报告系统

**目标**: 实现批量分析队列和 HTML 报告生成。

**变更范围**: `modules/perfetto_analysis/src/agent/orchestrator.py`, `report.py`, `templates/`

**关键设计**:

1. **批量分析队列**
   - `analyze_batch()` 接收 `list[AnalysisTask]`
   - 默认串行：依次调用 `analyze_single()`
   - 并行模式：使用 `asyncio.gather()` 并发执行（受 `parallel_count` 限制）
   - 每个任务状态独立跟踪（PENDING → ANALYZING → REVIEWING → COMPLETED）

2. **Review Agent 编排**
   - 所有 SubAgent 完成后，收集结论摘要
   - ReviewAgent 输入: 各 trace 的结论 + 设备信息 + 场景信息
   - ReviewAgent 输出: 交叉验证结果 + 修正建议

3. **HTML 报告生成** (Jinja2)
   - 模板位于 `modules/perfetto_analysis/templates/report.html`
   - 包含：基本信息、问题概况、根因分析表、关键数据摘要表、排查建议
   - 原始数据以 JSON 保存在 `raw_data/` 子目录
   - HTML 中通过 `<script>` 加载 JSON 实现数据联动（可选）

4. **报告文件结构**
   ```
   output/analysis/<trace_stem>_<YYYYMMDD_HHmmss>/
   ├── report.html
   └── raw_data/
       ├── trace_overview.json
       ├── jank_detection.json
       ├── dimension_cpu.json
       ├── dimension_thread.json
       └── conversation.json
   ```

---

### Phase E — 数据管理与收尾

**目标**: 包名数据库、分析状态可视化、移除旧 tab。

**变更范围**: `modules/perfetto_analysis/src/plugin.py`, `modules/perfetto_capture/src/models.py`, `history_storage.py`

**关键设计**:

1. **分析状态可视化**
   - `HistoryTrace` 模型扩展 `analysis_status` 字段
   - `SessionTreeWidget` 在 trace 节点后附加状态标记: ✅/❌/⏳
   - 刷新时从 `analysis_tasks` 表查询最新状态

2. **包名数据库**
   - JSON 文件存储 (`data/package_mappings.json`)
   - `PackageMappingDB` 类：CRUD + 学习 + 导出/导入
   - AI 分析完成后自动调用 `learn(package_name, process_name)`
   - 导出: `export_json(path)` → 用户可分享
   - 导入: `import_json(path)` → 合并（冲突保留本地）

3. **移除旧 Perfetto 分析 tab**
   - `PerfettoAnalysisPlugin.register_gui_tab()` 返回 `None`
   - 保留 `register_agent_tools()`, `register_cli_commands()`, `on_startup()` 等钩子
   - 保留 `PerfettoAnalysisService` 和所有 CLI 命令

4. **配置集成**
   - `AnalysisConfig` 存入 `modules/perfetto_analysis/data/config.json`
   - GUI 中通过设置面板暴露 `parallel_count` 和 `analysis_timeout_sec`

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 新增 Pydantic AI 依赖 | 多 Agent 编排需求 | 自建 Agent 编排层开发量大，且缺乏工具调用标准化 |
| 新增 Jinja2 依赖 | HTML 报告模板渲染 | 字符串拼接不可维护，Markdown→HTML 需额外工具 |
| 左右双栏面板 | 对话 + 列表同时可见 | 弹窗/tab 切换体验割裂 |
