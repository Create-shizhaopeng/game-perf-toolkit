# Data Model: PerfDog 导入与性能洞察

**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## 运行时实体（Python dataclass / 等价）

### SessionSummary

| 字段 | 类型 | 说明 |
|------|------|------|
| package_name | str? | 包名，来自 `all` 首行/元数据区 |
| device_name | str? | 机型 |
| perfdog_version | str? | 如首行含 PerfDog(xxx) |
| record_started_at | str? | 原始字符串 |
| duration_ms | int? | 由 Data_v4 `time` max 或元数据推断 |
| target_fps_hint | int? | 由 FPS P95 或 Stat 推断 60/90/120/144 |

### MetricSample（逻辑行）

对应 `Data_v4` 一行（解析后列名规范化为内部 snake_case）。

| 字段 | 类型 | 说明 |
|------|------|------|
| index | int | 行号 |
| time_ms | float | 相对时间 |
| fps | float? | |
| smooth | float? | |
| jank_small / jank / jank_big | int? | 列存在则填 |
| stutter_pct | float? | |
| app_cpu_pct | float? | |
| total_cpu_pct | float? | |
| gpu_usage_pct | float? | GUsage |
| cpu_clocks_mhz | list[float]? | 多核 |
| gpu_clock_mhz | float? | |
| battery_temp | float? | BTemp |
| gpu_temp | float? | GTemp |
| power_mw | float? | |
| battery_level_pct | float? | |

*实际列随版本变化；解析层填充「已知映射」，其余进 `extras: dict`。*

### FrameStats（聚合）

由 `@FrameInfo` 计算，非逐帧存储在内存（大文件）。

| 字段 | 类型 | 说明 |
|------|------|------|
| count | int | |
| mean_ms / p99_ms / max_ms | float | |
| over_budget_count | int | 超 2×目标帧时间的帧数 |
| max_frame_time_ms | float | |
| max_frame_at_ms | float? | 对应 time 列 |

### ThreadTopEntry

| 字段 | 类型 | 说明 |
|------|------|------|
| thread_label | str | 列名或线程名 |
| mean_pct_in_window | float | |
| peak_pct_in_window | float | |

### Finding

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 稳定 id，如 `spike-34376` |
| category | enum | drop / stability / thermal / power / freq / thread |
| severity | enum | info / warn / critical |
| title | str | 展示标题 |
| detail | str | 说明文字 |
| time_start_ms | float? | |
| time_end_ms | float? | |
| evidence | dict | 关键数值快照 |

### Recommendation

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | |
| finding_ids | list[str] | **FR-007** 追溯 |
| text | str | 含「建议复测」类措辞 |
| category | str | 复现条件 / 采集建议 / 环境 |

### AnalysisReport（聚合根）

| 字段 | 类型 | 说明 |
|------|------|------|
| session | SessionSummary | |
| summary_metrics | dict | 摘要区键值 |
| findings | list[Finding] | |
| recommendations | list[Recommendation] | |
| frame_stats | FrameStats? | |
| thread_top | list[ThreadTopEntry]? | |
| compare_note | str? | A/B 警告文案 |
| stat_row_disclaimer | str? | Stat vs 重算 |

### SessionComparePair（二期）

| 字段 | 类型 |
|------|------|
| session_a / session_b | SessionSummary |
| delta_metrics | dict[str, tuple[Any, Any]] |
| aligned_columns | list[str] |
| warnings | list[str] |

## 校验规则（来自 spec）

- 无包名/无 Data_v4：解析失败，**FR-009** 友好错误。
- 应用不一致对比：**FR-012** 需确认标记。

## 状态（ImportJob）

| 状态 | 说明 |
|------|------|
| idle | |
| running | 显示加载 |
| success | 展示 AnalysisReport |
| failed | message + 可恢复 |

---

## 子特性：联合分析实体（Pydantic）

> 对应 [spec.md](./spec.md) **US9～US11**；实现建议放在 **`toolkit/sdk/joint_models.py`**。以下字段语义须保持一致。

### PolicySnapshot（策略快照）

从 **`gameperfconfig`** 解析结果中，针对选定 **`package_name` + `mode_name`** 抽取。

| 字段 | 类型 | 说明 |
|------|------|------|
| package_name | str | 包名 |
| mode_name | str | 性能模式名 |
| game_alias | str? | 展示用别名 |
| freq_rows | list[FreqPolicyRow] | 当前模式下各温档行的 Gold/Prime/GPU 上下限（Hz 或索引，实现须注释固定策略） |
| bindcore_summary | str? | BindCore 等 **人类可读摘要** |
| strategy_highlights | list[str] | 其他 CPU/GPU 调度相关要点 |
| source_xml_path | str? | 报告脚注，可选 |

#### FreqPolicyRow

| 字段 | 类型 |
|------|------|
| temp_level, trigger_temp | str |
| gold_min_hz, gold_max_hz, prime_min_hz, prime_max_hz, gpu_min_hz, gpu_max_hz | int? |
| gold_index, prime_index, gpu_index | str? |

### ObservationsSnapshot（观测快照）

从 **`AnalysisReport`** 派生。

| 字段 | 类型 | 说明 |
|------|------|------|
| package_name | str? | 来自 SessionSummary |
| duration_ms, target_fps_hint | int? | |
| metric_lines | list[str] | 可对比摘要行 |
| finding_summaries | list[FindingRef] | id + title + category |
| recommendation_summaries | list[RecRef] | id + 首句 |
| data_gaps | list[str] | 缺失说明（**JA-SC-004**） |

#### FindingRef / RecRef

| 字段 | 类型 |
|------|------|
| id | str |
| title_or_text | str |
| category | str |

### JointAssessmentReport

| 字段 | 类型 |
|------|------|
| policy_section, observation_section, consistency_section | list[str] |
| bindcore_suggestions, freq_suggestions | list[JointSuggestion] |
| bindcore_insufficient_reason, freq_insufficient_reason | str? |
| warnings | list[str] |
| disclaimer | str |

#### JointSuggestion

| 字段 | 类型 |
|------|------|
| id, text, basis | str |
| related_finding_ids | list[str]? |
| severity_hint | str |

### 联合分析 UI 状态

| 状态 | 说明 |
|------|------|
| idle / running / success / failed | 同 ImportJob 语义；success 时展示 `JointAssessmentReport` |
