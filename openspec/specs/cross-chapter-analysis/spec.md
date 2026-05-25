# cross-chapter-analysis Specification

## Purpose
TBD - created by archiving change perfetto-skill-report-system. Update Purpose after archive.
## Requirements
### Requirement: Root cause deduplication

The system SHALL deduplicate root causes that represent the same underlying issue observed from different analysis perspectives.

When two candidate root causes share the same root mechanism (e.g., both attributed to "dequeueBuffer buffer queue congestion"), they SHALL be merged into a single root cause entry with combined evidence from all observing chapters.

#### Scenario: Same root cause from GPU and FPS chapters

- **WHEN** GPU chapter reports "dequeueBuffer 934次, 单次最大等待 31.6ms" AND FPS chapter reports "Frame#846 间隔 32.86ms, 疑似根因 dequeueBuffer 等待"
- **THEN** these are merged into one root cause: "dequeueBuffer buffer queue congestion"
- **AND** the combined evidence references both the GPU metric (934 calls, max 31.6ms) and the FPS metric (Frame#846, 32.86ms)

### Requirement: Root cause severity ranking

The system SHALL rank root causes by severity using the following priority:
1. Cross-chapter confirmed (strong correlation) — CRITICAL/HIGH
2. Single-chapter with threshold violation — MEDIUM
3. Single-chapter without threshold violation — LOW/INFO

#### Scenario: Severity ranking with cross-chapter confirmation

- **WHEN** a root cause has strong evidence from both GPU chapter (dequeueBuffer 31.6ms) and FPS chapter (32.86ms frame interval)
- **THEN** its severity is ranked at least MEDIUM
- **AND** it is listed above single-chapter findings

### Requirement: Conclusion generation from cross-chapter analysis

The system SHALL generate a structured conclusion containing:
- `overall_rating` — synthesized from all chapter severity levels
- `summary` — a concise paragraph integrating key findings across chapters
- `highlights` — positive findings (e.g., stable FPS, low CPU usage)
- `risks` — concerns requiring attention
- `recommendations` — actionable optimization suggestions

#### Scenario: Conclusion for a well-performing game trace

- **WHEN** fps chapter shows 97.9% target hit rate, cpu chapter shows 20.5% main thread usage, gpu chapter shows minor dequeueBuffer outliers
- **THEN** `overall_rating` is "优秀"
- **AND** `highlights` include "60fps 全程稳定" and "CPU 占用健康"
- **AND** `risks` include "dequeueBuffer 偶发等待导致 3 帧 >25ms"
- **AND** `recommendations` suggest investigating the specific frames with long dequeueBuffer waits

