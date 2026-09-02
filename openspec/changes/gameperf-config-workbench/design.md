## Context

当前两个模块围绕同一份 `gameperfconfig.xml` 提供割裂的能力：

- **`modules/game_perf`（性能配置）**：`GamePerfParser`（解析/编辑）＋ `GamePerfService`（push/reset/pull/备份）＋ 上下分栏 GUI。调优循环主场景（设备拉取→调频→推送→重启验证）。
- **`modules/workspace_tools`（性能配置对比）**：`gameperf_diff_*`（语义 diff 引擎 + 合并 service）＋ 左右分栏 GUI。仅支持"另存为"输出，与编辑模块无数据连通。

已识别的问题（探索结论）：频率索引手输 `a_b` 下标、策略区编辑整块重建丢焦点、BindCore 显示方向反（当前 hex 输入/binary 只读）、GUI 丢弃 `pairs.header` 层级路径致嵌套同名节点无法区分、`PreEnv`/`version` 为编辑盲区、无撤销、对比采纳后需"另存为→重新加载"链路。parser 为 dataclass 缓存 + lxml DOM 双轨制（P36 踩坑根源）。

约束：模块不得跨 `src` import；Service 无 PyQt；后台操作 QThread；GUI 日志 `_log()`；中文提取 `strings_*.py`；代码移动 cp+Edit；UI 用 objectName + 全局 QSS。MainWindow 默认 1200×800，内容区宽约 700~1000px。

## Goals / Non-Goals

**Goals:**
- 单一工作台：同一文档上下文内完成 编辑、对比、采纳、推送
- 以调优循环为中心：设备拉取、频率双下拉、策略就地编辑、推送/还原保持在手边
- 差异感知融入：对比 Tab 差异树默认只展开有差异项；采纳直写编辑文档
- 消除"另存为→重开"链路与两模块来回切换

**Non-Goals:**
- 不做通用 XML diff 工具（仅 gameperfconfig 语义）
- 不实现三路合并（BASE/MINE/THEIRS）或 Git 集成
- 不做跨设备自动推送合并结果（推送仍由用户显式触发）
- 不重构 `toolkit/` 框架层公共 API

## Decisions

### D1 — 融合落点：迁移到 `game_perf` 模块内

将 `workspace_tools` 的 `gameperf_diff_*` 能力**迁移进 `game_perf`**，工作台作为 game_perf 的新 GUI Tab 交付；`workspace_tools` 移除 gameperf 相关文件与注册。

- **理由**：调优循环（push/reset/pull/备份/Agent 工具）全在 game_perf service 与 plugin 中，融合后对比增强直接复用；`context` 键沿用 `gp_` 前缀，改动面最小。模块隔离约束下，两个模块的 `src` 本就禁止互相 import，融合必然要求**代码迁移**而非引用。
- **备选 A**：新建独立模块 `config_workbench`。需重造 parser/push/备份生态且仍无法 import game_perf `src`，成本高、无收益。
- **备选 B**：留在 `workspace_tools` 并反向迁移 game_perf 编辑链。与"调优是主场景"相悖，且 workspace_tools 定位是通用工作台而非性能配置。
- **代码移动**：`git mv`/cp 迁移 `gameperf_diff_engine.py`、`gameperf_diff_service.py`、`gameperf_diff_models.py`、`gameperf_diff_errors.py`、`gameperf_xml.py`（若存在）到 `modules/game_perf/src/`，再 Edit 改造。

### D2 — 单一真相源：DOM 为唯一变更入口

保持 `GamePerfParser` 的公共查询 API 不变，但**统一所有编辑走 DOM 原子操作**，派生缓存（`freq_rows` / `_game_level_data` / `_mode_level_data`）仅作为只读视图在变更后刷新。

- **现状问题**：编辑同时写 dataclass 与 DOM（`update_freq_index` 改字段 + `_sync_row_to_xml`），且 `add_bindcore_row` 等操作触发 `_refresh_game_policy()` 全量重解析，双轨易不一致（P36）。
- **改造**：每个编辑方法 = 原子改 DOM → 局部刷新派生缓存 → 通知 UI。移除"手动 _sync + 全量重解析"的混合路径；`_refresh_game_policy` 仅保留在解析/加载时调用。
- **备选**：引入独立 Tree Model + 序列化器（完整 MV）——对本规模过度设计。

### D3 — diff 引擎对接当前 DOM，实现采纳直写

迁移后的 diff 引擎**直接对当前 parser 的 DOM 树运行**（而非对独立文件重新解析）：`build_diff_items(baseline_dom, comparator_dom)` 语义比较；`apply_merge` 的落地目标为**当前编辑 DOM**，采纳后刷新视图并置 dirty。

