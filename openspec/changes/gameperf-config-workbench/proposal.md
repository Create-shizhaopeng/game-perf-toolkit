## Why

「性能配置」（`modules/game_perf`）与「性能配置对比」（`modules/workspace_tools` 内的 `gameperf_diff_*`）是两个围绕**同一份 `gameperfconfig.xml`** 的操作模块，但功能割裂、交互不顺手。调优循环（最常用场景：设备拉取→调频→推送→重启验证）中：频率索引要手输 `a_b` 下标串、策略区编辑整块重建丢焦点、BindCore 显示方向反了、嵌套同名标签界面无法区分（部分标签"看得见但编辑不了"），且无撤销。对比采纳后要"另存为→切回性能配置→重新加载→再编辑→推送"，链路长。用户需要一套以调优循环为中心的、编辑与对比一体的配置工作台。

## What Changes

- **融合两模块为「配置工作台」**：`game_perf` 的编辑能力与 `workspace_tools` 的 `gameperf_diff` 对比能力统一到同一文档上下文，消除"另存为→重开"链路。
- **编辑视图**：游戏下拉 + 该游戏**所有 Mode 垂直卡片平铺**（默认展开、可折叠），不再用下拉反复切模式。
- **频率表语义化**：始终**双下拉**（下限/上限，Hz 语义显示），窄窗口**横向滚动**不降级；不再手输 `a_b` 下标串。
- **BindCore 输入/显示反转**：**二进制输入 → 十六进制回显**（hex 才是 XML 存值）。
- **补齐编辑盲区**：`PreEnv`（CPU/GPU 频率表）经卡片内「高级…」入口可编辑；根 `version` 可编辑；策略表单保留**层级路径**，嵌套同名标签可区分。
- **对比视图**：独立 Tab，差异树按 `游戏→模式→项` 分层、**默认只展开有差异的节点**；支持三种对比对象（本地编辑 vs 设备 / 两份本地 / 设备 vs 设备）。
- **采纳直写**：对比 Tab 采纳结果直接写入编辑文档并置 dirty，无需另存再重开。
- **可见性**：顶栏显示文档来源、version（可编辑）、**未保存 dirty 指示**。
- **BREAKING**：`game_perf` 与 `workspace_tools` 的 gameperf 相关 GUI/能力被融合改造，现有两模块的独立 Tab 入口与部分公共 API 将迁移或移除；现有 `GamePerfParser` / `GamePerfService` / `GamePerfConfigDiffService` 的职责重新划分。

## Capabilities

### New Capabilities

- `workbench-editor`: 配置工作台**编辑视图** —— 融合 game_perf 编辑能力：游戏选择 + 所有 Mode 垂直卡片平铺、频率档位双下拉、BindCore 二进制输入/hex 回显、策略表单层级路径展示、PreEnv/version 编辑、dirty 指示、撤销/重做。
- `workbench-compare`: 配置工作台**对比视图** —— 融合 gameperf_diff 能力：三种对比对象、差异树按语义层级组织且默认只展开有差异项、双向采纳直写编辑文档、撤销/重置/导出。

### Modified Capabilities

（无 —— `openspec/specs/` 现有 15 个 spec 均与 gameperf 无关，无既有需求被修改。）

## Impact

- **改动范围**：`modules/game_perf/`（`src/gui_tab.py`、`src/parser.py`、`src/service.py`、`src/models.py`、`manifest.json`、`src/plugin.py`）与 `modules/workspace_tools/`（`src/gameperf_diff_*`、`src/gui_tab.py`、`src/plugin.py`）。
- **模块归属待设计**：融合后配置工作台落在哪个模块（game_perf 内吸收 diff / workspace_tools / 新独立模块）需在 `design.md` 决策，直接影响 `context` 键前缀（现有 `gp_` / `wo_`）与模块依赖声明。
- **架构约束**：需在 design 中重新审视 NFR（模块不得跨 `src` import、Service 无 PyQt、QThread 后台、`_log()` 日志、字符串提取到 `strings_*.py`）。
- **测试**：`modules/game_perf/tests/`、`modules/workspace_tools/tests/` 重写/补充；fixtures 复用。
- **风险**：大改造（双模块、双 parser 统一为单一真相源）；历史 `PushRecord` / 推送链路需保持兼容。
