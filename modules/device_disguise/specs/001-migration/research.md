# Research: 设备伪装模块移植

## 目录

- [技术决策](#技术决策)
- [旧代码分析](#旧代码分析)
- [迁移映射](#迁移映射)
- [Clarification 决策影响](#clarification-决策影响)

## 技术决策

### 服务层与 GUI 解耦

**决策**: service.py 纯同步，GUI 层用 QThread 包装。

**理由**: Constitution V 要求表现分离。旧代码 `DeviceService(QThread)` 违反此原则。新架构中 service.py 可被 CLI、Agent 直接调用，不受 GUI 线程限制。

**影响**: `disguise()` 和 `reset()` 接收 `on_progress: Callable[[str], None] | None` 回调，CLI 直接 print，GUI 通过 signal 转发。

### 档案存储

**决策**: 保持 JSON 文件存储。

**理由**: 旧版使用 JSON 存储运行良好，数据量小（通常 < 100 条），无需引入数据库复杂性。后续如需迁移到 SQLite，仅需修改 ProfileManager 内部实现。

**影响**: `ProfileManager` 使用原子写入（tempfile + os.replace）保证数据安全。

### ADB 操作方式

**决策**: 全部通过 `toolkit.core.adb_manager.AdbManager` 的封装方法调用。

**理由**: AdbManager 已在 Phase 0 扩展了 `root()`, `remount()`, `push()`, `pull()`, `reboot()`, `wait_for_device()`, `shell()` 方法，完全覆盖伪装流程所需。

**影响**: 旧代码中 `self._adb.run_cmd(["root"])` 替换为 `self._adb.root(serial)`。

### DeviceProfile 模型

**决策**: 使用 Pydantic BaseModel 替代 dataclass。

**理由**: 与项目整体技术栈一致（SDK 模型均使用 Pydantic），天然支持 JSON 序列化、验证、Schema 生成。

## 旧代码分析

### device_service.py 核心逻辑

1. `get_device_state()` — 读取 ODM/vendor 6 个属性，返回 DeviceState
2. `_execute_modify(props, action_name)` — 通用修改流程：root → remount → setenforce → pull → modify → push → reboot → wait → verify
3. `_modify_build_prop(path, props)` — 文件级属性修改：已有键替换，缺失键追加
4. `_wait_boot_completed(timeout)` — 轮询 sys.boot_completed

### profile_manager.py 核心逻辑

1. JSON 文件加载/保存（原子写入）
2. CRUD 操作（基于 unique_key 去重）
3. `import_from(path)` 批量导入

### 迁移要点

- QThread 信号 (`progress`, `error`, `finished_signal`) → 回调函数 `on_progress`
- 旧代码无 `serial` 参数（单设备）→ 新代码全部加 `serial` 参数（多设备）
- dataclass → Pydantic BaseModel
- 直接 `run_cmd()` → 使用 AdbManager 封装方法

## 迁移映射

| 旧代码 | 新代码 | 变更说明 |
|--------|--------|----------|
| `DeviceService(QThread)` | `DeviceDisguiseService` (纯 Python) | 移除 QThread 依赖 |
| `DeviceState` (dataclass) | `toolkit.sdk.models.DeviceState` (Pydantic) | 已迁移到 SDK |
| `DeviceProfile` (dataclass) | `DeviceProfile` (Pydantic BaseModel) | 模块内 models.py |
| `ProfileManager` | `ProfileManager` | 逻辑不变，路径调整 |
| `self._adb.run_cmd(["root"])` | `self._adb.root(serial)` | 使用封装方法 |
| `self.progress.emit(msg)` | `on_progress(msg)` | 信号→回调 |
| `self._adb.get_device_props()` | `self._adb.get_device_props(serial)` | 加 serial 参数 |

## Clarification 决策影响

| 决策 | 影响的任务 | 具体变化 |
|------|-----------|----------|
| 服务层同步 | T006, T007, T014 | service.py 不含 QThread；gui_tab.py 中创建 QThread Worker |
| JSON 存储 | T002, T018 | 使用 JSON 文件，不创建 SQLite migration |
| 本期不做历史 | T001 | DeviceProfile 不包含历史字段 |
| 方案 A 布局 | T011-T016 | 左右 QSplitter 分栏 |
| CLI 格式确认 | T008-T010 | device namespace 下的子命令 |
