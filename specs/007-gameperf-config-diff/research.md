# Research: gameperfconfig 多文件对比与合并

**Feature**: 007-gameperf-config-diff | **Date**: 2026-04-03

## R1 — 差异算法：语义 vs 行级

| 方案 | 说明 |
|------|------|
| A. 行级 text diff | 实现快，但对 XML 属性/换行敏感，测试工程师难读 |
| B. DOM 深度比对 + 业务路径 | 与现有解析模型一致，展示可按游戏/模式聚合 |

**Decision**: **B 为主**。在 `lxml` 树上按规格路径（Game → Mode → …）遍历；对 PreEnv/BaseInfo/GamePolicy 分块对比。同一语义路径下 **属性与文本** 分别报告。无法映射的节点 **降级** 为「未分类结构差异」块（满足 spec Edge Cases）。

**Rationale**: 对齐 FR-003「用户可理解的结构化方式」与 **gameperfconfig** 语义结构（与 game_perf 编辑对象一致；**本模块自行实现** lxml 遍历，不依赖 game_perf 源码）。

**Alternatives considered**: unified diff 仅作调试可选输出（Out of scope for MVP UI）。

---

## R2 — 多对比文件 UI 模型

| 方案 | 说明 |
|------|------|
| A. 同时展示 N 路矩阵 | 信息密度过高 |
| B. 基准 vs 当前选中的一个对比文件 + 全局摘要 | 符合认知负荷 |

**Decision**: **B**。左侧或顶部 **对比文件列表**（带变更计数）；主差异树针对 **当前选中的对比文件与基准**；差异项上仍带 **来源文件 id** 以便多源合并同一工作副本。

**Rationale**: 满足「多个文件参与」且保持 SC-001 3 分钟内可操作。

---

## R3 — 采纳与撤销

**Decision**: 工作副本 = 基准 DOM 的 **深拷贝** + **覆盖补丁栈**（list of operations）；**撤销** = 弹出栈顶或「重置为基准」一键清空补丁。保存时 **物化** 为最终 XML（`pretty_print=True` 与现有编辑器一致）。

**Rationale**: 可测、可渐进增强为多步撤销（栈深度可配置）。

---

## R4 — 设备文件来源

**Decision**: 在 **`workspace_tools` Service** 内使用 **`context["adb"]`（AdbManager）** 按与 game_perf **相同标准路径** `/system/etc/gameperfconfig.xml` 拉取到本模块缓存目录；**不调用** `GamePerfService`。拉取结果标记 `FileProvenance.DEVICE_CACHED`。

**Rationale**: 满足 FR-007 与产品路径一致，且遵守模块 `src` 互不导入。

---

## R5 — 性能目标（落实 SC-004）

**Decision**: 10MB 以内文件，在 **16G RAM / SSD 典型开发机** 上，**单次全量语义 diff（单对比文件）≤ 8s** 作为首期验收；若超时需在 UI 显示进度并可取消（与 LVGT 其他 Tab 长任务模式一致）。

**Rationale**: 规格要求「可测」；具体硬件在 tasks 中记录测量环境。

---

## R6 — Constitution 与模块边界

**Decision**: 功能放在 **`modules/workspace_tools`**；**禁止** import `modules.game_perf.src.*`；与 game_perf **仅约定对齐**（路径、文件名、XML 容错策略）。

**Rationale**: 产品将本特性划归工作区工具模块；模块隔离优先于代码复用，重复解析逻辑可后续上沉 `toolkit`。
