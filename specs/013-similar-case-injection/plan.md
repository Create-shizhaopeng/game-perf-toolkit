# Implementation Plan: 相似案例注入 (G2)

**Branch**: `013-similar-case-injection` | **Date**: 2026-04-13 | **Spec**: [spec.md](spec.md)

## 目录

- [Summary](#summary)
- [Technical Context](#technical-context)
- [Constitution Check](#constitution-check)
- [Project Structure](#project-structure)
- [Phase 0 Research](#phase-0-research)
- [Phase 1 Design](#phase-1-design)

## Summary

实现两级经验检索系统（L1 SQL 标签匹配 + L2 向量语义搜索），在 SubAgent 分析前自动注入历史相似案例。L1 零依赖直接使用 SQLite 查询；L2 通过 `sqlite-vec` + `sentence-transformers` 提供语义搜索能力，作为可选增强。检索到的案例注入 SubAgent prompt 的"历史分析参考"区块。

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: sqlite3 (内置), sentence-transformers (可选), sqlite-vec (可选)  
**Storage**: SQLite (`perfetto_analysis.db`)，复用现有 DB  
**Testing**: pytest + unittest.mock  
**Constraints**: L2 依赖不可用时零报错静默降级  
**Prerequisites**: G1 已实现（`pa_learnings` 表、`AnalysisOutput` 结构化输出）

## Constitution Check

| 原则 | 合规 | 说明 |
|------|------|------|
| 模块不修改 toolkit/ | ✅ | 仅修改 modules/perfetto_analysis/ |
| service.py 无 GUI 代码 | ✅ | 检索逻辑在 orchestrator 层 |
| Pydantic 用于公共 API | ✅ | 无新公共 API 模型，内部使用 dict |
| UTF-8 输出 | ✅ | 中文 embedding 模型 |

## Project Structure

### 新增/修改文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/agent/learnings_search.py` | **新增** | LearningsSearcher 类：L1 + L2 两级检索 |
| `src/engine/storage.py` | 修改 | 新增 pa_learning_embeddings 虚拟表 + embedding 写入函数 |
| `src/agent/orchestrator.py` | 修改 | 集成案例检索到预取流程 + hit_count 更新 |
| `tests/test_g2_similar_case.py` | **新增** | G2 单元测试 |

## Phase 0 Research

### R1: 预取结果中的 issue_tags 提取

当前预取结果（G0）的数据结构：

| 场景 | 预取工具 | 可提取标签 |
|------|---------|-----------|
| jank | `detect_jank` | `jank_type`（从 jank_frames 中提取） |
| anr | `analyze_dimension(thread)` | 主线程阻塞类型（binder/io/lock） |
| memory | `analyze_dimension(gc)` | GC 暂停类型 |
| 其他 | `trace_overview` | 无明确 issue 标签 |

**Decision**: 实现 `_extract_issue_tags_from_prefetch(prefetch_context: dict) -> list[str]` 函数，从预取结果中提取标签。无法提取时返回空列表，L1 第二优先级退化为 `scene` 匹配。

### R2: sqlite-vec 在 Windows 上的兼容性

**Decision**: 使用 `sqlite-vec` PyPI 包（`pip install sqlite-vec`），已提供 Windows/Linux/macOS 预编译 wheel。通过 `conn.enable_load_extension(True)` + `sqlite_vec.load(conn)` 加载。不可用时静默跳过 L2。

### R3: embedding 模型选择

**Decision**: 使用 `shibing624/text2vec-base-chinese`（384 维），中文语义理解能力强。首次使用时自动下载模型（约 400MB）。可以配置为离线模式（将模型放在本地目录）。

## Phase 1 Design

### LearningsSearcher 架构

```python
class LearningsSearcher:
    """两级经验检索器。"""

    def __init__(self, conn: sqlite3.Connection, embedder=None):
        self._conn = conn
        self._embedder = embedder  # None = L2 不可用

    def search(
        self, scene: str, process_name: str,
        issue_tags: list[str] | None = None, limit: int = 3,
    ) -> list[dict]:
        """主入口：L1 → (可选 L2) → 合并去重。"""
        results = []
        found_ids = []

        # L1 第一优先级：精确匹配
        exact = self._l1_exact_match(scene, process_name, limit=2)
        results.extend(exact)
        found_ids.extend(r["id"] for r in exact)

        # L1 第二优先级：标签交叉 / scene 扩大
        if len(results) < limit:
            cross = self._l1_tag_cross_match(
                scene, issue_tags or [], found_ids, limit=limit - len(results),
            )
            results.extend(cross)
            found_ids.extend(r["id"] for r in cross)

        # L2 语义搜索（L1 命中 < 2 条时触发）
        if len(results) < 2 and self._embedder is not None:
            query = f"{scene} {' '.join(issue_tags or [])}"
            semantic = self._l2_semantic_search(query, found_ids, limit=limit - len(results))
            results.extend(semantic)

        return results[:limit]
```

### 预取标签提取

```python
def _extract_issue_tags_from_prefetch(prefetch_context: dict) -> list[str]:
    """从预取结果中提取 issue 标签。"""
    tags = []

    # jank 场景: 从 jank_frames 提取 jank_type
    jank_data = prefetch_context.get("jank_frames") or prefetch_context.get("jank_detect")
    if isinstance(jank_data, dict):
        jank_records = jank_data.get("jank_records") or jank_data.get("parse_result", {}).get("jank_records", [])
        for jr in jank_records[:5]:
            jt = jr.get("jank_type", "")
            if jt and jt not in tags:
                tags.append(jt)

    # 其他维度结果中的 issues
    for key, value in prefetch_context.items():
        if isinstance(value, dict) and "issues" in value:
            for issue in value["issues"][:5]:
                tag = issue.get("type") or issue.get("tag", "")
                if tag and tag not in tags:
                    tags.append(tag)

    return tags
```

### hit_count 更新逻辑

```python
def _update_hit_counts(
    self, injected_ids: list[int], analysis_output: AnalysisOutput,
) -> None:
    """仅当结论根因标签与注入案例标签有交集时更新。"""
    if not analysis_output or not analysis_output.root_causes:
        return
    conclusion_tags = {rc.tag for rc in analysis_output.root_causes}

    for learning_id in injected_ids:
        # 查询该 learning 的 root_cause_tags
        row = self._conn.execute(
            "SELECT root_cause_tags FROM pa_learnings WHERE id = ?",
            (learning_id,),
        ).fetchone()
        if not row:
            continue
        learning_tags = set(row[0].split(",")) if row[0] else set()
        if conclusion_tags & learning_tags:
            self._conn.execute(
                "UPDATE pa_learnings SET hit_count = hit_count + 1, last_used = ? WHERE id = ?",
                (datetime.now().isoformat(), learning_id),
            )
    self._conn.commit()
```

### 注入格式

```markdown
### 历史分析参考（仅供参考，以当前 trace 数据为准）

#### 案例 1 (置信度 0.8, 命中 5 次)
- 场景: jank | 进程: com.example.game
- 根因: cpu_throttle, thermal
- 经验: SM8750 设备在高负载时大核频率被限制在 1.4GHz
- 关键指标: {"max_freq_khz": 1400000}
```

### 降级链

```
L1 + L2 完整检索
    ↓ (sentence-transformers 不可用)
纯 L1 检索
    ↓ (pa_learnings 表为空)
无案例注入（不影响分析）
    ↓ (DB 连接失败)
静默跳过（try-except 包裹）
```
