# test_buffer_rates

## 目录

- [功能概述](#功能概述)
- [参数说明](#参数说明)
- [使用示例](#使用示例)
- [返回值与错误](#返回值与错误)

## 功能概述

本脚本在已连接的 Android 设备上，针对多组 **atrace categories** 和 **ftrace events** 配置分别进行固定时长（默认 10 秒）的 Perfetto 抓取，统计每组配置下 trace 文件的**实际大小**与**数据速率**（总 KB/s、按 tag 均摊的 KB/s）。用于校准 buffer 自动计算公式中的经验参数（`LIGHT_RATE_KB_PER_SEC`、`HEAVY_PER_CAT_RATE_KB`）。

脚本内置多档测试：
- 纯 atrace 组：仅 `sched`、3 个 category、7 个 category（推荐默认）、19 个 category（近似全选）
- 混合组：atrace + ftrace events 组合，验证 ftrace 对负载的影响

测试完成后自动打印 `HEAVY_PER_CAT_RATE_KB` 和 `LIGHT_RATE_KB_PER_SEC` 建议值。

**设备序列号自动检测**：脚本通过 `adb devices` 自动检测已连接的设备序列号。仅有一台设备时自动选取；多台或无设备时退出并提示。

**pbtxt 模板同步**：脚本内置的 `PBTXT_TEMPLATE` 与模块 `service.py` 中 `build_pbtxt_config` 的输出保持一致，包含 `flush_period_ms`、`incremental_state_config`、`builtin_data_sources { primary_trace_clock: BUILTIN_CLOCK_BOOTTIME }`、`compact_sched` 等配置。修改模块 pbtxt 生成逻辑时需同步更新本脚本模板。

## 参数说明

本脚本**无命令行参数**，行为由源码顶部常量控制，修改后重新运行即可：

| 常量 | 含义 | 默认值（以源码为准） |
|------|------|----------------------|
| `DURATION_SEC` | 每次抓取持续时间（秒），之后向 perfetto 进程发 `SIGTERM` | `10` |
| `DEVICE_DIR` | 设备上 trace 输出目录 | `/data/misc/perfetto-traces` |
| `BUFFER_KB` | TraceConfig 中主 ring buffer 大小（KB），用于避免抓取被 buffer 截断 | `262144`（256 MB） |

设备序列号由 `detect_serial()` 自动检测，无需手动配置。

Perfetto 通过 `perfetto --background --txt -c - -o <设备路径>` 启动，配置由内存中的 **pbtxt 模板** 生成（含 `linux.ftrace`、`linux.process_stats`、`android.packages_list` 等 data source）。

## 使用示例

在项目根目录执行：

```bash
python scripts/test_buffer_rates.py
```

典型输出包括：每组测试的标签、category/ftrace 列表、PID、文件大小（MB）、总速率（KB/s）、每 tag 速率（KB/s）；最后汇总表及「建议公式参数」段落。

## 返回值与错误

- **进程退出码**：脚本未显式调用 `sys.exit`，正常结束为 **0**；若子进程异常导致未捕获异常则可能非 0。
- **设备检测错误**：无设备或多设备连接时，脚本打印提示信息并退出。
- **控制台与逻辑错误**：
  - 无法从 `perfetto --background` 输出中解析 PID 时，该组返回字典中含 `"error": "no PID"`，汇总行显示 `ERROR`。
  - `stat` 取文件大小失败时会尝试 `ls -l` 并可能将大小记为 `0`。
- **设备侧**：每组结束后会删除设备上的临时 trace 文件；请保证应用对 `/data/misc/perfetto-traces` 有写权限（与常规模块抓取前提一致）。
