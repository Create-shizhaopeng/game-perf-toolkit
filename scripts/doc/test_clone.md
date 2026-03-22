# test_clone

## 目录

- [功能概述](#功能概述)
- [参数说明](#参数说明)
- [使用示例](#使用示例)
- [返回值与错误](#返回值与错误)

## 功能概述

本脚本验证 Android 设备上 **Perfetto 分离会话（`--detach`）** 与 **`--clone-by-name`（按会话名克隆快照）** 是否可用于「无间隙」或多次快照场景。流程概要：

1. 使用带 `unique_session_name`、`write_into_file` 等字段的 TraceConfig，通过 `perfetto --detach=<key> --txt -c - -o ...` 启动后台会话；
2. 等待一段时间后执行 `perfetto --clone-by-name <会话名> -o <快照路径>`，检查返回码与生成文件大小；
3. 再次等待后重复 clone，观察第二次快照；
4. 使用 `perfetto --is_detached=<key>` 检查会话是否仍分离存在；
5. 使用 `perfetto --attach=<key> --stop` 停止原始会话；
6. 清理设备上的临时 pb/trace 文件。

用于开发阶段确认 **detach / clone** 与产品 TraceConfig（尤其 `write_into_file`）是否匹配。相关踩坑见 `scripts/doc/development-pitfalls.md` 中 Perfetto 条目。

## 参数说明

本脚本**无命令行参数**，关键常量如下：

| 常量 | 含义 |
|------|------|
| `SERIAL` | `adb` 目标设备序列号（须自行改为本机设备） |
| `DEVICE_DIR` | 设备上输出目录，默认 `/data/misc/perfetto-traces` |
| `DETACH_KEY` | `--detach=` 与 `--is_detached=` / `--attach=` 共用的键 |
| `BUFFER_KB` | TraceConfig 主 buffer 大小（KB） |
| `PBTXT` | 含 `unique_session_name: "test_clone_session"`、`write_into_file: true`、`file_write_period_ms` 等 |

若设备上会话名或路径与脚本不一致，需同步修改 `PBTXT` 与 `perfetto --clone-by-name` 后的名称。

## 使用示例

```bash
python scripts/test_clone.py
```

观察各步骤打印的 `stdout` / `stderr` / `returncode`，以及 clone 成功时的快照文件大小（MB）。

## 返回值与错误

- **退出码**：`main()` 在 **detach 启动失败**（`returncode != 0`）时直接 `return`，进程退出码为 **0**（未使用非零码表示失败）。其它步骤失败仅打印日志，仍可能以 0 退出。
- **clone 失败**：若第一次 `--clone-by-name` 非 0，脚本会打印提示并仍继续后续等待与第二次 clone（与「尝试 `--clone`」的说明性输出一致，实际 fallback 需自行扩展脚本）。
- **环境**：需保证设备可执行 `perfetto` 且对输出路径可写；若存在 **会话数达到上限**，需先在设备上清理残留 `perfetto` 进程（见开发踩坑文档）。
