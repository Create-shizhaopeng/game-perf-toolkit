# Implementation Plan: 经验淘汰与晋升 (G3)

**Branch**: `014-learning-eviction-promotion` | **Date**: 2026-04-13 | **Spec**: [spec.md](spec.md)

## 目录

- [Summary](#summary)
- [Technical Context](#technical-context)
- [Constitution Check](#constitution-check)
- [Project Structure](#project-structure)
- [Phase 0 Research](#phase-0-research)
- [Phase 1 Design](#phase-1-design)
  - [memory_score 评分引擎](#memory_score-评分引擎)
  - [淘汰流程 evict_low_score_learnings](#淘汰流程-evict_low_score_learnings)
  - [LLM 晋升流程 promote_learnings](#llm-晋升流程-promote_learnings)
  - [合并操作 merge_learnings](#合并操作-merge_learnings)
  - [自动触发集成](#自动触发集成)
  - [G2 检索适配](#g2-检索适配)
  - [CLI 入口](#cli-入口)
  - [遥测记录](#遥测记录)

## Summary

为防止 `pa_learnings` 经验库无限膨胀，实现基于 OpenClaw `memory_score = recency × importance × frequency` 公式的记忆价值评估。低分条目自动软删除归档，高分高频条目通过 LLM 评审晋升为"已验证"状态。晋升后的经验在 G2 检索中获得排序优势并标注 `[已验证]`。支持自动触发（每 20 次分析）和 CLI 手动触发。

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: pydantic-ai (LLM 调用)、sqlite3 (内置)、math/datetime (标准库)
**Storage**: SQLite (`pa_learnings` 现有表 + `pa_telemetry` 现有表)
**Testing**: pytest + unittest.mock
**Target Platform**: Windows + Linux (跨平台)
**Project Type**: 模块内功能扩展（perfetto_analysis 模块）
**Performance Goals**: 淘汰流程 < 5 秒（不含 LLM）
**Constraints**: 软删除、不阻塞分析、LLM 故障安全降级

## Constitution Check

| 原则 | 状态 | 说明 |
|------|------|------|
| Plugin-First | PASS | 变更在 `modules/perfetto_analysis/` 内完成 |
| Three-Surface Unity | PASS | 核心逻辑在 service/agent 层，CLI 仅做调用入口 |
| Presentation Separation | PASS | service.py 不含 GUI/CLI 代码 |
| Open-Closed | PASS | 不修改 `toolkit/` 目录 |
| Spec-Driven | PASS | 遵循 specify → clarify → plan → tasks → implement 流程 |
| Encoding | PASS | 所有输出 UTF-8 |

## Project Structure

### Source Code (变更范围)

```text
modules/perfetto_analysis/
├── src/
│   ├── agent/
│   │   ├── learnings_manager.py   # [新建] memory_score + evict + promote + merge
│   │   ├── learnings_search.py    # [修改] L1 SQL 增加 promoted DESC 排序
│   │   └── orchestrator.py        # [修改] analyze_single 末尾集成自动触发
│   └── engine/
│       └── storage.py             # [修改] 可选: 新增 telemetry 辅助查询函数
├── src/
│   └── cli_commands.py            # [修改] 新增 review-learnings 子命令
└── tests/
    └── test_g3_eviction_promotion.py  # [新建] G3 单元测试
```

## Phase 0 Research

### R1: memory_score 公式验证

**Decision**: 直接采用 OpenClaw `recency × importance × frequency` 公式
**Rationale**: 已在之前的讨论中与用户确认，公式参数先用 OpenClaw 默认值
**Alternatives**: 自定义加权公式 — 缺乏实验数据支撑，暂不采用

### R2: LLM 评审调用方式

**Decision**: 使用现有 `LLMManager` 获取模型，通过 pydantic-ai `Agent.run()` 执行评审
**Rationale**: 复用现有 LLM 基础设施，不引入新依赖
**Alternatives**: 直接 HTTP API 调用 — 会绕过现有模型管理和错误处理

### R3: 自动触发计数方式

**Decision**: 查询 `SELECT COUNT(*) FROM pa_telemetry` 取模 20（每行即一次完成的分析，无需 event_type 过滤）
**Rationale**: Clarify 阶段确认，复用现有基础设施，跨重启持久化
**Alternatives**: 内存计数器（重启丢失）、新表存储（过度设计）

## Phase 1 Design

### memory_score 评分引擎

```python
import math
from datetime import datetime

DECAY_FACTOR = 0.95
EVICT_THRESHOLD = 0.05
MIN_RETAIN_COUNT = 20
COOLDOWN_DAYS = 7

def memory_score(learning: dict, now: datetime | None = None) -> float:
    now = now or datetime.now()
    last_access = learning.get("last_used") or learning["created_at"]
    if isinstance(last_access, str):
        last_access = datetime.fromisoformat(last_access)
    days_since = max((now - last_access).days, 0)

    recency = DECAY_FACTOR ** days_since
    importance = learning.get("confidence", 0.5)
    frequency = math.log(learning.get("hit_count", 0) + 1)

    return recency * importance * frequency
```

**设计要点**：
- `days_since` 取 `max(..., 0)` 防止时钟偏移导致负值
- `hit_count = 0` 时 `frequency = log(1) = 0`，score 必然为 0，但受冷却期保护（FR-004）
- 纯函数设计，无副作用，易于单元测试

### 淘汰流程 evict_low_score_learnings

```python
def evict_low_score_learnings(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("""
        SELECT id, confidence, hit_count, last_used, created_at
        FROM pa_learnings
        WHERE archived = 0
    """).fetchall()

    now = datetime.now()
    cooldown_cutoff = now - timedelta(days=COOLDOWN_DAYS)

    scored = []
    for row in rows:
        r = dict(row)
        created = datetime.fromisoformat(r["created_at"])
        if created > cooldown_cutoff:
            continue  # FR-004: 跳过冷却期内的记录
        r["_score"] = memory_score(r, now)
        scored.append(r)

    scored.sort(key=lambda x: x["_score"])

    total_active = len(rows)
    archived_count = 0
    for item in scored:
        if item["_score"] >= EVICT_THRESHOLD:
            break
        if total_active - archived_count <= MIN_RETAIN_COUNT:
            break  # FR-003: 最低保留 20 条
        conn.execute("UPDATE pa_learnings SET archived = 1 WHERE id = ?", (item["id"],))
        archived_count += 1

    conn.commit()
    return {"archived": archived_count, "remaining": total_active - archived_count}
```

**设计要点**：
- 按分数升序排列，从最低分开始淘汰
- 双重终止条件：分数达到阈值 OR 剩余不足最低保留数
- 冷却期保护：创建 7 天内的记录不参与淘汰评估

### LLM 晋升流程 promote_learnings

```python
PROMOTE_CANDIDATE_LIMIT = 10
PROMOTE_HIT_THRESHOLD = 3
PROMOTE_CONFIDENCE_THRESHOLD = 0.6

async def promote_learnings(
    conn: sqlite3.Connection,
    llm_manager: Any,
) -> dict:
    rows = conn.execute("""
        SELECT id, scene, root_cause_tags, insight, key_metrics,
               confidence, hit_count, last_used, created_at
        FROM pa_learnings
        WHERE promoted = 0 AND archived = 0
          AND hit_count >= ? AND confidence >= ?
    """, (PROMOTE_HIT_THRESHOLD, PROMOTE_CONFIDENCE_THRESHOLD)).fetchall()

    if not rows:
        return {"promoted": 0, "merged": 0, "archived": 0, "skipped": True}

    candidates = [dict(r) for r in rows]
    now = datetime.now()
    candidates.sort(key=lambda x: memory_score(x, now), reverse=True)
    candidates = candidates[:PROMOTE_CANDIDATE_LIMIT]

    prompt = _build_promotion_prompt(candidates)

    try:
        model = llm_manager.get_model()
        agent = Agent(model, output_type=list[PromotionAction])
        result = await agent.run(prompt)
        actions = result.output
    except Exception as e:
        logger.error("LLM promotion failed: %s", e)
        return {"promoted": 0, "merged": 0, "archived": 0, "error": str(e)}

    return _apply_promotion_actions(conn, actions, candidates)
```

**设计要点**：
- `PromotionAction` 为 Pydantic 模型，利用 pydantic-ai 的 `output_type` 解析
- LLM 失败时安全降级，返回零操作统计
- 候选数限制为 10，控制 LLM prompt 长度

### 合并操作 merge_learnings

```python
def _merge_learnings(conn: sqlite3.Connection, source_id: int, target_id: int) -> bool:
    if source_id == target_id:
        return False

    source = conn.execute(
        "SELECT hit_count, confidence FROM pa_learnings WHERE id = ?", (source_id,)
    ).fetchone()
    target = conn.execute(
        "SELECT hit_count, confidence FROM pa_learnings WHERE id = ?", (target_id,)
    ).fetchone()

    if not source or not target:
        return False

    new_hit = target["hit_count"] + source["hit_count"]
    new_conf = max(target["confidence"], source["confidence"])

    conn.execute(
        "UPDATE pa_learnings SET hit_count = ?, confidence = ? WHERE id = ?",
        (new_hit, new_conf, target_id),
    )
    conn.execute(
        "UPDATE pa_learnings SET archived = 1 WHERE id = ?", (source_id,),
    )
    conn.commit()
    return True
```

**设计要点**：
- 自引用合并（source == target）安全跳过
- 仅累加 `hit_count`、取 max `confidence`，insight 保留目标（Clarify 确认）
- 源条目标记 `archived = 1`（软删除）

### 自动触发集成

在 `orchestrator.py` 的 `analyze_single` 末尾（finalize 阶段）增加检查：

```python
async def _maybe_trigger_maintenance(self) -> None:
    conn = self._get_db_connection()
    if not conn:
        return

    count = conn.execute(
        "SELECT COUNT(*) FROM pa_telemetry"
    ).fetchone()[0]

    if count > 0 and count % 20 == 0:
        evict_result = evict_low_score_learnings(conn)
        promote_result = await promote_learnings(conn, self._llm_manager)
        _record_maintenance_telemetry(conn, "auto_20", evict_result, promote_result)
```

**设计要点**：
- 异步执行，不阻塞返回结果
- 仅在分析完成后检查，非定时轮询
- 遥测记录触发类型和操作统计

### G2 检索适配

修改 `LearningsSearcher._l1_exact_match` 和 `_l1_tag_cross_match` 的 SQL：

```sql
-- 当前 ORDER BY
ORDER BY confidence DESC LIMIT ?

-- 修改为
ORDER BY promoted DESC, confidence DESC LIMIT ?
```

修改 `_format_learnings_block` 在输出中为 `promoted = 1` 的条目添加 `[已验证]` 标签。

### CLI 入口

在 `cli_commands.py` 中新增 `review-learnings` 子命令：

```python
@app.command("review-learnings")
def review_learnings(json_output: bool = typer.Option(False, "--json")):
    """手动触发经验库整理（淘汰 + LLM 晋升）。"""
    # 1. 获取 DB 连接
    # 2. 执行 evict_low_score_learnings
    # 3. 执行 promote_learnings (async → asyncio.run)
    # 4. 输出统计
```

### 遥测记录

扩展 `pa_telemetry` 事件类型：

| event_type | event_data 字段 |
|------------|----------------|
| `maintenance_evict` | `{"trigger", "archived_count", "remaining_count"}` |
| `maintenance_promote` | `{"trigger", "candidates_count", "promoted_count", "merged_count", "archived_count", "llm_tokens_used", "elapsed_sec"}` |
