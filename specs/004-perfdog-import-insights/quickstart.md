# Quickstart: 开发 PerfDog 分析模块（lv-game-toolkit）

## 前置

- 仓库：本仓库根目录（`lv-game-toolkit`）
- Python **3.12+**，在根目录执行 `pip install -e ".[dev]"`（含 `openpyxl`、`pandas`）
- 参考规范：同目录 [spec.md](./spec.md)

## 目录与入口

1. 核心库：`toolkit/core/perfdog/`（解析、洞察、`load_and_analyze` / `build_markdown`）。
2. GUI 模块：`modules/perfdog_insights/`（`plugin.py` 注册 `register_gui_tab`，`gui_tab.py` + `analysis_worker.py`）。
3. 启动主程序：`python -m toolkit.app`，侧栏选择 **「PerfDog分析」**；**无需连接设备**即可拖入 `.xlsx`。

## 单测

```bash
cd lv-game-toolkit
pytest tests/test_perfdog_workbook.py -q
```

测试会在临时目录生成最小 xlsx，验证 `load_and_analyze` 不崩溃。真实夹具可置于 `modules/perfdog_insights/fixtures/`（脱敏，勿提交用户数据）。

## 依赖

根目录 `pyproject.toml` 已包含：

- `pandas>=2.0`
- `openpyxl>=3.1`

## 文档链路

| 文档 | 用途 |
|------|------|
| [spec.md](./spec.md) | 产品需求 |
| [plan.md](./plan.md) | 技术方案与分阶段 |
| [implementation.md](./implementation.md) | **实现记录**：已落地文件、路径差异、Data_v4 兼容、修订历史 |
| [tasks.md](./tasks.md) | 任务拆解与完成勾选 |
| [data-model.md](./data-model.md) | 数据结构 |
| [contracts/analysis_api.md](./contracts/analysis_api.md) | 模块对外契约 |
| [contracts/joint_assessment_api.md](./contracts/joint_assessment_api.md) | **联合分析** Core API（US9～US11） |

## 联合分析烟测（US9～US11）

1. 启动 `python -m toolkit.app`，**无需连接设备**。
2. **游戏性能配置**：加载 `gameperfconfig*.xml`，选中与 PerfDog 会话一致（或故意不一致）的游戏与模式。
3. **PerfDog 分析**：拖入脱敏 `.xlsx`，等待标准报告生成。
4. 点击 **「联合分析」**（`PerfdogInsightsTab` 工具栏按钮）：应看到策略要点 / 观测要点 / 一致性或矛盾；包名不一致时应先确认。
5. **导出/复制**：报告应包含联合章节，且含启发式/复测免责声明（**JA-FR-007**）。

单测（实现落地后）：

```bash
pytest toolkit/core/joint_assessment/tests/test_joint_assess.py -q
```

## 常见问题（解析）

- **提示找不到 Data_v4**：多为表名大小写、标记与表头间空行、列名未映射等；处理策略见 **[implementation.md §8](./implementation.md)** 与源码 `toolkit/core/perfdog/workbook.py`、`column_aliases.py`。
