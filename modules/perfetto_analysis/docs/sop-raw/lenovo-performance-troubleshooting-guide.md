# 联想整机性能问题处理指导

> 来源: https://thundersoft.feishu.cn/wiki/Tj43wVM1Wig0SlkGRpkc9iRbnLe
> 转写时间: 2026-04-01
> 状态: 原始文档（未加工）

## 目录

- [典型问题总结](#典型问题总结)
  - [一、点按 back 键返回场景](#一点按-back-键返回场景)
  - [二、点击 home 键返回场景](#二点击-home-键返回场景)
  - [三、笔写时延](#三笔写时延)
  - [四、启动响应时延分析](#四启动响应时延分析)
  - [五、旋转响应类问题](#五旋转响应类问题)
  - [六、重启解锁类问题](#六重启解锁类问题)
  - [七、应用安装速度类问题](#七应用安装速度类问题)
- [高通 GPU 调优](#高通-gpu-调优)
- [MTK 调优](#mtk-调优)
  - [CPU](#cpu)
  - [GPU](#gpu)
  - [DDR](#ddr)
  - [如何调试](#如何调试)
- [user+root 方法](#userroot-方法)
- [GC](#gc)

## 典型问题总结

### 一、点按 back 键返回场景

**【问题场景】**

相关问题单：OTOPAZV-2357

**【分析方法】**

具体 trace 流程如下：

1. **桌面 taskbar 接受点击事件并进行处理**

   Trace 中定位：在 launcher 进程中找到 `InputFlinger Taskbar touch` 事件，可看到 input 事件从 taskbar 进入并经过 `inputflinger` 分发到 launcher 的 main thread。触摸事件会在 launcher 的主线程泳道中产生对应的 slice。

2. **桌面处理完 action up 事件后通知 systemui 处理系统侧逻辑**

   桌面侧关键字：`android.view.ViewRootImpl$ViewRootHandler: android.view.View$PerformClick`

   搜到后找第二个异步 binder，点击可跳转至 systemui 相关流程

   Trace 中定位：在 launcher 主线程的 `PerformClick` slice 附近，可看到 binder thread 上的异步 binder 调用（红色连接线），该 binder 调用跳转到 systemui 进程。在 Perfetto UI 中点击该 binder 连接可直接跳转到 systemui 侧对应的处理流程。

3. **systemui 侧处理**

   关键字：`AIDL::java::ISystemUiProxy::#45::server`

   Trace 中定位：在 systemui 进程的 binder 线程中搜索此关键字，可找到一个绿色的 slice 标记 systemui 接收到 launcher 的回调。

4. **systemui 内部流程**（深究可根据 tracetag 看源码）

   Trace 中定位：在 systemui 主线程中可看到一系列内部处理 slice，包含 binder 调用到 system_server。深入分析时可展开 systemui 进程的各个线程（主线程、binder thread）查看具体耗时分布。

5. **systemui 通知 system_server 的 inputdispatcher 处理 input 事件**（结束当前应用进程，走到 activitypause）

   Trace 中定位：在 system_server 进程中查看 `inputdispatcher` 线程和 `InputManager` 相关线程。可看到从 systemui 的 binder 调用到达 system_server 后，`inputdispatcher` 开始处理 input inject 事件。同时可在 `focused app` 泳道（橙色条带）观察应用焦点变化。

6. **system_server 通知相关进程走 activitypause**（在哪个 app 页面点的返回就是通知哪个 app 走 activitypause）

   Trace 中定位：在 system_server 进程中可看到 `Default Workspace` 相关泳道和 binder reply 线程的活动。在目标 app 进程中可观察到 `activityPause` 相关 slice。同时 `Expected Timeline` 和 `Actual Timeline` 两条轨道可用于对比帧时序。

7. **activitypaused 之后拉起桌面 activityresume**

   Trace 中定位：在 launcher（com.zui.launcher）进程的主线程中可看到 `activityResume` 相关 slice。时间点紧随上一步 app 的 activityPause 完成之后。

8. **桌面 activityresume 之后绘制第一帧，绘制完后通知系统 finishdrawing**

   系统侧关键字：`finishDrawing: com.zui.launcher`

   Trace 中定位：在 launcher 进程中可看到 RenderThread 开始绘制帧（出现 drawFrame 相关 slice），绘制完成后在 system_server 中搜索 `finishDrawing: com.zui.launcher` 即可找到桌面通知系统绘制完成的时间点。

9. **系统收到 finishdrawing 消息后，走 transactionready 并回调桌面通知做返回动画**

   系统侧关键字：`onTransactionReady`
   桌面侧接受系统回调关键字：`AIDL::java::IRemoteTransition::startAnimation::server`

   Trace 中定位：在 system_server 中搜索 `onTransactionReady` 可找到系统准备好 transition 的时间点。随后通过 binder 回调到 launcher 进程，在 launcher 的 binder 线程中可看到 `AIDL::java::IRemoteTransition::startAnimation::server` slice，标记动画回调到达。

10. **桌面做动画**

    `AIDL::java::IRemoteTransition::startAnimation::server` 之后的第一帧为动画开始点。可通过桌面进程中的 animator 泳道定位动画范围。

    Trace 中定位：在 launcher 进程中查看 `animator` 泳道（专门显示动画相关事件的轨道），`startAnimation` 之后的第一帧上屏即为动画起始点。animator 泳道会标注动画持续的时间范围。

**点击返回键的响应时延**：起始点为 actionup 事件（抬手），终止点为动画第一帧上屏。可根据第 2 步中流程确认返回动画第一帧后再计算时延，trace 上看的时延与测试实际测试结果有误差，不可做为终版数据输出。

**可能的耗时点和问题点**

目前发现的与 oppo 的差异点：联想在第 2 步中的第（2）个流程时，是在 actionup 的时候才拉起 systemui，而 oppo 是在第一个 actiondown 的时候就拉起，相比联想时机更提前。

**【解决方案】**

流程问题暂无解决方案，尝试澄清。

---

### 二、点击 home 键返回场景

整体流程与 back 键完全一致。

相关问题单：OTOPAZV-2356

**可能的耗时点和问题点**

对比机 oppo 的 home 键流程与 back 不同，oppo 机器在桌面处理完 actionup 事件之后直接调用 ams 的 startactivityinner 流程，不再由系统侧处理上一个进程 pause 之后的流程发起，也就与联想的流程产生了差异。

Trace 中定位：oppo 的 trace 中可看到 launcher 在 actionup 之后直接通过 AMS 的 `startActivityInner` 流程拉起桌面，跳过了 systemui 中转步骤，使得整体链路更短。在 system_server 进程中搜索 `startActivityInner` 可观察到此差异。

---

### 三、笔写时延

**【问题现象】**

在云记、notein 等应用使用手写笔划线，有一定时延。参考问题单 OTOPAZV-4197。

**【分析方法】**

从 input 传入到画面上屏为完整的时延，具体 trace 流程如下：

1. **应用消费 input 事件**

   根据应用消费的 input id 在 inputreader 中找对应的 input 事件。

   Trace 中定位：在 Perfetto UI 左侧 Navigation 面板 → `Current Trace` 展开进程列表，找到目标应用。在应用主线程中定位 input 消费 slice，记录 input id，然后在 `inputreader` 线程中搜索对应 id 找到 input 事件的原始时间戳。

2. **应用完成绘制，buffer 队列 count+1**

   Trace 中定位：在目标应用的 buffer counter track 中可看到 buffer 队列深度的变化。应用 RenderThread 完成绘制后，buffer count 会 +1。此 counter 轨道直接显示数值变化。

3. **SF 消费 buffer**

   如果有 buffer 堆积，根据先进先出，当前绘制的 buffer 需要在下一个 vsync-sf 周期才会被消费。

   Trace 中定位：在 SurfaceFlinger 进程中查看 vsync-sf 信号和 buffer 消费时序。如果 buffer count > 1，说明存在堆积，当前帧需要等到下一个 vsync-sf 周期才被 SF 消费。buffer count 回到 0 的时间点即 SF 完成消费。

4. **SF 把合成好的画面给 hwc 上屏**

   Trace 中定位：在 SurfaceFlinger 进程中查看 HWC（Hardware Composer）合成完成的时间点。SF 将合成后的帧提交给 HWC 后，该帧在下一个 vsync 信号时上屏。从 input → 绘制 → SF 消费 → HWC 上屏的总耗时即为端到端时延。

最终的时延就是 inputreader 到一帧完成上屏中间的耗时加和。

**【解决方案】**

- 联想自研单帧方案，可以使 buffer 及时消费，缺点是与高通存在适配问题，第一帧会有一定耗时
  - 在 `singleBuffer_whitelist.txt` 中添加 activity 名
- 联想与部分应用存在合作协议，有专门的笔写预测方案

> [附件: 笔写预测方案.zip]

---

### 四、启动响应时延分析

**【问题现象】**

点击设置图标启动响应慢（点击后到图标开始放大做启动动画的速度慢）。

问题单：https://tbjira.lenovo.com/issue/browse/OTOPAZV-9744

**【分析方法】**

1. 根据 system_server 中的 `focused app` 泳道以及 launcher 的 `animator` tag 确认问题场景区间

   Trace 中定位：system_server 进程中 `focused app` 泳道（橙色/棕色条带）显示当前焦点应用名称和切换时间点。双向箭头标注的区间即为焦点从 launcher 切换到目标 app 再切回的时间窗口。launcher 进程中搜索 `animator` tag 可看到专门的动画泳道。

2. 根据 `AIDL::java::IRemoteTransition::startAnimation::server` 这个 tag 确认启动动画起始点

   Trace 中定位：在 launcher 进程的 binder 线程中搜索 `AIDL::java::IRemoteTransition::startAnimation::server`，找到该 slice 即为启动动画回调到达的时间点。此后 launcher 主线程开始绘制启动动画。

3. 从 `AIDL::java::IRemoteTransition::startAnimation::server` 开始，逐步往前看唤醒关系，最终推导至点击事件

   Trace 中定位：在 Perfetto UI 中，选中 `startAnimation` slice 后查看 waker 信息，逐级往前追踪唤醒链。每个阻塞状态的线程都可查看唤醒者（waker thread/process），通过连续追踪可还原完整的调用链：startAnimation → system_server transition → app pause → inputdispatcher → 点击事件。唤醒链在 UI 中表现为红色的连接箭头。

最终可以定位到本问题有两个主要耗时原因：

1. **startactivity system_server 侧 blockio 耗时严重**
2. **settings 热启动耗时严重**

**【解决方案】**

1. 关于 startactivity blockio 耗时严重：可以同步观察到 launcher 的 launcher-loader 线程也在同步读写文件，并且两个线程读写的都是同一个文件：`settings.apk`。startactivity 读应用 apk 是原生逻辑无法避免，所以可以从桌面侧考虑优化。

   参考：http://tbsc.lenovo.com:8080/485609

   原生的逻辑是每次点击启动的时候都通过 `getResources` 方法去从磁盘中拿应用的图标来做启动动画，优化后逻辑变为直接从 bubbletextview 中取图标即可，不再调用 `getResources` 方法，防止发生 blockio。

2. 热启动耗时问题根因在于 settings 点击启动后是由两个 activity 组成的，所以导致并不能直接使用 startingwindow 去做启动流程，需要应用第一帧真窗，所以需要等待一个热启动流程，这个无法避免，无优化方向。其余单 activity 的应用，都是 systemui 绘制完 startingwindow 就可以直接做启动动画，不存在此问题。

---

### 五、旋转响应类问题

**【问题现象】**

屏幕旋转速度响应慢。

问题单：https://tbjira.lenovo.com/issue/browse/OTOPAZV-3544

**【分析方法】**

1. 在 system_server 中找到 `transition` tag 和 `focused app` 泳道，确认转屏时当前所处的应用以及转屏动画的时间点

   Trace 中定位：system_server 中 `transition` 有独立泳道，显示转屏 transition 的起止时间。结合 `focused app` 泳道可确认转屏发生时的前台应用。两个泳道交叉定位即可确定转屏事件的时间窗口。

2. 上层判断需要进行转屏的关键字是 `updateGlobalConfiguration`，可以搜到后从此 tag 往前看唤醒逻辑。最终推导至 sensorservice 后，上层流程至此完成，再往前的流程就是硬件通知 sensorservice 做转屏。

   Trace 中定位：在 system_server 进程中搜索 `updateGlobalConfiguration` slice，从此 slice 开始往前追踪唤醒链（waker 关系），可看到多级跳转：system_server 内部线程 → AlarmManager/HandlerManager → sensorservice 进程。唤醒链终止于 sensorservice，说明转屏触发来自硬件传感器。

3. 从 `updateGlobalConfiguration` 到真正转屏动画出来，中间还有一段流程：当前转屏时处在最上层的应用自身的 configchange 流程，做完 configchange 并且绘制完第一帧画面后，通知系统做转屏动画。

   Trace 中定位：在前台应用进程中查看 configchange 相关 slice（通常在主线程），可看到应用处理配置变更的耗时。完成 configchange 后，应用的 RenderThread 会绘制新布局的第一帧，绘制完成后通知系统触发转屏动画。从 configchange 开始到第一帧完成的时间差即为应用侧耗时。

**【解决方案】**

查看转屏响应流程期间 CPU 频点是否拉满，若未拉满可以尝试进行拉满优化。

---

### 六、重启解锁类问题

**【问题现象】**

重启后首次解锁桌面有一段时间空白，解锁耗时长。

问题单：https://tbjira.lenovo.com/issue/browse/OTOPAZV-3759

**【分析方法】**

此类问题测试提供的 trace 一般不能用，因为原有的抓取方法在重启后会断开抓取，必须使用专用工具。

> [附件: 抓开机 trace.zip]

用上面工具抓取完 systrace 后，从 `keyguardgoingaway` 这个 tag 往前看唤醒逻辑即可。开机后如果首次快速解锁，解锁流程会被重启的一部分逻辑耗时阻塞，所以会有尝试间的空白，具体有如下几点：

1. **解锁之前需要等待存储管理服务初始化完成**，以及 HAL 准备完成，完成后回调 `onBootCompleted()` 后才可继续解锁流程，这部分有很多长 binder 耗时，主要耗时取决于硬件层的完成速度

   Trace 中定位：在 system_server 中搜索 `onBootCompleted` 可确定系统启动完成时间点。在此之前的 binder 调用中可看到存储管理服务和 HAL 初始化的耗时分布。

2. **解锁过程有部分长 binder 耗时**

   Trace 中定位：在 system_server 和 keyguard/systemui 进程之间的 binder 调用中查看长耗时 binder（>5ms），这些 binder 调用可能阻塞解锁流程。

3. **桌面初始化耗时**，插件、图标等绑定流程

   Trace 中定位：在 launcher 进程主线程中可看到桌面初始化相关 slice，包含插件绑定、图标加载等操作的耗时。如果桌面 widget 较多，此步骤耗时会显著增加。

**【解决方案】**

Topaz 项目上对比的是 realme 的机器，realme 有自研方案重启后会不受重启流程限制直接走解锁逻辑，所以会优于 Topaz，Topaz 使用的是原生逻辑未作变动。

此类问题如果不改解锁逻辑，整机性能侧无优化空间，按照如下思路进行澄清：

1. 重启后等待 2s，再进行解锁，这一步的目的是给重启流程一段时间让它自行走完，再去解锁看现象是否消失，若消失则证明只有重启后首次解锁会有问题，影响很小
2. 设置锁屏密码再去解锁，大多数用户都会有锁屏密码，锁屏密码解锁时也会给重启流程留出时间
3. 上述两个步骤做完后已经能澄清自身的耗时，再去与项目选区的对应对比机澄清差异即可

---

### 七、应用安装速度类问题

**【问题现象】**

安装速度慢。

问题单：https://tbjira.lenovo.com/issue/browse/OTOPAZV-3814

**【分析方法】**

看 packageinstaller 线程和 packagemanager 线程的状态。详见问题单上分析步骤。

**【解决方案】**

外销机器，测试前需要对齐谷歌商店版本并强制停止谷歌商店。

---

## 高通 GPU 调优

### 节点路径

```
/sys/class/kgsl/kgsl-3d0/
```

- `gpuclk` — 当前 GPU 频率
- `max_gpuclk` — 最大 GPU 频率
- `gpu_available_frequencies` — 可用的调频档位

### 如何调试

循环查看当前 GPU 频点脚本（每隔 100ms 输出一次）：

> [附件: GPU_CurFreq.py]

设置具体挡位（以设置 GPU 最低频率为例）：

```bash
echo 180000000 > /sys/class/kgsl/kgsl-3d0/min_gpuclk
```

> 注意：设置的值需要是 `gpu_available_frequencies` 中的档位，且如果设置的 `min_clock_mhz` 大于 `max_clock_mhz`，`max_clock_mhz` 优先生效。

> [附件: CPU_GPU_CurFreq.py]

---

## MTK 调优

### CPU

路径：`/sys/devices/system/cpu/cpu0/cpufreq`

固定 CPU 频率方法：

```bash
chmod 660 /sys/devices/system/cpu/cpufreq/policyX/scaling_max_freq
chmod 660 /sys/devices/system/cpu/cpufreq/policyX/scaling_min_freq
echo FREQ > /sys/devices/system/cpu/cpufreq/policyX/scaling_min_freq
echo FREQ > /sys/devices/system/cpu/cpufreq/policyX/scaling_max_freq
chmod 440 /sys/devices/system/cpu/cpufreq/policyX/scaling_max_freq
chmod 440 /sys/devices/system/cpu/cpufreq/policyX/scaling_min_freq
```

> 红色 X 是 cluster 首位，比如 1+3+4 架构需要每次都下发一次，三次分别对应不同的簇值。FREQ 是需要写入的具体频率值，按照每个簇的最大频率写入。

查看各个 CPU 簇的 CPU 频率是否有定成功：

```bash
cat /sys/devices/system/cpu/cpuX/cpufreq/cpuinfo_cur_freq
```

定 DRAM 频率：

```bash
echo 0 > /sys/kernel/helio-dvfsrc/dvfsrc_force_vcore_dvfs_opp
```

查看 DRAM 频率是否有定成功：

```bash
cat /sys/kernel/helio-dvfsrc/dvfsrc_dump
```

查看各个 CPU 核心的参数：

```bash
adb shell
echo "=== CPU Core Summary ===" && \
for cpu in /sys/devices/system/cpu/cpu[0-9]*; do \
  cat "$cpu/cpufreq/cpuinfo_max_freq" 2>/dev/null; \
done | sort | uniq -c | while read count freq; do \
  echo "Max Freq $(awk "BEGIN{printf \"%.2f\", $freq/1000000}") GHz cores: ${count}"; \
done && echo "" && echo "=== Per Core Details ===" && \
for cpu in /sys/devices/system/cpu/cpu[0-9]*; do \
  num=$(basename $cpu); \
  maxfreq=$(cat "$cpu/cpufreq/cpuinfo_max_freq" 2>/dev/null); \
  minfreq=$(cat "$cpu/cpufreq/cpuinfo_min_freq" 2>/dev/null); \
  echo "$num: Max $(awk "BEGIN{printf \"%.2f\", $maxfreq/1000000}") GHz, Min $(awk "BEGIN{printf \"%.2f\", $minfreq/1000000}") GHz"; \
done
```

### GPU

查看所有可用档位：

```
/proc/gpufreqv2
```

示例输出（TB711FU）：

```
[00] freq: 1612000, volt:  83125, vsram:  83125
[01] freq: 1612000, volt:  83125, vsram:  83125
...
[51] freq:  338000, volt:  51250, vsram:  75000
```

查看 GPU 挡位频率：

```bash
adb shell "cat /proc/gpufreqv2/stack_working_opp_table"
# 或
adb shell "cat /proc/gpufreqv2/gpu_working_opp_table"
```

设置最大 GPU 频率：

```bash
adb shell "echo 0 > /proc/gpufreqv2/fix_target_opp_index"
```

查看当前频率、挡位：

```bash
adb shell "cat /proc/gpufreqv2/gpufreq_status | grep 'STACK OPP'"
adb shell "cat /sys/module/ged/parameters/gpu_cust_boost_freq"
```

恢复默认设置（或重启）：

```bash
adb shell "echo -1 > /proc/gpufreqv2/fix_target_opp_index"
```

**trace 中打开 GPU 相关 event**

遇到 GPU 相关的 Performance/Power 问题时，需要在 Systrace 中查看 GPU 的实时频率以及 Loading 情况，需要打开 GPU Event。在 Systrace Process 5566 的表现中可查看。

执行如下指令后，再抓取 Systrace，搜索 process id 5566 即可（需要 root 权限）：

```bash
adb shell "echo 1 > /sys/module/ged/parameters/ged_log_perf_trace_enable"
```

### DDR

DDR 频点提满：

kernel-4.x：

```bash
# 0 代表档位，0 档是最高档
adb shell "echo 0 > /sys/devices/platform/10012000.dvfsrc/helio-dvfsrc/dvfsrc_req_ddr_opp"
```

kernel-5.x：

```bash
# 0 代表档位，0 档是最高档
adb shell "echo 0 > /sys/kernel/helio-dvfsrc/dvfsrc_force_vcore_dvfs_opp"
```

查看 DRAM OPP Table（所有支持的频点档位）：

```bash
# 所有可用档位以及对应的具体频点
adb shell "cat /sys/kernel/helio-dvfsrc/dvfsrc_opp_table"
```

查看当前 DDR 频率：

```bash
adb shell "cat /sys/kernel/helio-dvfsrc/dvfsrc_dump | grep -e uv -e khz"
```

### 如何调试

MTK perflock 使用方法链接：https://online.mediatek.com/apps/quickstart/QS00265#QSS02859

具体的应用实例可参考：GPU、CPU 提频（详见 MTK perflock 官方文档中的提频配置示例）。

---

## user+root 方法

执行以下命令：

```bash
adb reboot bootloader
fastboot getvar all
```

如果显示未解锁状态，需要参照"联想项目客制化 bootloader 解锁 SOP"文档进行解锁。

按照文档编译出 `unlock.img` 后执行以下命令：

```bash
fastboot flash unlock xxxxxxxx_oem_unlock.img  # 你下载的 unlock.img
fastboot oem unlock
# 平板的屏幕出现小字，5 秒内按音量下键确认
fastboot reboot
```

然后查看是否已经解锁成功：

```bash
adb reboot bootloader
fastboot getvar all
```

解锁成功后继续执行 user+root 操作：

```bash
fastboot flash vendor_boot vendor_boot-debug.img
fastboot reboot
```

---

## GC

一个 Java 进程只有一个堆内存空间，进程下面的所有线程各自有一个线程自己的栈内存空间，这个进程的所有线程共享一个堆内存空间。

内存模型：堆（Heap）为进程级共享，所有线程共用一个堆；栈（Stack）为线程私有，每个线程有独立的栈空间。GC 发生在堆上，STW（Stop-The-World）暂停会影响所有线程。
