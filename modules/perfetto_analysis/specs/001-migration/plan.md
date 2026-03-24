# Implementation Plan: Perfetto 解析分析模块迁移

## 目录

- [技术上下文](#技术上下文)
- [Constitution 合规性](#constitution-合规性)
- [影响范围](#影响范围)
- [分阶段实施方案](#分阶段实施方案)
  - [Phase 1: 数据模型与配置](#phase-1-数据模型与配置)
  - [Phase 2: 分析引擎迁移](#phase-2-分析引擎迁移)
  - [Phase 3: Service 封装层](#phase-3-service-封装层)
  - [Phase 4: Plugin 注册](#phase-4-plugin-注册)
  - [Phase 5: CLI 迁移](#phase-5-cli-迁移)
  - [Phase 6: GUI 实现](#phase-6-gui-实现)
  - [Phase 7: 混合 DB 与事件联动](#phase-7-混合-db-与事件联动)
  - [Phase 8: 测试与文档](#phase-8-测试与文档)
- [依赖安装](#依赖安装)
- [风险与缓解](#风险与缓解)

---

## 技术上下文

### 依赖项

| 依赖 | 版本 | 用途 |
|------|------|------|
| perfetto | >=0.16.0 | TraceProcessor — trace 查询引擎 |
| ~~PyYAML~~ | — | 本模块不使用（C-004: 仅 JSON 配置） |
| Pydantic | >=2.0 | 配置模型（项目已有） |
| PyQt6 | 已有 | GUI |
| Typer | 已有 | CLI |
| pluggy | >=1.3 | 插件注册（项目已有） |

### 源项目文件清单（20 个 Python 模块）

| 文件 | 大小 | 角色 | 改动程度 |
|------|------|------|---------|
| parser.py | 22KB | Phase 1 丢帧解析 | 仅调整导入路径 |
| analyzer.py | 12KB | Phase 2 分析编排 | 仅调整导入路径 |
| storage.py | 13KB | SQLite 持久化 | 仅调整导入路径 |
| export.py | 31KB | Markdown 报告导出 | 仅调整导入路径 |
| summary_analysis.py | 14KB | 全 Trace 整体分析 | 仅调整导入路径 |
| cpu_analysis.py | 11KB | CPU 维度分析 | 不改动 |
| binder_analysis.py | 7KB | Binder 维度分析 | 不改动 |
| thread_analysis.py | 7KB | 线程维度分析 | 不改动 |
| report_writer.py | 6KB | 报告文件写入 | 调整输出路径逻辑 |
| config.py | 2KB | 配置加载 | 重写为 Pydantic 适配 |
| app_type.py | 5KB | App 类型检测 | 不改动 |
| cpu_topology.py | 5KB | CPU 拓扑初始化 | 不改动 |
| lock_analysis.py | 4KB | 锁竞争分析 | 不改动 |
| input_analysis.py | 4KB | 输入事件分析 | 不改动 |
| gpu_analysis.py | 3KB | GPU 分析 | 不改动 |
| dimension_registry.py | 3KB | 维度注册表 | 不改动 |
| frame_boundary.py | 3KB | 帧边界确定 | 不改动 |
| io_analysis.py | 3KB | IO 阻塞分析 | 不改动 |
| sf_analysis.py | 3KB | SF 合成分析 | 不改动 |
| gc_analysis.py | 2KB | GC 分析 | 不改动 |

---

## Constitution 合规性

| 原则 | 合规措施 |
|------|---------|
| I. Plugin-First | 独立模块，manifest.json 声明元数据 |
| II. Three-Surface Unity | Service API 共享，GUI/CLI/Agent 仅调用入口 |
| III. Agent-Driven | register_agent_tools 注册 5 个工具 |
| IV. Dependency Inversion | 仅导入 toolkit.sdk.*、toolkit.core.hookspecs |
| V. Presentation Separation | service.py 纯同步无 GUI 代码；gui_tab.py 仅展示 |
| VI. Open-Closed | 不修改 toolkit/core/ |
| VII. Spec-Driven | 遵循 speckit 8 步流程 |

---

## 影响范围

### 新增文件

| 路径 | 说明 |
|------|------|
| `modules/perfetto_analysis/src/models.py` | Pydantic 配置 + dataclass 内部模型 |
| `modules/perfetto_analysis/src/service.py` | Service 封装层 |
| `modules/perfetto_analysis/src/plugin.py` | pluggy 注册（脚手架已生成，需完善） |
| `modules/perfetto_analysis/src/cli_commands.py` | Typer CLI（脚手架已生成，需完善） |
| `modules/perfetto_analysis/src/gui_tab.py` | PyQt6 GUI（脚手架已生成，需完善） |
| `modules/perfetto_analysis/src/engine/*.py` | 20 个分析引擎模块（从源项目迁移） |
| `modules/perfetto_analysis/src/migrations/001_create_tables.sql` | 共享 DB 迁移脚本 |
| `modules/perfetto_analysis/assets/config.json` | 默认配置模板 |
| `modules/perfetto_analysis/data/config.json` | 用户配置（运行时） |
| `modules/perfetto_analysis/tests/test_service.py` | Service 层测试 |
| `modules/perfetto_analysis/tests/test_parser.py` | 解析引擎测试 |
| `modules/perfetto_analysis/tests/conftest.py` | 测试固件 |

### 修改文件

| 路径 | 说明 |
|------|------|
| `scripts/run_all_tests.py` | 注册新模块测试目录 |

### 不修改

- `toolkit/core/` — 不修改框架代码
- `toolkit/sdk/` — 不修改 SDK
- 其他模块 — 不修改

---

## 分阶段实施方案

### Phase 1: 数据模型与配置

**目标**：定义 Pydantic 配置模型和 dataclass 内部数据模型

**涉及文件**：
- `src/models.py` — 新建
- `assets/config.json` — 新建
- `data/config.json` — 新建（首次运行时从 assets 复制）

**技术要点**：
- `AnalysisConfig(BaseModel)` 替代源项目 dict 配置
- `load_config()` / `save_config()` 函数
- 配置文件路径解析逻辑（开发模式 vs PyInstaller 打包模式）

### Phase 2: 分析引擎迁移

**目标**：将源项目 20 个 Python 模块复制到 `src/engine/`，调整包引用

**涉及文件**：
- `src/engine/__init__.py` — 已创建
- `src/engine/parser.py` — 从源项目迁移
- `src/engine/analyzer.py` — 从源项目迁移
- `src/engine/storage.py` — 从源项目迁移
- `src/engine/export.py` — 从源项目迁移
- `src/engine/config.py` — 重写（适配 Pydantic 配置）
- `src/engine/report_writer.py` — 迁移，调整输出路径
- 其余 13 个分析模块 — 原样复制

**技术要点**：
- 内部 `from . import parser` 等相对引用保持不变
- `engine/config.py` 重写为接收 `AnalysisConfig` Pydantic 对象的适配层
- `report_writer.py` 的输出路径从 `report/` 改为 `output/trace_report/`
- 验证所有模块导入正确，无循环依赖

### Phase 3: Service 封装层

**目标**：创建 `PerfettoAnalysisService` 作为 Three-Surface Unity 的 API 层

**涉及文件**：
- `src/service.py` — 重写

**技术要点**：
- 纯同步实现，不导入 PyQt6
- 封装 engine/ 的 parser、analyzer、storage、export 调用
- 支持 `on_progress: Callable[[str], None] | None` 回调
- 管理模块独立 DB 路径和报告输出路径（C-002 修订：`output/trace_report/`）
- 开发环境：`data/output/trace_report/<trace_stem>/`；打包后：`<exe_dir>/output/trace_report/<trace_stem>/`
- `analyze()` 方法编排完整流程：Phase 1 → Phase 2 → 导出
- `regenerate_report()` 从 DB 已有数据重新生成报告（C-006）
- `delete_analysis_record()` 智能删除：仅删除当前记录，最后一条时清理磁盘文件（C-007）
- 工作线程使用独立 `sqlite3.connect()` 写入共享 DB，避免跨线程 SQLite 错误
- 错误处理：捕获引擎异常，转换为用户友好的错误信息

### Phase 4: Plugin 注册

**目标**：实现 pluggy 插件注册

**涉及文件**：
- `src/plugin.py` — 完善脚手架代码

**技术要点**：
- context 键：`pa_service`、`pa_adb`、`pa_data_dir`
- `register_gui_tab` 返回 `PerfettoAnalysisTab`
- `register_cli_commands` 注册 `analysis` Typer 子命令
- `register_agent_tools` 注册 5 个 Agent 工具
- `on_startup` 中初始化 Service、检查 perfetto 依赖
- perfetto_capture.trace_ready 事件监听（可配置）

### Phase 5: CLI 迁移

**目标**：将 argparse CLI 迁移为 Typer 子命令

**涉及文件**：
- `src/cli_commands.py` — 重写

**技术要点**：
- `analysis_app = typer.Typer(help="Perfetto 解析分析")`
- 子命令：parse、export、analyze、dims、history
- 参数映射：`--process`、`--app-type`、`--analyze-top` 等
- 输出格式：默认 Rich Table，`--json` 输出 JSON
- 进度显示：Rich progress bar

### Phase 6: GUI 实现

**目标**：实现左右分栏 GUI Tab

**涉及文件**：
- `src/gui_tab.py` — 重写

**技术要点**：
- 继承 BaseTab
- QSplitter 左右分栏，左侧固定 580px（`_LEFT_PANEL_W` 常量），右侧自适应
- 左侧：文件选择（QLineEdit 320px + QPushButton + 拖拽）、配置区（QComboBox, 无 QSpinBox）、控制区（在配置与历史之间）、历史列表（QTableWidget 6 列固定宽度）
- 右侧：结果预览区（分析完成后显示）、底部操作日志（QTextEdit readonly, 固定高度 150px）
- 控制区位于配置与历史之间（非底部），开始/停止按钮各 100px，使用 QStyle.StandardPixmap 图标
- 历史操作列含 4 个按钮：重新生成（从 DB）、打开报告、打开目录、删除
- QThread + pyqtSignal 执行后台分析
- 维度多选：QPushButton + _PersistentMenu（QMenu 子类，避免 Windows QComboBox popup 崩溃）
- UI 刷新使用 QTimer.singleShot(100ms) 延迟执行，避免 use-after-free 竞态

### Phase 7: 混合 DB 与事件联动

**目标**：实现共享 DB 索引和 perfetto_capture 事件联动

**涉及文件**：
- `src/migrations/001_create_tables.sql` — 新建
- `src/migrations/002_add_process_name.sql` — 新增 process_name 字段
- `src/migrations/003_add_mode_dimensions.sql` — 新增 mode、dimensions 字段
- `src/plugin.py` — 添加事件监听逻辑

**技术要点**：
- `pa_analysis_tasks` 表通过 toolkit db_manager 迁移创建
- 迁移脚本 002/003 通过 ALTER TABLE 添加新字段（向后兼容）
- Service 中 `_ensure_extra_columns()` 动态检测并添加字段（防御性兼容）
- 共享 DB 写入使用独立 `sqlite3.connect()` 保证线程安全
- 去重策略：DELETE WHERE trace_path=? AND mode=? → INSERT（覆盖同模式记录）
- Service 在分析完成后写入共享 DB 索引（含 process_name、mode、dimensions）
- 事件联动：plugin 监听 trace_ready，检查配置后调用 service.analyze()

### Phase 8: 测试与文档

**目标**：编写测试用例和完善文档

**涉及文件**：
- `tests/test_service.py` — 新建
- `tests/test_parser.py` — 新建
- `tests/conftest.py` — 新建
- `scripts/run_all_tests.py` — 注册新模块

**技术要点**：
- mock TraceProcessor 查询结果
- 测试 Service 层所有公共方法
- 测试配置加载/保存
- 测试 CLI 命令输出

---

## 依赖安装

```powershell
.venv\Scripts\pip.exe install perfetto>=0.16.0 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

在 Phase 2 开始前执行。

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| perfetto 包版本兼容性 | TraceProcessor API 可能变化 | 锁定 >=0.16.0，测试验证 |
| engine/ 内部引用调整遗漏 | 运行时 ImportError | Phase 2 完成后立即执行导入测试 |
| 大 trace 文件分析超时 | GUI 假死 | QThread 后台执行 + 进度回调 |
| 共享 DB 迁移冲突 | 表名冲突 | 使用 pa_ 前缀 + IF NOT EXISTS |
| 报告输出路径权限 | 写入失败 | 创建目录前检查权限，错误提示 |
