# Tasks: AdbManager 智能操作增强

## 目录

- [Phase 1: 基础设施](#phase-1-基础设施)
- [Phase 2: root 增强](#phase-2-root-增强)
- [Phase 3: smart remount](#phase-3-smart-remount)
- [Phase 4: 测试](#phase-4-测试)
- [FR ↔ Task Traceability](#fr--task-traceability)

---

## Phase 1: 基础设施

### T001 — 新增 AdbCmdResult 和 _run_cmd_raw *(P1)* ✅
- [x] 定义 `AdbCmdResult = NamedTuple("AdbCmdResult", [("stdout", str), ("stderr", str), ("returncode", int)])`
- [x] 实现 `_run_cmd_raw(args, timeout)` → `AdbCmdResult`，不抛异常，返回原始结果
- [x] 重构 `run_cmd` 内部调用 `_run_cmd_raw`，保持外部行为不变
- **依赖**: 无
- **完成**: `run_cmd` 向后兼容，113 个回归测试全通过

---

## Phase 2: root 增强

### T002 — root 方法增强 *(P1)* ✅
- [x] `root(serial)` 执行后检查输出：
  - "already running as root" → 跳过等待，直接返回
  - "restarting adbd as root" → `time.sleep(2)` + `wait_for_device(serial, timeout=30)`
  - "cannot run as root" → 抛出 `AdbError`，提示 userdebug/eng
- **依赖**: T001
- **完成**: 3 个测试用例覆盖三种分支

---

## Phase 3: smart remount

### T003 — 重写 remount 方法 *(P1)* ✅
- [x] `remount(serial, on_progress=None)` 新签名，保持向后兼容
- [x] 使用 `_run_cmd_raw` 执行 remount，同时检查 stdout + stderr 中的 "reboot" 关键词
- [x] 需要重启时：reboot → wait_for_device → wait_boot_completed → root → 再次 remount
- [x] 第二次 remount 仍需重启时：不循环，抛出 `AdbError` 提示 `disable-verity`
- [x] 每个步骤通过 `on_progress` 回调通知
- **依赖**: T001, T002
- **完成**: 完整 smart remount 流程实现，6 个测试用例覆盖

### T004 — _needs_reboot_for_remount 检测方法 *(P1)* ✅
- [x] 静态方法，检查输出文本中是否包含重启提示
- [x] 关键词：`"reboot"` + `("remount" | "take effect" | "overlayfs" | "settings")`
- **依赖**: 无
- **完成**: 2 个专项测试验证检测逻辑

### T005 — _wait_boot_completed 方法 *(P1)* ✅
- [x] 轮询 `getprop sys.boot_completed`，值为 "1" 时返回
- [x] 超时抛出 `AdbError`
- 注：device_disguise 模块中相同方法可移除，统一使用 AdbManager 的
- **依赖**: 无
- **完成**: 公开方法 `wait_boot_completed` + 内部 `_wait_boot_completed` 兼容

---

## Phase 4: 测试

### T006 — _run_cmd_raw 测试 *(P1)* ✅
- [x] 测试正常返回 stdout/stderr/returncode
- [x] 验证 `run_cmd` 行为不变（向后兼容）
- **依赖**: T001
- **完成**: 4 个测试（TestRunCmdRaw）全通过

### T007 — root 增强测试 *(P1)* ✅
- [x] 测试 "restarting adbd" → 等待 wait_for_device
- [x] 测试 "already running as root" → 跳过等待
- [x] 测试 "cannot run as root" → 抛出 AdbError
- **依赖**: T002
- **完成**: 3 个测试（TestRootEnhanced）全通过

### T008 — smart remount 测试 *(P1)* ✅
- [x] 测试无需重启 → 直接成功
- [x] 测试需要重启 → 自动 reboot + re-root + re-remount
- [x] 测试两次都需要重启 → 抛出 AdbError (disable-verity)
- [x] 测试 stderr 中的 reboot 提示也被检测
- [x] 测试 on_progress 回调收到正确消息
- **依赖**: T003
- **完成**: 6 个测试（TestSmartRemount）全通过

### T009 — 回归测试 *(P1)* ✅
- [x] 运行主项目全部 113 个测试，验证向后兼容
- **依赖**: T006-T008
- **完成**: 113 passed, 0 failed (0.74s)

---

## FR ↔ Task Traceability

| FR | 任务 |
|----|------|
| FR-001 | T001 |
| FR-002 | T002 |
| FR-003 | T003 |
| FR-004 | T003, T004 |
| FR-005 | T003 |
| FR-006 | T003 |
| FR-007 | T002 |
| FR-008 | T001 (run_cmd 重构) |