- 对比对象统一抽象为**文档源** `LocalPath | Device(serial)`，三种组合（编辑 vs 设备 / 两份本地 / 设备 vs 设备）都是"基准源 vs 对比源"，设备拉取复用现有 pull 缓存逻辑。
- **备选**：保持 diff 独立解析文件，采纳后回写路径——无法实现"直写编辑文档"，被否。

### D4 — UI 结构：顶栏 + 双 Tab（编辑/对比）+ 底部操作条

```
内容区
├─ 顶栏：来源徽标 | version(可编辑) | 游戏下拉(+新增) | ●未保存 | [高级…]
├─ QTabWidget
│   ├─ 编辑页：QScrollArea
│   │   └─ 模式垂直卡片(Normal/HighPerf…) 每卡=头(折叠)+模式字段行
│   │        +温度档位表+策略表单+BindCore+[高级…PreEnv]
│   └─ 对比页：对象选择条 + 差异树(QTreeWidget 三层分组)
└─ 底部操作条：推送 | 还原设备备份 | 重载 | 进度/日志
```

- 温度档位表：**始终双下拉**（下限+上限，Hz 语义显示），窄窗口**整表横向滚动**（`QTableWidget` 保持最小宽度，外层 `QScrollArea` 横滚），不降级为单下拉。
- 策略表单：key 用 `pairs.header`（含路径）而非 `dom.tag`，嵌套同名节点可区分；单字段编辑**局部更新**，不整块重建。
- BindCore：`QLineEdit` 二进制输入 + `QLabel` hex 实时回显（方向反转，hex 为 XML 存值）；非法输入就地红框。
- 差异树：`游戏→模式→项` 三层分组，**默认只展开有差异的节点**，分组行显示差异计数。

### D5 — 撤销/重做

parser 层维护**逆操作栈**：每次原子编辑记录可逆描述（原值/目标路径），`undo/redo` 反向执行并刷新；覆盖频率、温度、策略、BindCore、PreEnv、version。GUI 提供按钮 + `Ctrl+Z`/`Ctrl+Y`。

### D6 — 兼容与保留

- `GamePerfService.push/reset/pull/get_info` 签名与行为不变，推送链路与 `PushRecord` 历史兼容。
- Agent 工具（`perf_push`、`perf_reset`、`perf_info`、`gp_analyze_config`）保留。
- `workspace_tools` 移除 gameperf 相关后，其余非 gameperf 能力不受影响。

## Risks / Trade-offs

- **[大规模改造] → 分阶段迁移**：先 cp+改造 diff 引擎并跑通 service 层测试，再搭新 GUI 骨架，最后替换旧编辑页与移除旧模块，每阶段可独立验证。
- **[双 parser 统一] → 保持 parser API 兼容**：diff 引擎对接 DOM 的改造收敛在 service/engine 层，对外查询 API 不动。
- **[现有测试重写] → 复用 fixtures**：`game_perf/fixtures`、`workspace_tools/fixtures` 差异对样本直接复用；先保证 parser/service 层测试绿，再动 GUI。
- **[宽度约束 700~1000px] → 语义化双下拉 + 横滚**：Hz 语义显示（约 55px/下拉）较原始 6 位数字（约 95px）显著缓解，横向滚动兜底。
- **[双轨制残留] → D2 统一 DOM 入口**：消除 dataclass/DOM 不一致，避免再次踩 P36。
- **[采纳直写的数据一致] → 原子 DOM 更新 + 视图刷新 + dirty 同步**：采纳与编辑走同一更新通道，避免旁路。

## Migration Plan

1. **迁移 diff 引擎**：cp `gameperf_diff_*` 到 `modules/game_perf/src/`，改造 `build_diff_items`/merge 对接 parser DOM；跑通 service 层测试。
2. **新工作台 GUI 骨架**：game_perf Tab 改为 顶栏 + 双 Tab + 底部操作条；设备自动拉取、推送/还原复用现有 service。
3. **编辑页改造**：模式垂直卡片、频率双下拉、BindCore 二进→hex、策略路径、dirty、撤销/重做 逐个落地。
4. **补齐盲区**：PreEnv 高级入口编辑、version 编辑。
5. **对比页**：对象三选一、差异树只展开有差异、采纳直写、导出/忽略。
6. **清理 workspace_tools**：移除 gameperf 相关文件与 plugin 注册，更新 `manifest.json`。
7. **验证**：全量 pytest + `python -m toolkit.app` 启动链 + 无头 GUI 实例化。

## Open Questions

- Agent 工具是否本期扩展 diff 能力（如"对比当前配置与设备"自然语言入口）？——建议放后续迭代。
- 差异树"项"与编辑行的**定位联动**（点击差异项跳转编辑行高亮）是否本期做？——影响采纳体验，倾向做。
- 过渡期旧 Tab 入口是否保留一个带标注的占位？——倾向直接替换，历史可通过 PushRecord 追溯。
