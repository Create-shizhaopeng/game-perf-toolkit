# 模块注册表

## 目录

- [模块前缀注册表](#模块前缀注册表)
- [EventBus 事件注册表](#eventbus-事件注册表)
- [模块依赖关系](#模块依赖关系)

## 模块前缀注册表

所有模块的 `context` 键名 MUST 使用以下前缀，避免跨模块键名冲突（参考 P01）。

| 模块 | 前缀 | 示例键名 | manifest 类别 |
|------|------|---------|--------------|
| device_disguise | `dd_` | `dd_service`, `dd_adb` | device |
| game_perf | `gp_` | `gp_service`, `gp_adb` | perf |
| perfetto_capture | `pe_` | `pe_service`, `pe_adb` | perfetto |
| perfetto_analysis | `pa_` | `pa_service`, `pa_engine` | analysis |
| perfdog_insights | `pdi_` | `pdi_service` | perfdog |
| agent_chat | `ac_` | `ac_service`, `ac_llm` | agent |

**注意**：`pe_`（perfetto_capture）与 `pa_`（perfetto_analysis）容易混淆，编码时需特别留意。

## EventBus 事件注册表

| 事件名 | 发布者 | 订阅者 | 说明 |
|--------|--------|--------|------|
| `device_disguise.state_changed` | device_disguise | — | 设备伪装状态变更 |
| `perfetto_capture.trace_ready` | perfetto_capture | perfetto_analysis | Trace 抓取完成，文件已就绪 |

## 模块依赖关系

```text
perfdog_insights → device_disguise (设备信息)
perfdog_insights → perfetto_capture (性能数据)
perfetto_analysis ← perfetto_capture (事件驱动：trace_ready)
```
