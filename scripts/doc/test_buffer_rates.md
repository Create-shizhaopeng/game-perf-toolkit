# test_buffer_rates

## 目录

- [功能概述](#功能概述)
- [参数说明](#参数说明)
- [使用示例](#使用示例)
- [返回值与错误](#返回值与错误)

## 功能概述

本脚本在已连接的 Android 设备上，针对多组 **atrace categories** 配置分别进行固定时长（默认 10 秒）的 Perfetto 抓取，统计每组配置下 trace 文件的**实际大小**与**数据速率**（总 KB/s、按 category 均摊的 KB/s）。用于校准 buffer 自动计算公式中的经验参数（如「仅 sched」基准速率、每增加一个 category 的增量速率等）。

脚本内置多档测试：仅 `sched`、3 个 category、7 个 category（推荐默认）、以及 19 个 category（近似全选），并在全部成功时打印 `base_rate`、`per_category_rate` 等建议参考值。

**依赖**：本机已安装 `adb`，设备已 USB 调试连接；脚本中 **设备序列号** 为硬编码常量，需与当前环境一致。

## 参数说明

本脚本**无命令行参数**，行为由源码顶部常量控制，修改后重新运行即可：

| 常量 | 含义 | 默认值（以源码为准） |
|------|------|----------------------|
| `SERIAL` | `adb -s` 目标设备序列号 | 需在脚本中改为你的设备 |
| `DURATION_SEC` | 每次抓取持续时间（秒），之后向 perfetto 进程发 `SIGTERM` | `10` |
| `DEVICE_DIR` | 设备上 trace 输出目录 | `/data/misc/perfetto-traces` |
| `BUFFER_KB` | TraceConfig 中主 ring buffer 大小（KB），用于避免抓取被 buffer 截断 | `262144`（256 MB） |

Perfetto 通过 `perfetto --background --txt -c - -o <设备路径>` 启动，配置由内存中的 **pbtxt 模板** 生成（含 `linux.ftrace`、`linux.process_stats`、`android.packages_list` 等 data source）。

## 使用示例

在项目根目录执行（请先按实际设备修改 `SERIAL`）：

```bash
python scripts/test_buffer_rates.py
```

典型输出包括：每组测试的标签、category 列表、PID、文件大小（MB）、总速率（KB/s）、每 category 速率（KB/s）；最后汇总表及「建议公式参数」段落。

## 返回值与错误

- **进程退出码**：脚本未显式调用 `sys.exit`，正常结束为 **0**；若子进程异常导致未捕获异常则可能非 0。
- **控制台与逻辑错误**：
  - 无法从 `perfetto --background` 输出中解析 PID 时，该组返回字典中含 `"error": "no PID"`，汇总行显示 `ERROR`。
  - `stat` 取文件大小失败时会尝试 `ls -l` 并可能将大小记为 `0`。
- **设备侧**：每组结束后会删除设备上的临时 trace 文件；请保证应用对 `/data/misc/perfetto-traces` 有写权限（与常规模块抓取前提一致）。
