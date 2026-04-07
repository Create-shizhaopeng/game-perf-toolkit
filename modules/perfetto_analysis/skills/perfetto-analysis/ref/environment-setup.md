# 环境准备参考

## 目录

- [user+root 方法](#userroot-方法)
- [特殊 trace 抓取](#特殊-trace-抓取)
  - [重启场景 trace](#重启场景-trace)
  - [GPU trace event](#gpu-trace-event)
  - [ftrace IO 配置](#ftrace-io-配置)
- [常用配置文件](#常用配置文件)

---

## user+root 方法

user 版本获取 root 权限的流程：

1. 解锁 bootloader：
```bash
adb reboot bootloader
fastboot getvar all  # 检查解锁状态
```

2. 如果未解锁，参照"联想项目客制化 bootloader 解锁 SOP"编译 `unlock.img`：
```bash
fastboot flash unlock <unlock.img>
fastboot oem unlock
# 平板屏幕出现确认提示，5 秒内按音量下键确认
fastboot reboot
```

3. 刷入 debug vendor_boot：
```bash
fastboot flash vendor_boot vendor_boot-debug.img
fastboot reboot
```

4. 验证：`adb root` 应返回成功。

---

## 特殊 trace 抓取

### 重启场景 trace

标准 Perfetto/Systrace 抓取方法在重启后会断开连接。重启场景需使用专用脚本，确保 trace 跨越重启过程不中断。

抓取完成后从 `keyguardgoingaway` tag 开始分析。

### GPU trace event

MTK 平台需额外启用 GPU event：
```bash
adb shell "echo 1 > /sys/module/ged/parameters/ged_log_perf_trace_enable"
```

### ftrace IO 配置

分析 IO Block 问题需要在 trace 抓取配置（`config.pbtx`）中添加文件系统和块设备事件：

```
ftrace_events: "f2fs/f2fs_sync_file_enter"
ftrace_events: "f2fs/f2fs_sync_file_exit"
ftrace_events: "f2fs/f2fs_write_begin"
ftrace_events: "f2fs/f2fs_write_end"
ftrace_events: "f2fs/f2fs_readpage"
ftrace_events: "f2fs/f2fs_readpages"
ftrace_events: "f2fs/f2fs_sync_fs"
ftrace_events: "block/block_rq_issue"
ftrace_events: "block/block_rq_complete"
ftrace_events: "block/block_rq_insert"
```

> 需同时抓取 f2fs 和 block 层事件，才能完整定位 IO 问题。详细分析流程见 [io-block-analysis.md](sop/io-block-analysis.md)。

---

## 常用配置文件

| 文件 | 用途 |
|------|------|
| `singleBuffer_whitelist.txt` | 单帧模式白名单（笔写优化） |
