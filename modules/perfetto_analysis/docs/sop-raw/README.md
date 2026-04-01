# 团队原始 SOP 文档

此目录存放团队提供的原始分析 SOP 文档（未加工版本）。

加工后的 Agent 友好版本存放在 `../../skills/perfetto-analysis/` 下对应子目录中。

## 目录

- [加工流程](#加工流程)
- [文档清单与加工状态](#文档清单与加工状态)

## 加工流程

1. 团队成员将原始 SOP 文档放入此目录
2. 加工处理：补充目录、结构化内容、增加工具映射、优化 Agent 可读性
3. 加工后的版本放入 `../../skills/perfetto-analysis/` 对应子目录（sop/、patterns/、cases/、ref/）

## 文档清单与加工状态

| 文档 | 来源 | 状态 | 加工产物 |
|------|------|------|----------|
| `lenovo-performance-troubleshooting-guide.md` | 飞书 wiki | ✅ 已加工 | `sop/response-latency.md`、`sop/input-latency.md`、`sop/startup-analysis.md`、`sop/rotation-analysis.md`、`ref/device-tuning.md`、`ref/environment-setup.md` |
| `io-block-analysis.md` | 飞书 docx | ✅ 已加工 | `sop/io-block-analysis.md`、`sql-patterns.md`(IO 部分)、`patterns/root-cause-patterns.md`(IO Block 模式)、`ref/environment-setup.md`(ftrace IO 配置) |
| `surfaceflinger-pipeline-case.md` | 飞书 pptx | ✅ 已加工 | `sop/jank-analysis.md`(SF 维度要点)、`sql-patterns.md`(SF/HWC 查询)、`patterns/root-cause-patterns.md`(HWC Binder 超时) |
| `face-unlock-audio-stutter.md` | 飞书 docx | ✅ 已加工 | `cases/face-unlock-audio-stutter.md`、`patterns/root-cause-patterns.md`(CPU 调度抢占) |
