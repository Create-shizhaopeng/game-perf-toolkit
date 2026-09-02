## 1. 迁移 diff 引擎到 game_perf（D1/D3 前置）

- [x] 1.1 `git mv`/cp 迁移 `workspace_tools/src/gameperf_diff_engine.py`、`gameperf_diff_service.py`、`gameperf_diff_models.py`、`gameperf_diff_errors.py`、`gameperf_xml.py`（如存在）到 `modules/game_perf/src/`，保持文件内容不变
- [x] 1.2 更新迁移文件的 import 路径与 `context` 键为 `gp_` 前缀，移除 `wo_` 引用
- [x] 1.3 改造 `build_diff_items` 支持以"当前 parser 的 DOM 树"为基准（而非独立文件解析）
- [x] 1.4 改造 merge/采纳落地目标为当前编辑 DOM，采纳后刷新派生缓存并置 dirty（采纳直写）
- [x] 1.5 引入文档源抽象（`LocalPath | Device(serial)`），支撑 编辑 vs 设备 / 两份本地 / 设备 vs 设备 三种组合；设备拉取复用现有 pull 缓存逻辑
- [x] 1.6 迁移 + 新增 diff service 层测试（复用 `game_perf/fixtures` 与 `workspace_tools/fixtures` 差异对样本），全部通过
- [x] 1.7 从 `workspace_tools` 移除 gameperf 相关文件、`manifest.json` 依赖与 `plugin.py` 注册（BREAKING）

## 2. 单一真相源与撤销（D2/D5）

- [x] 2.1 统一 `GamePerfParser` 编辑走 DOM 原子操作，`freq_rows`/`_game_level_data`/`_mode_level_data` 改为只读视图、变更后局部刷新
- [x] 2.2 移除 `update_freq_index` 的"改 dataclass + 手动 _sync"混合路径，`_refresh_game_policy()` 仅保留在解析/加载时调用
- [x] 2.3 实现 parser 层逆操作栈 `undo/redo`，覆盖频率、温度、策略、BindCore、PreEnv、version 编辑
- [x] 2.4 新增一致性 + 撤销/重做测试（编辑后重载 XML 不丢状态，undo/redo 往返一致）

## 3. 新工作台 GUI 骨架（D4）

- [x] 3.1 实现顶栏：来源徽标、version 可编辑、游戏下拉（+新增游戏）、未保存 dirty 指示
- [x] 3.2 内容区改为双 Tab（编辑 | 对比），底部操作条（推送/还原设备备份/重载/进度日志）复用现有 `GamePerfService`
- [x] 3.3 无头 GUI 实例化验证：`GamePerfTab` 新结构可创建，设备拉取/推送链路不被破坏

## 4. 编辑页（workbench-editor）

- [ ] 4.1 模式垂直卡片：选中游戏后该游戏所有 Mode 平铺为可折叠卡片，不再用模式下拉切换
- [ ] 4.2 温度档位表改「双下拉」：Gold/Prime/Gpu 各下限+上限两个 QComboBox，Hz 语义显示，保留下标↔Hz 自动换算，移除手输 `a_b` 索引列
- [ ] 4.3 频率表窄窗口横向滚动：整表保持最小宽度，外层横向滚动，双下拉不截断文字
- [ ] 4.4 BindCore 二进制输入 + hex 实时回显（方向反转，hex 为 XML 存值），非法输入就地红框不写 XML
- [ ] 4.5 策略表单 key 改用 `pairs.header` 完整路径，嵌套同名节点可区分；单字段编辑局部更新、不整块重建丢焦点
- [ ] 4.6 PreEnv 编辑：模式卡片内「高级…」入口，可增删改 CPU/GPU 频点，保存后写回 XML 并同步全部频率下拉选项
- [ ] 4.7 根 `version` 编辑写回 XML
- [ ] 4.8 编辑页测试（双下拉换算、BindCore 转换、路径展示、局部刷新、PreEnv/version 写回）

## 5. 对比页（workbench-compare）

- [ ] 5.1 对比对象三选一 UI（当前编辑 vs 设备 / 两份本地 / 设备 vs 设备）+ 各侧来源选择，后台线程执行、可取消
- [ ] 5.2 差异树按 游戏→模式→项 三层分组，默认只展开有差异节点，分组行显示差异计数（零差异组收起）
- [ ] 5.3 双向采纳（采纳基准侧 / 采纳对比侧）直写编辑文档并置 dirty；结构缺失项（不可合并）不提供采纳按钮
- [ ] 5.4 撤销最近一次采纳 + 重置为对比前基准
- [ ] 5.5 差异导出（Markdown / JSON：语义路径、两侧值、严重级别）
- [ ] 5.6 差异忽略：标记已忽略并计入摘要计数
- [ ] 5.7 对比页测试（三对象组合、差异树展开规则、采纳直写、撤销/重置、导出、忽略、取消）

## 6. 验证与收尾

- [ ] 6.1 全量 pytest（主项目 + game_perf + workspace_tools 剩余模块）通过
- [ ] 6.2 `python -m toolkit.app` 启动链验证 + 无头 GUI 实例化，7 插件加载正常
- [ ] 6.3 用户可见中文全部提取到 `strings_*.py`（`scripts/check_hardcoded_strings.py` 清零）
- [ ] 6.4 `ruff check .` + `ruff format` 通过
- [ ] 6.5 更新 `docs/PROGRESS.md`「近期工作」与 game_perf 模块文档/AGENTS.md 边界说明
