# ADB Perfetto 支持扩展 — 规格说明

## 目录

- [背景与目标](#背景与目标)
- [功能需求](#功能需求)
- [验收标准](#验收标准)
- [非目标](#非目标)

## 背景与目标

### 背景

perfetto_capture 模块需要通过 ADB 向设备端的 `perfetto` 命令传递 pbtxt 配置文本（通过 stdin），
当前 AdbManager 的 `_run_cmd_raw()` 不支持 `input_text` 参数，`shell()` 方法只返回 stdout 字符串
而不返回完整的执行结果（returncode、stderr），无法满足 Perfetto 抓取的错误处理需求。

### 目标

扩展 AdbManager 提供两项新能力，使 perfetto_capture 模块能够复用 toolkit 核心的 ADB 基础设施，
而无需维护独立的 ADB 实现。

## 功能需求

### FR-001: _run_cmd_raw 支持 stdin 输入

- `_run_cmd_raw()` 新增 `input_text: str | None = None` 参数
- 当 `input_text` 不为 None 时，将其编码为 UTF-8 通过 `subprocess.run` 的 `input` 参数传递
- 与 `capture_output=True` 兼容（`input` 参数替代 `stdin=PIPE`，需改用独立的 `stdout=PIPE, stderr=PIPE`）
- 默认值为 None，不影响任何现有调用

### FR-002: shell_raw 方法

- 新增 `shell_raw(serial, command, *, input_text=None, timeout=30) -> AdbCmdResult` 方法
- 等效于 `_run_cmd_raw(["-s", serial, "shell", command], input_text=input_text, timeout=timeout)`
- 返回 `AdbCmdResult`（含 stdout、stderr、returncode），**不** 自动抛异常
- 调用方根据 returncode 和 stderr 自行判断成功/失败

## 验收标准

| ID | 标准 | 类型 |
|----|------|------|
| SC-001 | `_run_cmd_raw` 在 `input_text=None` 时行为与修改前完全一致 | 回归 |
| SC-002 | `_run_cmd_raw` 在 `input_text="test"` 时正确将 stdin 传入子进程 | 功能 |
| SC-003 | `shell_raw` 返回 `AdbCmdResult` 且不抛异常 | 功能 |
| SC-004 | 现有 180 项测试全部通过 | 回归 |

## 非目标

- 不修改 `shell()` 的现有签名和行为
- 不修改 `run_cmd()` 的行为
- 不添加 Perfetto 业务逻辑到 AdbManager
