# test_duration_verify

## 目录

- [功能概述](#功能概述)
- [参数说明](#参数说明)
- [使用示例](#使用示例)
- [返回值与错误](#返回值与错误)

## 功能概述

本脚本用于在**修正 buffer 大小**（或其它公式）之后，通过多轮抓取验证 **trace 文件体量与「估算时长」** 是否与预期一致。每一轮使用相同的 TraceConfig（固定的一组 atrace categories 与 buffer 配置），但 **停止前等待时间** 不同（例如 10、20、30、45 秒），停止后对输出文件做 `stat`，并基于假定速率 **1386 KB/s** 反推「估算时长」，与根据等待时间推导的「期望时长」对比打印，便于人工判断 ring buffer / 截断行为是否符合预期。

说明：仓库内脚本顶部的文档字符串可能提到「30 秒」等表述，**以源码中的 `DURATION_SEC` 与循环中的 `wait_sec` 列表为准**。

## 参数说明

本脚本**无命令行参数**，由源码常量驱动：

| 常量 | 含义 | 说明 |
|------|------|------|
| `SERIAL` | 设备序列号 | 须改为当前 `adb devices` 中的目标机 |
| `DEVICE_DIR` / `DEVICE_PATH` | 设备上目录与单文件路径 | 默认在 `perfetto-traces` 下固定文件名 |
| `DURATION_SEC` | 期望覆盖的「目标时长」阈值 | 用于与 `wait_sec` 比较，决定 `expected_sec` 取 `wait_sec` 还是封顶为 `DURATION_SEC` |
| `BUFFER_KB` | 主 ring buffer 大小（KB） | 与产品侧修正公式一致时使用（示例中为 22050） |
| 循环 `wait_sec` | 各轮抓取持续时间 | 源码中为 `[10, 20, 30, 45]`，可改 |

估算公式在脚本中为：`estimated_duration = file_size / 1024 / 1386`（单位秒），**1386** 为写死的假定总速率（KB/s），若校准参数变更需同步改脚本。

## 使用示例

```bash
python scripts/test_duration_verify.py
```

每轮输出：等待秒数、PID、文件大小、估算时长、期望时长。全部轮次结束后会删除设备上的临时文件。

## 返回值与错误

- **退出码**：未显式 `sys.exit`，正常为 **0**。
- **失败分支**：解析不到 perfetto PID 时打印错误并 `continue` 下一轮；`stat` 失败时打印并跳过该轮。
- **解读注意**：本脚本**不**解析 perfetto trace 内部时间戳，仅根据文件大小与固定速率做粗算，用于辅助验证 buffer 与时长关系；精确时长需用 Perfetto UI 或其它工具打开 trace 核对。
