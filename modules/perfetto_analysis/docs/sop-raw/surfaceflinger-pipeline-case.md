# 性能问题案例分享 — SurfaceFlinger 耗时

> 来源: https://thundersoft.feishu.cn/file/boxcnA5MwIqpoO1ZzsSceofvQze
> 格式: PowerPoint (7 slides)
> 转写时间: 2026-04-01
> 状态: 原始文档（未加工）
> 分类建议: 知识参考 → patterns/ 或 ref-rendering-pipeline.md

## 目录

- [App 侧一帧的渲染流程（Vsync-App）](#app-侧一帧的渲染流程vsync-app)
- [SurfaceFlinger 侧一帧的流程（Vsync-sf）](#surfaceflinger-侧一帧的流程vsync-sf)
- [HWComposer 部分](#hwcomposer-部分)
- [案例分析](#案例分析)
  - [案例 1：launcher 帧渲染与 GPU completion](#案例-1launcher-帧渲染与-gpu-completion)
  - [案例 2：SF 合成与 HWC binder 耗时](#案例-2sf-合成与-hwc-binder-耗时)
  - [案例 3：HWC 超时](#案例-3hwc-超时)

## App 侧一帧的渲染流程（Vsync-App）

Trace 中关注的线程：UI thread（主线程）、RenderThread

完整一帧流程（7 步）：

1. **等待 Vsync 信号**：主线程处于 Sleep 状态

2. **Vsync-App 到达**：主线程被唤醒，Choreographer 回调 `FrameDisplayEventReceiver.onVsync` 开始一帧的绘制

3. **处理 Input 事件**：处理 App 这一帧的 Input 事件（如果有的话）

4. **处理 Animation**：处理 App 这一帧的 Animation 事件（如果有的话）

5. **处理 Traversal**：处理 App 这一帧的 Traversal 事件（如果有的话）

6. **主线程与 RenderThread 同步**：主线程与渲染线程同步渲染数据。同步结束后主线程结束一帧的绘制，可以继续处理下一个 Message（如果有），IdleHandler 如果不为空也会触发，或者进入 Sleep 等待下一个 Vsync

7. **RenderThread 渲染**：
   - 从 BufferQueue 取一个 Buffer（`dequeueBuffer`）
   - 调用 OpenGL 相关函数执行渲染
   - 将渲染好的 Buffer 还给 BufferQueue（`queueBuffer`）
   - SurfaceFlinger 在 Vsync-SF 到了之后取出所有准备好的 Buffer 进行合成

**Trace 中的关键 slice**：
- 主线程：`Choreographer#doFrame`、`input`、`animation`、`traversal`
- RenderThread：`dequeueBuffer`、`DrawFrame`、`queueBuffer`

## SurfaceFlinger 侧一帧的流程（Vsync-sf）

Trace 中关注的进程：surfaceflinger

**SurfaceFlinger 进程中的关键泳道**：
- `FrameMissed` — 标记丢帧
- `GpuFrameMissed` — GPU 导致的丢帧
- `hasClientComposition` — 是否有 GPU 合成
- `HW_VSYNC_0` — 硬件 VSync 信号
- `HwcFrameMissed` — HWC 丢帧
- `Total Buffer Size` — buffer 总大小
- `VSYNC-app` — 应用 VSync
- `VSYNC-sf` — SF VSync

**SF 主线程主要处理两个 Message**：

1. `MessageQueue::INVALIDATE` — 执行 `handleMessageTransaction` 和 `handleMessageInvalidate`
2. `MessageQueue::REFRESH` — 执行 `handleMessageRefresh`

**Trace 中的关键 slice**：
- `onMessageReceived`
- `handleMessageRefresh`
- `HIDL::IComposerClient::executeCommands::client`
- `doComposition`
- `postComposition`

## HWComposer 部分

Hardware Composer HAL (HWC) 用于确定通过可用硬件来合成缓冲区的最有效方法。作为 HAL，其实现是特定于设备的，而且通常由显示设备硬件原始设备制造商 (OEM) 完成。

**Trace 中的流程**：
1. SurfaceFlinger 进程通过 binder 调用 HWC
2. HWC 处理结果通过 binder 回到 SurfaceFlinger 继续处理

关注的线程：
- `surfaceflinger`（主线程）
- `HwBinder:S10_1` 等 HwBinder 线程
- `android.hardware.graphics.composer` 服务进程中的 `HwBinder` 线程

## 案例分析

### 案例 1：launcher 帧渲染与 GPU completion

Trace 中可观察到 launcher 应用（m.oppo.launcher）的帧渲染流程：

- `Frames` 泳道下的 `m.oppo.launcher` 显示每帧的起止和状态
- `RenderThread` 显示渲染耗时
- `GPU completion` 轨道显示 GPU 完成帧渲染的时间
- `HWC release` 轨道显示 HWC 释放 buffer 的时间

当 RenderThread 出现异常耗时（红色标注 `RenderThread耗时!`），会导致帧超时。

**关注指标**：
- HWUI CPU Memory / HWUI Texture Memory 的变化
- GPU completion 是否及时
- Purgeable HWUI 内存变化

### 案例 2：SF 合成与 HWC binder 耗时

Trace 中的 SurfaceFlinger 进程：
- `VSYNC-sf` 信号驱动 SF 每帧合成
- `surfaceflinger` 主线程中可看到 `onMessageRefresh`、`present`、`presentFrame`、`chooseCompositionStrategy`、`getDeviceCompositionChanges` 等 slice
- 通过 binder transaction 调用 HWC

**HWC binder 耗时**标注处：SF 发起 binder 调用到 app 进程的 `Binder:1116_1`，如果此 binder 耗时长，会导致 SF 合成延迟。

### 案例 3：HWC 超时

Trace 中的 HWC 服务进程 `vendor.qti.hardware.display.composer-service`：
- `HwBinder:1080_3` 线程处理 HWC 合成请求
- 可看到 `binder reply`、`HWCSession`、`HWCComposerClient`、`DisplayBufferCommit` 等 slice
- 当 HWC 处理耗时超过预算（标注 `HWC超时`），会导致帧未能在 VSync deadline 前完成合成

**HWC 流程关键 slice**：
- `HWCSession::CommitOrPrepare...`
- `HWCSession::PresentDisplay`
- `HWC::DisplayBufferCommit`
- `DisplayBufferCommit`
- `DRMAtomicReq::Commit`
