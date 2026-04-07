# 设备性能调优速查

## 目录

- [高通平台](#高通平台)
  - [GPU](#gpu)
- [MTK 平台](#mtk-平台)
  - [CPU](#cpu)
  - [GPU](#gpu-1)
  - [DDR](#ddr)
  - [Perflock](#perflock)
- [Trace 中的 GPU 事件](#trace-中的-gpu-事件)

本文档为性能分析的辅助参考，用于分析过程中需要验证硬件频率/性能是否为瓶颈时的快速查询。

---

## 高通平台

### GPU

节点路径：`/sys/class/kgsl/kgsl-3d0/`

| 节点 | 说明 |
|------|------|
| `gpuclk` | 当前 GPU 频率 |
| `max_gpuclk` | 最大 GPU 频率 |
| `gpu_available_frequencies` | 可用档位 |
| `min_gpuclk` | 最低 GPU 频率（可写） |

设置最低频率（验证 GPU 是否为瓶颈）：

```bash
echo 180000000 > /sys/class/kgsl/kgsl-3d0/min_gpuclk
```

注意：设置值必须是 `gpu_available_frequencies` 中的档位。

---

## MTK 平台

### CPU

路径：`/sys/devices/system/cpu/cpu0/cpufreq`

固定 CPU 频率（需对每个 cluster 分别设置）：

```bash
# X = cluster 首位 CPU 编号，FREQ = 目标频率
chmod 660 /sys/devices/system/cpu/cpufreq/policyX/scaling_max_freq
chmod 660 /sys/devices/system/cpu/cpufreq/policyX/scaling_min_freq
echo FREQ > /sys/devices/system/cpu/cpufreq/policyX/scaling_min_freq
echo FREQ > /sys/devices/system/cpu/cpufreq/policyX/scaling_max_freq
chmod 440 /sys/devices/system/cpu/cpufreq/policyX/scaling_max_freq
chmod 440 /sys/devices/system/cpu/cpufreq/policyX/scaling_min_freq
```

验证：`cat /sys/devices/system/cpu/cpuX/cpufreq/cpuinfo_cur_freq`

### GPU

查看可用档位：
```bash
adb shell "cat /proc/gpufreqv2/gpu_working_opp_table"
```

设置最高频率（0 = 最高档）：
```bash
adb shell "echo 0 > /proc/gpufreqv2/fix_target_opp_index"
```

恢复默认：
```bash
adb shell "echo -1 > /proc/gpufreqv2/fix_target_opp_index"
```

查看当前状态：
```bash
adb shell "cat /proc/gpufreqv2/gpufreq_status | grep 'STACK OPP'"
```

### DDR

提满 DRAM 频率（kernel-5.x）：
```bash
adb shell "echo 0 > /sys/kernel/helio-dvfsrc/dvfsrc_force_vcore_dvfs_opp"
```

查看 OPP Table：
```bash
adb shell "cat /sys/kernel/helio-dvfsrc/dvfsrc_opp_table"
```

查看当前频率：
```bash
adb shell "cat /sys/kernel/helio-dvfsrc/dvfsrc_dump | grep -e uv -e khz"
```

### Perflock

MTK perflock 文档：https://online.mediatek.com/apps/quickstart/QS00265#QSS02859

---

## Trace 中的 GPU 事件

MTK 平台启用 GPU event 后可在 Systrace/Perfetto 中查看 GPU 实时频率和 Loading：

```bash
adb shell "echo 1 > /sys/module/ged/parameters/ged_log_perf_trace_enable"
```

启用后抓取 trace，搜索 process id 5566 查看 GPU 相关数据（需 root 权限）。
