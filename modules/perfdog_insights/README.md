# PerfDog 分析（`perfdog_insights`）

Toolkit 插件：离线导入 PerfDog **`.xlsx/.xlsm`**，生成摘要、洞察与建议；侧栏 **「PerfDog分析」**。

**联合游戏性能策略分析**：在 **「游戏性能配置」** 中已加载 `gameperfconfig*.xml` 并选择游戏/性能模式后，本 Tab 在完成 PerfDog 分析后可点击 **「联合分析」**，对照 XML 策略与当前报告（**无需连接设备**）。需求与烟测步骤见 **`SPECIFY_FEATURE=004-perfdog-import-insights`** 对应规格：[specs/004-perfdog-import-insights/quickstart.md](../../specs/004-perfdog-import-insights/quickstart.md)。

## 文档（实现与需求）

| 文档 | 说明 |
|------|------|
| [specs/004-perfdog-import-insights/implementation.md](../../specs/004-perfdog-import-insights/implementation.md) | **实现记录**：本模块与 `toolkit/core/perfdog` 的变更总账 |
| [specs/004-perfdog-import-insights/quickstart.md](../../specs/004-perfdog-import-insights/quickstart.md) | 开发与运行入口（含联合分析烟测） |
| [specs/004-perfdog-import-insights/tasks.md](../../specs/004-perfdog-import-insights/tasks.md) | 任务清单 |

## 源码结构

- `manifest.json` — 插件清单（依赖 `device_disguise`、`game_perf`、`perfetto_capture` 以固定侧栏顺序）
- `src/plugin.py` — 钩子注册
- `src/gui_tab.py` — UI（含联合分析区与导出/复制拼接）
- `src/analysis_worker.py` — 后台解析线程
- `src/joint_worker.py` — 联合分析后台线程

核心解析逻辑位于 **`toolkit/core/perfdog/`**；联合分析纯函数位于 **`toolkit/core/joint_assessment/`**（非本目录）。
