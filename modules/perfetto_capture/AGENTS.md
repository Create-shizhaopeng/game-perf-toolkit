# Perfetto卡顿抓取 — AI 开发规则

> 继承项目根 Constitution（`.specify/memory/constitution.md`），以下为模块级补充约束。

## 目录

- [模块概述](#模块概述)
- [继承的全局规则](#继承的全局规则)
- [模块边界约束](#模块边界约束)
- [模块特有规则](#模块特有规则)
  - [Buffer 自动估算](#buffer-自动估算)
  - [Trace 输出路径](#trace-输出路径)
- [历史面板与分析集成](#历史面板与分析集成)
- [活跃 Spec](#活跃-spec)
- [测试要求](#测试要求)

## 模块概述

自动化 Perfetto trace 的抓取、管理与导出，用于分析 Android 设备上的卡顿（jank）问题。支持 trace 配置管理、自动触发抓取、trace 文件管理与分析入口。

## 继承的全局规则

> 本模块遵循项目全局编码规范（详见项目根 `.cursor/rules/`）
> - Python 3.12+，类型注解覆盖所有公共方法
> - 数据模型：公共 API 用 Pydantic，模块内部用 dataclass
> - 中文注释和文档字符串
> - CLI 输出 SHOULD 支持 JSON 格式（渐进落地）
> - 插件 context 键名使用 `pe_` 前缀（如 `pe_service`、`pe_adb`）
> - 开发前 MUST 阅读 `docs/experience/development-pitfalls.md`

## 模块边界约束

- ✅ 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`
- ❌ 禁止修改：`toolkit/`、其他模块目录、项目根配置文件
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`
- ❌ 禁止导入：`toolkit.core` 内部实现（plugin_manager、db_manager 等）、其他模块的 `src/`

## 模块特有规则

- ADB 操作通过 `context["pe_adb"]` 调用
- Perfetto 配置文件（.pbtx）存放在 `assets/` 目录
- 抓取完成后通过 EventBus 发布 `perfetto_capture.trace_ready` 事件
- Trace 文件路径和元数据持久化到数据库

### Buffer 自动估算

- Ring buffer 大小自动估算使用 **实测标定** 数据；常量定义：
  - `LIGHT_RATE_KB_PER_SEC = 9200`（轻载基线，约 90 MB / 10 s）
  - `HEAVY_PER_CAT_RATE_KB = 2600`（超轻载阈值后每 tag 附加速率）
  - `buffer_safety_factor` 默认 **1.2**
  - 上下限：`MIN_BUFFER_KB = 91136`（~89 MB）、`MAX_BUFFER_KB = 512000`（~500 MB）
- **tag 总数** = atrace categories 数量 **+** ftrace events 数量；`calculate_buffer_size` 可传入 `ftrace_count`，与配置中的 `advanced.ftrace_events` 对齐
- 详见 `specs/002-auto-buffer/spec.md`

### Trace 输出路径

- **开发环境**：Trace 会话导出根目录为 `modules/perfetto_capture/data/output/trace/`（`output` 为配置项 `output_dir`，默认 `"output"`）
- **打包可执行文件（`sys.frozen`）**：根目录为 **`<exe 所在目录>/output/trace/`**

## 历史面板与分析集成

历史面板（`history_panel.py`）已升级为左右双栏分析管理中心。

| 文件 | 说明 |
|------|------|
| `history_panel.py` | 左右双栏布局（QSplitter），左栏上下分割（trace 列表 + 分析历史），右栏 AI 对话 |
| `analysis_chat.py` | AI 分析对话组件（AnalysisChatWidget + AnalysisWorker） |
| `drag_drop_area.py` | 拖入区域，接受外部 .perfetto-trace 文件 |

### 关键约束

- 面板最小宽度 600px（左栏 280px + 右栏 320px），覆盖式从右侧滑出
- `AnalysisWorker(QThread)` 调用 `context["pa_orchestrator"]` 执行分析，MUST NOT 在主线程运行异步分析
- trace 选中变化时通过 `itemSelectionChanged` 信号更新右栏对话区域
- 支持 `ExtendedSelection` 多选模式，批量删除前弹出确认对话框
- 分析完成后通过 `QDesktopServices.openUrl()` 打开 HTML 报告
- 拖入文件复制到 `user_traces/` 目录后自动刷新列表

## 活跃 Spec

- [005-auto-jank-capture](specs/005-auto-jank-capture/) — FPS 监控 + 卡顿自动抓取 (Draft)
- [007-fps-chart-enhancement](specs/007-fps-chart-enhancement/) — FPS 图表长时数据 + 缩放/平移/悬停 (Draft)

完整 Spec 索引见 [specs/INDEX.md](specs/INDEX.md)。

## 测试要求

- `service.py` 中每个公共方法至少一个测试用例
- 测试数据放在 `fixtures/` 目录
