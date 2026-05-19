# Tasks: 设备伪装模块移植

## 目录

- [Phase 1: 数据模型](#phase-1-数据模型)
- [Phase 2: 服务层核心](#phase-2-服务层核心)
- [Phase 3: CLI 命令](#phase-3-cli-命令)
- [Phase 4: GUI 页面](#phase-4-gui-页面)
- [Phase 5: 插件集成](#phase-5-插件集成)
- [Phase 6: 测试](#phase-6-测试)
- [FR ↔ Task Traceability](#fr--task-traceability)

---

## Phase 1: 数据模型

### T001 — 定义 DeviceProfile 模型 *(P1)* ✅
- [x] 在 `modules/device_disguise/src/models.py` 创建 `DeviceProfile(BaseModel)` 模型
- 字段：`brand`, `manufacturer`, `model`, `notes`（可选）
- 方法：`unique_key()` 返回 `brand|manufacturer|model` 小写拼接
- **依赖**: 无

### T002 — 实现 ProfileManager *(P2)* ✅
- [x] 在 `modules/device_disguise/src/models.py` 实现 `ProfileManager`
- JSON 文件读写（原子写入，tempfile + replace）
- CRUD 方法：`get_all`, `exists`, `find`, `add`, `update`, `delete`
- `import_from(path)` 批量导入，返回 `{"imported": N, "skipped": M}`
- 存储路径：`modules/device_disguise/config/device_info.json`（见 specs/002-device-info-json）
- **依赖**: T001

---

## Phase 2: 服务层核心

### T003 — 实现 get_device_state *(P1)* ✅
- [x] `DeviceDisguiseService.get_device_state(serial)` → `DeviceState`
- 通过 `AdbManager.get_device_props(serial)` 获取 ODM 和 vendor 属性
- 填充 `DeviceState` 并返回
- **依赖**: 无（使用 SDK 已有模型）

### T004 — 实现 _modify_build_prop *(P1)* ✅
- [x] 静态方法 `modify_build_prop(path, props)` 修改 build.prop 文件
- 已有键替换值，缺失键追加到末尾
- 保持 UTF-8 编码
- **依赖**: 无

### T005 — 实现 _wait_boot_completed *(P1)* ✅
- [x] `_wait_boot_completed(serial, timeout)` 轮询 `sys.boot_completed`
- 使用 `AdbManager.get_prop("sys.boot_completed", serial)`
- 超时抛出 `AdbError`
- **依赖**: 无

### T006 — 实现 disguise 方法 *(P1)* ✅
- [x] `DeviceDisguiseService.disguise(serial, brand, manufacturer, model, on_progress=None)`
- 流程：root → remount → setenforce 0 → pull build.prop → modify → push → reboot → wait_for_device → wait_boot_completed → verify
- 每个步骤通过 `on_progress(message)` 回调通知
- 验证成功返回 `DeviceState`，验证失败抛出异常（包含期望值和实际值）
- **依赖**: T004, T005

### T007 — 实现 reset 方法 *(P1)* ✅
- [x] `DeviceDisguiseService.reset(serial, on_progress=None)`
- 先获取 vendor 属性作为还原目标，然后复用 `_execute_modify` 逻辑
- 设备未伪装时提前返回提示
- **依赖**: T003, T006

---

## Phase 3: CLI 命令

### T008 — 实现 device status 命令 *(P1)* ✅
- [x] `device status` 显示设备连接状态和伪装信息
- 使用 `rich.table` 格式化输出
- 支持 `--serial` 参数指定设备
- **依赖**: T003

### T009 — 实现 device disguise/reset 命令 *(P1)* ✅
- [x] `device disguise --brand X --manufacturer Y --model Z [--serial S]`
- [x] `device reset [--serial S]`
- 进度信息通过 `typer.echo` 输出
- **依赖**: T006, T007

### T010 — 实现 device profile 子命令 *(P2)* ✅
- [x] `device profile list` — 列出所有档案
- [x] `device profile add --brand X --manufacturer Y --model Z [--notes N]` — 添加档案
- [x] `device profile import --file path.json` — 导入档案
- **依赖**: T002

---

## Phase 4: GUI 页面

### T011 — 创建 DeviceDisguiseTab 基础布局 *(P1)* ✅
- [x] 方案 A 左右分栏：左侧操作区 / 右侧日志区
- 使用 `QSplitter` 分割，比例 45:55
- 继承 `BaseTab`，设置 `tab_title = "设备伪装"`
- **依赖**: 无

### T012 — 实现设备状态显示区 *(P1)* ✅
- [x] 显示当前设备品牌/厂商/型号
- 显示伪装状态（已伪装/未伪装）
- 使用状态指示器样式（绿色/灰色圆点）
- **依赖**: T003, T011

### T013 — 实现伪装输入区 *(P1)* ✅
- [x] 三个 `QComboBox`（editable）+ `QCompleter` 联想
- 联想数据来源于 `ProfileManager` 中的档案
- 选中联想项时联动填充其他字段
- 输入为空时禁用伪装按钮
- **依赖**: T002, T011

### T014 — 实现操作按钮和工作线程 *(P1)* ✅
- [x] 「伪装」按钮（主色调）和「还原」按钮
- 点击后在 `QThread` 中调用服务层方法
- 操作进行中按钮禁用，日志实时更新
- 完成/失败后更新设备状态和按钮状态
- **依赖**: T006, T007, T011

### T015 — 实现日志区域 *(P1)* ✅
- [x] `QTextEdit` 只读模式
- 每行带时间戳、成功绿色 ✓、失败红色 ✗
- 自动滚动到最新行
- **依赖**: T011

### T016 — 实现档案弹窗 *(P2)* ✅
- [x] 「选择档案」弹窗（搜索+列表+双击选取）
- 「保存档案」对话框（brand/manufacturer/model + notes 输入）
- 匹配主框架无边框风格
- **依赖**: T002, T011

---

## Phase 5: 插件集成

### T017 — 更新 plugin.py *(P1)* ✅
- [x] `on_startup` 中初始化 `DeviceDisguiseService`，传入 `AdbManager` 实例
- `register_gui_tab` 传递 context 包含 service 实例
- `register_agent_tools` 返回服务层方法的 JSON Schema
- **依赖**: T003-T007

### T018 — 创建初始档案文件 *(P3)* ✅
- [x] `modules/device_disguise/config/device_info.json` 档案库（002 迭代后替代 `device_profiles.json`）
- **依赖**: 无

---

## Phase 6: 测试

### T019 — 服务层单元测试 *(P1)* ✅
- [x] `tests/test_service.py` 测试 `get_device_state`（mock ADB 返回属性）— 2 测试
- [x] 测试 `disguise`（mock 所有 ADB 步骤，验证调用顺序和参数）— 2 测试
- [x] 测试 `reset`（mock ADB，验证使用 vendor 属性还原）— 2 测试
- [x] 测试 `modify_build_prop`（实际文件读写，验证替换和追加）— 3 测试
- **依赖**: T003-T007

### T020 — 模型测试 *(P2)* ✅
- [x] `tests/test_models.py` 测试 `DeviceProfile.unique_key()` — 3 测试
- [x] 测试 `ProfileManager` CRUD 操作 — 8 测试
- [x] 测试 `ProfileManager.import_from` 批量导入 — 2 测试
- [x] 测试持久化和损坏文件处理 — 2 测试
- **依赖**: T001, T002

### T021 — CLI 测试 *(P2)* ✅
- [x] `tests/test_cli.py` 测试 `device status` 输出 — 2 测试
- [x] 测试 `device disguise` 参数传递 — 1 测试
- [x] 测试 `device reset` — 1 测试
- [x] 测试无设备时退出 — 1 测试
- **依赖**: T008-T010

### T022 — 运行全部测试验证 *(P1)* ✅
- [x] 执行 `pytest modules/device_disguise/tests/ -v` — 30 passed in 0.32s
- [x] 主项目回归测试 `pytest tests/ -v` — 100 passed in 0.74s
- **依赖**: T019-T021

### T023 — GUI 手动验证 *(P1)* ✅ (待用户验收)
- [x] 启动应用，设备伪装 Tab 正确加载（日志确认）
- [ ] 用户验证输入联想、按钮交互、日志显示（手动）
- **依赖**: T011-T016

---

## FR ↔ Task Traceability

| FR | 任务 | 说明 |
|----|------|------|
| FR-001 | T003 | get_device_state 方法 |
| FR-002 | T006 | disguise 方法 |
| FR-003 | T007 | reset 方法 |
| FR-004 | T006, T007, T014 | 进度回调 on_progress |
| FR-005 | T002 | ProfileManager CRUD |
| FR-006 | T002 | import_from 方法 |
| FR-007 | T004 | _modify_build_prop 替换/追加 |
| FR-008 | T011-T015 | GUI 伪装界面 |
| FR-009 | T013 | QComboBox + QCompleter 联想 |
| FR-010 | T016 | 保存对话框 |
| FR-011 | T008-T010 | CLI 命令 |
| FR-012 | T006, T007 | 通过 AdbManager API |
