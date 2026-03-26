# Tasks: 游戏性能配置模块迁移

## 目录

- [Phase 1: 数据模型 + 解析引擎](#phase-1-数据模型--解析引擎)
- [Phase 2: 推送/还原服务层](#phase-2-推送还原服务层)
- [Phase 3: CLI 命令](#phase-3-cli-命令)
- [Phase 4: GUI Tab 页](#phase-4-gui-tab-页)
- [Phase 5: 插件集成](#phase-5-插件集成)
- [Phase 6: 测试 + 回归验证](#phase-6-测试--回归验证)
- [Phase 7: 连接后自动载入设备配置（US6）](#phase-7-连接后自动载入设备配置us6)
- [Phase 8: BindCore 绑核 — 单条删除（补 FR-006）](#phase-8-bindcore-绑核--单条删除补-fr-006)
- [FR ↔ Task Traceability](#fr--task-traceability)

---

## Phase 1: 数据模型 + 解析引擎

### T001 — dataclass 数据模型 *(P1)*
- [x] `FreqRow`: 温度等级、触发温度、Gold/Prime/GPU 上下限+索引、游戏名、包名、模式名
- [x] `ClusterInfo`: cluster 名称 + 频率列表
- [x] `GameScene`: 游戏名 + 场景列表
- [x] `StrategyItem`: 策略节点（tag、key-value pairs、sync_df 标记）
- [x] `PushRecord`: 推送记录（游戏、包名、模式、备注、时间、数据、json_path）
- [x] `XmlErrorContext`: 错误行号、列号、上下文行
- **依赖**: 无

### T002 — GamePerfParser 核心解析 *(P1)*
- [x] `parse(xml_path)` → 返回解析结果（clusters、scenes、freq_rows: list[FreqRow]）
- [x] 解析 PreEnv → CPU clusters（Gold/Prime）、GPU cluster
- [x] 解析 BaseInfo → game_scenes
- [x] 解析 GamePolicy → modes、TempLevel → FreqRow 列表
- [x] 索引 → Hz 转换逻辑
- [x] 编码容错（errors="replace"）
- **依赖**: T001

### T003 — GamePerfParser 编辑能力 *(P1)*
- [x] `update_freq_index(row_label, cluster, new_index)` → 更新 XML DOM + 反算 Hz
- [x] `update_temperature(row_label, new_temp)` → 更新 XML DOM
- [x] `apply_strategy_edit(dom, mode, attr, value)` → 策略 Key/Value 写回
- [x] `save_as(path)` → 将修改后的 XML 写入文件
- [x] `write_to_path(path)` → 保存到指定路径（push 前用）
- **依赖**: T002

### T004 — GamePerfParser 策略面板数据 *(P1)*
- [x] `get_game_level_data(package)` → 整体策略 list[StrategyItem]
- [x] `get_mode_level_data(package, mode)` → 性能模式策略 list[StrategyItem]
- [x] BindCore 增删子项：`add_bindcore_row(bind_root)`, `remove_subtree(element)`
- [x] PerfHint 特殊结构提取
- [x] `_sync_mode_fields_to_freq_rows()` 同步 ThermalSceneCode/PerfHint 到频率行
- **依赖**: T002

---

## Phase 2: 推送/还原服务层

### T005 — GamePerfService 推送流程 *(P1)*
- [x] `push(serial, config_file, on_progress)` 完整推送
- [x] XML 格式校验（xml.etree.ElementTree.parse）→ `XmlErrorContext`
- [x] 读取设备 version（`head -5` + 正则）
- [x] version 递增（临时副本修改）
- [x] 使用框架 `AdbManager.root()` + `AdbManager.remount()` (smart remount)
- [x] 备份设备配置到 `data/backups/{serial}/`
- [x] `AdbManager.push()` 推送
- [x] `AdbManager.reboot()` + `wait_for_device` + `wait_boot_completed`
- [x] version 校验
- **依赖**: T001

### T006 — GamePerfService 还原流程 *(P1)*
- [x] `reset(serial, on_progress)` 从备份恢复
- [x] 读取设备 version → 修改备份 version → push → reboot → 校验
- [x] 无备份时抛出明确异常
- **依赖**: T005

### T007 — 推送记录双写 *(P2)*
- [x] JSON 文件保存（按游戏包名建文件夹、时间戳命名）
- [x] DB 写入 `perf_push_history` 表（game, package, mode, notes, version, json_path, timestamp）
- [x] DB 迁移脚本 `src/migrations/001_create_push_history.sql`
  > 实现方式：Schema 在 plugin.py on_startup 中内联创建，未使用独立 SQL 文件
- **依赖**: T005

### T008 — GamePerfService 辅助方法 *(P1)*
- [x] `get_device_version(serial)` → int
- [x] `get_info(serial)` → dict（版本、配置文件路径等）
- [x] `has_backup(serial)` → bool
- **依赖**: 无

---

## Phase 3: CLI 命令

### T009 — perf push 命令 *(P2)*
- [x] `perf push <file>` → 调用 service.push()
- [x] 进度回调输出 rich 格式日志
- [x] 设备未连接时提示
- **依赖**: T005

### T010 — perf reset 命令 *(P2)*
- [x] `perf reset` → 调用 service.reset()
- **依赖**: T006

### T011 — perf info 命令 *(P2)*
- [x] `perf info` → 调用 service.get_info() 输出 rich table
- **依赖**: T008

---

## Phase 4: GUI Tab 页

### T012 — 配置文件选择区域 *(P1)*
- [x] QFrame + QLineEdit + QPushButton（浏览）
- [x] 拖拽支持（dragEnterEvent + dropEvent），仅接受 gameperfconfig*.xml
- [x] 文件名校验：包含 "gameperfconfig" 且 .xml 后缀
- **依赖**: 无

### T013 — 游戏/模式过滤 + 另存为 *(P1)*
- [x] QComboBox × 2（游戏、模式）+ QPushButton（另存为）；推送备注不在主界面，见 Phase 7 Start 弹窗
- [x] 切换游戏时更新模式列表
- [x] 切换模式时刷新频率表和策略面板
- **依赖**: T002

### T014 — 频率配置表 *(P1)*
- [x] QTableWidget（11 列），从 parser 返回的 list[FreqRow] 填充
- [x] Gold/Prime/GPU 下限、上限为 QComboBox（PreEnv 全量频率，滚轮选取），变更后 `update_freq_index` 并刷新索引列
- [x] 触发温度、索引列可编辑；cellChanged → parser → 刷新
- **依赖**: T002, T003

### T015 — 频率参考列表 *(P1)*（已移除侧栏）
- [x] ~~3× QTextEdit 侧栏~~ 已删除；频率档位仅在 T014 表内上下限下拉展示（与 PreEnv 一致）
- **依赖**: T002

### T016 — 策略面板 *(P1)*
- [x] QTabWidget（整体策略 / 性能模式策略）
- [x] 按 XML 节点分组，Key/Value 可编辑表单
- [x] BindCore 特殊布局：增删行按钮
- [x] PerfHint 特殊布局：id/time 并排 + opcode 数据行
- [x] editingFinished 信号 → 调用 parser 编辑方法
- **依赖**: T004

### T017 — 执行日志 + 进度条 *(P1)*
- [x] QTextEdit（只读）+ QProgressBar + 百分比 QLabel
- [x] XML 错误高亮（红色加粗 + 暗红背景）
- [x] 上下文行灰色等宽字体
- **依赖**: 无

### T018 — 操作按钮 *(P1)*
- [x] Start（推送）、Clear（清除）、Reset（还原）
- [x] QThread 包装 service 调用
- [x] 设备未连接时禁用 Start/Reset
- [x] push 前写回修改到原文件
- [x] 「重置修改」按钮：重载文件并保持当前游戏/模式选择
- **依赖**: T005, T006, T012

### T019 — 主题适配 *(P1)*
- [x] `set_theme()` 方法
- [x] 颜色适配深色/浅色模式
  > 实现方式：全局 QSS 主题（styles.py）统一处理，无需模块级 set_theme()
- **依赖**: T012-T018

---

## Phase 5: 插件集成

### T020 — plugin.py 更新 *(P1)*
- [x] on_startup 初始化 GamePerfParser（延迟）、GamePerfService
- [x] 注册 CLI 命令
- [x] 注册 GUI Tab
- [x] 填充 context 字典
- **依赖**: T009-T011, T012-T019

---

## Phase 6: 测试 + 回归验证

### T021 — test_parser.py *(P1)*
- [x] 测试 PreEnv 解析（CPU/GPU clusters）
- [x] 测试 GamePolicy 解析（modes、TempLevel、FreqRow）
- [x] 测试索引编辑 → Hz 反算
- [x] 测试另存为 XML
- [x] 测试编码容错
- **依赖**: T002-T004

### T022 — test_service.py *(P1)*
- [x] 测试 push 完整流程（mock AdbManager）
- [x] 测试 reset 流程
- [x] 测试 XML 格式校验
- [x] 测试 version 读取/递增
- [x] 测试 JSON + DB 双写
- **依赖**: T005-T008

### T023 — test_cli.py *(P2)*
- [x] 测试 perf push/reset/info 命令
- **依赖**: T009-T011

### T024 — 回归测试 *(P1)*
- [x] 运行全量测试（主项目 + device_disguise + game_perf），确保无回归
- **依赖**: T021-T023

---

## Phase 7: 连接后自动载入设备配置（US6）

### T025 — 数据模型：文档来源与自动拉取结果 *(P1)*
- [x] `models.py`：`GamePerfDocumentOrigin`、`AutoDevicePullResult`（或等价命名）与 spec Key Entities 对齐
- **依赖**: 无

### T026 — Service：从设备读取 gameperfconfig *(P1)*
- [x] `GamePerfService.pull_device_config_from_device` → `AutoDevicePullResult`（含 `local_path`、失败 `failure_kind`）；错误分类满足 FR-015
- **依赖**: T025, T008

### T027 — GUI：触发时机 + 进度 + 来源展示 *(P1)*
- [x] `on_devices_changed`（序列号变化时）与 `on_activated`（进入 Tab 且尚未加载时）触发 `pull_device_config_from_device`；`QThread` 后台执行；执行日志展示进度
- [x] **FR-017**：自动拉取进行中显示「取消」按钮，置位 `threading.Event` 在各 adb 步骤间隙中止（单次 adb 阻塞内无法打断）
- [x] 配置文件区「来源：设备 / 本地文件」标签（FR-014）；失败仅写日志，不阻塞 Tab（FR-015）
- [x] **Start 推送**：点击 Start 先弹出**必填备注**对话框（预填上次成功提交的备注缓存），取消则不推送
- **依赖**: T026, T012

### T028 — 未保存编辑与自动拉取冲突 *(P1)*
- [x] `_document_dirty` + 自动拉取前 `QMessageBox` 确认（放弃并从设备载入 / 保留本地）（FR-016、US6）
- **依赖**: T027

### T029 — 测试 *(P2)*
- [x] `test_service.py`：mock AdbManager 覆盖成功、不存在/权限/非法 XML、`cancel_event` 取消（见 `TestPullDeviceConfig`）
- [x] GUI：无 pytest-qt；**手测** — ① 有未保存编辑时连设备须弹窗且不静默覆盖 ② 自动拉取时点「取消」须出现已取消日志 ③ Start 须弹备注框且空备注无法确定推送
- **依赖**: T026-T028

---

## Phase 8: BindCore 绑核 — 单条删除（补 FR-006）

**背景**：策略面板中 BindCore 已有「+ 添加」与「× 删除整块」（`remove_subtree` 删整个 `BindCore` 根）。**缺少**删除**单条**子节点（如单个 `tid` 行）的能力，与 **FR-006「动态增删子项」** 不完整对齐。

**独立验收**：加载含多行 BindCore 子项的 XML → 删除其中一行 → 仅该行从 DOM 消失，BindCore 块与其它键值仍在；保存/推送前 XML 结构合法。

- [x] T030 [P] [US1] 在 `modules/game_perf/src/parser.py` 实现 `remove_bindcore_child(child_el: _Element) -> bool`：校验 `child_el.getparent()` 为 `BindCore`；`parent.remove(child_el)` 后 `_refresh_game_policy()`；不得用于删除 BindCore 根节点本身
- [x] T031 [US1] 在 `modules/game_perf/src/gui_tab.py` 的 `_append_strategy_block` 中，对 `is_bindcore` 分支内每一行 `p["dom"]`（StrategyItem 子元素）增加「删除此行」控件，连接 `_on_bindcore_remove_row`（调用 `parser.remove_bindcore_child`）；成功后 `_refresh_strategy()`；可选 `QMessageBox` 确认以免误触
- [x] T032 [P] [US1] 在 `modules/game_perf/tests/test_parser.py` 增加用例：含多个同名子 tag 的 BindCore，`remove_bindcore_child` 删除其一后剩余子节点数量与标签正确

**依赖**：T004（已有 `add_bindcore_row` / `remove_subtree`）、T016（BindCore 布局）

**并行**：T030 与 T032 可同时开工（parser + 测试）；T031 依赖 T030。

---

## FR ↔ Task Traceability

| FR | 任务 |
|----|------|
| FR-001 | T002 |
| FR-002 | T002, T014 |
| FR-003 | T003, T014 |
| FR-004 | T003 |
| FR-005 | T004, T016 |
| FR-006 | T004, T016, **T030, T031**（单条删除） |
| FR-007 | T004, T016 |
| FR-008 | T005 |
| FR-009 | T005, T017 |
| FR-010 | T006 |
| FR-011 | T009, T010, T011 |
| FR-012 | T005, T006, T017, T018 |
| FR-013 | T026, T027 |
| FR-014 | T025, T027 |
| FR-015 | T026, T027 |
| FR-016 | T028 |
| FR-017 | T027 |
| FR-018 | T026（复用既有解析/校验） |
