# 提交信息模板

## 目录

- [格式](#格式)
- [字段说明](#字段说明)
- [示例](#示例)

## 格式

```text
[Toolkit.<module>.<action>][(<step>/<total>)]{<简要描述>}
适用范围:{<模块/ALL>}
准入id:{<需求ID/NA>}
分析:{<变更原因与分析>}
方案:{<实现方案概述>}
风险及影响[快/稳/省/功能/安全隐私]:{<风险评估>}
测试建议:{<测试要点>}
跨组依赖(topic name):{<依赖说明/无>}
```

## 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `module` | 模块标识 | `device_disguise`、`game_perf`、`core`、`gui` |
| `action` | 操作类型 | `feat`、`fix`、`refactor`、`docs`、`test` |
| `step/total` | 多步提交的进度 | `(1/3)`、`(1/1)` |
| `简要描述` | 一句话概括变更 | `新增 ADB remount 重试逻辑` |
| `适用范围` | 影响范围 | `device_disguise`、`ALL` |
| `准入id` | 关联的需求/缺陷 ID | `SPEC-003`、`NA` |
| `分析` | 变更原因 | `首次 remount 需要重启后再次执行` |
| `方案` | 实现方案 | `AdbManager.remount 添加输出解析与自动重试` |
| `风险及影响` | 五维度评估 | `功能: remount 流程变更`、`无` |
| `测试建议` | 测试要点 | `root 设备首次/二次 remount 验证` |
| `跨组依赖` | 是否需要其他模块配合 | `无`、`toolkit.core` |

## 示例

```text
[Toolkit.core.feat][(1/1)]{AdbManager 新增智能 remount 重试}
适用范围:{ALL}
准入id:{SPEC-003}
分析:{首次 remount 启用 overlayfs 需重启后再次执行，旧逻辑不处理此场景}
方案:{解析 remount 输出，识别 "reboot" 关键字后自动重启并二次 remount}
风险及影响[快/稳/省/功能/安全隐私]:{功能: 新增设备重启步骤，需确保设备可正常重启}
测试建议:{root 设备首次/二次 remount、非 root 设备提示}
跨组依赖(topic name):{无}
```
