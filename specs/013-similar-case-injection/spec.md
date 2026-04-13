# Spec: 相似案例注入 (G2)

**Status**: Draft | **Created**: 2026-04-13 | **Module**: perfetto_analysis

## 目录

- [概述](#概述)
- [用户故事](#用户故事)
- [功能需求](#功能需求)
- [关键实体](#关键实体)
- [验收场景](#验收场景)
- [边界与约束](#边界与约束)
- [可衡量的成功标准](#可衡量的成功标准)
- [Clarifications](#clarifications)

## 概述

分析开始前，自动从 `pa_learnings` 表检索历史相似案例，注入 SubAgent 上下文作为参考。采用两级检索策略：L1 SQL 标签交叉匹配（零依赖、快速精确），L2 向量语义搜索（`sqlite-vec` + `sentence-transformers`，跨场景关联）。L2 作为可选增强——如果依赖不可用，自动降级到纯 L1。

**OpenClaw 原型**：`vector_similarity + bm25_score + time_decay` 混合检索 → 注入 prompt

## 用户故事

### US1: L1 标签交叉匹配

**作为** Perfetto 分析 SubAgent，  
**我希望** 在分析开始前获得历史上同场景同进程或同根因的分析经验，  
**以便** 避免重复推理、加速根因定位。

**验收场景**：
1. 当 `pa_learnings` 中存在 `scene=jank, process_name=com.test.app` 的记录时，L1 返回匹配结果
2. 当精确匹配不足 2 条时，回退到根因标签交叉匹配
3. 匹配结果按 `confidence DESC, hit_count DESC` 排序
4. 所有 L1 查询过滤 `archived = 0`

### US2: L2 向量语义搜索

**作为** Perfetto 分析系统，  
**我希望** 当 L1 匹配不足时，使用向量语义搜索找到语义相关的历史案例，  
**以便** 跨场景、跨进程发现相似模式。

**验收场景**：
1. L1 返回 < 2 条时自动触发 L2
2. L2 通过 `pa_learning_embeddings` 表进行向量余弦距离搜索
3. `sentence-transformers` 或 `sqlite-vec` 不可用时静默跳过 L2
4. L2 结果排除 L1 已命中的 id

### US3: 上下文注入

**作为** 分析编排器，  
**我希望** 将检索到的历史案例格式化为 SubAgent prompt 的"历史分析参考"区块，  
**以便** SubAgent 在分析时参考但不被限制。

**验收场景**：
1. 历史案例注入到"已知信息"区块的"历史分析参考"子节
2. 每条案例包含：置信度、命中次数、场景、根因、经验、关键指标
3. 明确标注"仅供参考，以当前 trace 数据为准"
4. SubAgent 使用历史案例后，对应记录的 `hit_count` +1、`last_used` 更新

## 功能需求

| ID | 优先级 | 需求 |
|----|--------|------|
| FR-001 | P0 | 实现 `query_similar_learnings_l1` 函数：SQL 精确匹配（同场景+同进程）+ 标签交叉匹配 |
| FR-002 | P0 | 所有查询过滤 `archived = 0`，结果按 `confidence DESC, hit_count DESC` 排序 |
| FR-003 | P0 | L1 返回最多 3 条记录（2 精确 + 1 标签交叉） |
| FR-004 | P1 | 创建 `pa_learning_embeddings` 表（learning_id, embedding BLOB） |
| FR-005 | P1 | 实现 `LearningsSearcher` 类：封装 `sentence-transformers` + `sqlite-vec` 的向量搜索 |
| FR-006 | P1 | L1 命中 < 2 条时自动触发 L2 语义搜索 |
| FR-007 | P0 | 检索结果格式化为"历史分析参考"Markdown 区块注入 SubAgent prompt |
| FR-008 | P0 | 在预取完成后集成案例检索，结果写入 `prefetch_context`（需依赖预取结果提取 issue_tags） |
| FR-009 | P0 | SubAgent 分析完成后，仅当结论的 root_cause_tags 与注入案例标签有交集时，更新该案例的 `hit_count` +1 和 `last_used` |
| FR-010 | P1 | G1 `insert_learning` 时自动生成 embedding 写入 `pa_learning_embeddings`（L2 可用时） |
| FR-011 | P0 | `sentence-transformers` / `sqlite-vec` 不可用时静默降级到纯 L1 |
| FR-012 | P0 | 经验检索失败不中断主分析流程（try-except 包裹） |

## 关键实体

### pa_learning_embeddings 表

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS pa_learning_embeddings USING vec0(
    learning_id INTEGER PRIMARY KEY,
    embedding FLOAT[384]
);
```

### LearningsSearcher 类

```python
class LearningsSearcher:
    """两级经验检索：L1 SQL 标签 → L2 向量语义。"""

    def __init__(self, conn: sqlite3.Connection, embedder=None):
        self._conn = conn
        self._embedder = embedder  # SentenceTransformer 实例，None 表示 L2 不可用

    def search(self, scene: str, process_name: str, issue_tags: list[str], limit: int = 3) -> list[dict]:
        """两级检索主入口。"""

    def _l1_exact_match(self, scene: str, process_name: str, limit: int = 2) -> list[dict]:
        """L1 精确匹配：同场景 + 同进程。"""

    def _l1_tag_cross_match(self, scene: str, issue_tags: list[str], exclude_ids: list[int], limit: int = 1) -> list[dict]:
        """L1 标签交叉：同场景 + 根因标签重叠。"""

    def _l2_semantic_search(self, query: str, exclude_ids: list[int], limit: int = 2) -> list[dict]:
        """L2 向量语义搜索。"""

    def update_hit_count(self, learning_ids: list[int], analysis_output: "AnalysisOutput") -> None:
        """仅当结论 root_cause_tags 与案例标签有交集时更新 hit_count 和 last_used。"""
```

## 验收场景

### 场景 1: L1 精确匹配命中

- 前置：`pa_learnings` 中有 3 条 `scene=jank, process_name=com.test.app` 的记录
- 操作：分析 `com.test.app` 的 jank trace
- 预期：SubAgent prompt 包含"历史分析参考"区块，含 2 条精确匹配案例

### 场景 2: L1 不足，触发 L2

- 前置：`pa_learnings` 中仅 1 条匹配记录，L2 依赖已安装
- 操作：同上
- 预期：L1 返回 1 条，L2 补充 1 条语义相似案例

### 场景 3: L2 不可用降级

- 前置：`sentence-transformers` 未安装
- 操作：同上
- 预期：仅 L1 结果注入，无报错

### 场景 4: 无历史数据

- 前置：`pa_learnings` 表为空
- 操作：首次分析
- 预期：无"历史分析参考"区块，不影响分析流程

### 场景 5: hit_count 更新

- 前置：案例 A 被注入 SubAgent
- 操作：分析完成
- 预期：案例 A 的 `hit_count` +1，`last_used` 更新为当前时间

## 边界与约束

1. L1 SQL 查询必须过滤 `archived = 0`，避免引用已淘汰的经验
2. L2 向量搜索使用中文 embedding 模型 `shibing624/text2vec-base-chinese`（384 维）
3. embedding 生成在 `insert_learning` 时同步执行（<100ms per record）
4. `pa_learning_embeddings` 使用 `sqlite-vec` 虚拟表，需要加载扩展
5. 注入的案例数量限制：最多 3 条（避免 prompt 过长）
6. 注入文本每条案例限制 500 字符以内
7. 依赖不可用时的降级链：L1+L2 → 纯L1 → 无案例注入

## 可衡量的成功标准

| 指标 | 目标 |
|------|------|
| L1 查询延迟 | < 10ms |
| L2 查询延迟 | < 500ms（含 embedding 编码） |
| 案例注入 token 开销 | < 800 tokens |
| 测试覆盖率 | L1/L2/降级/hit_count 更新全覆盖 |
| L2 不可用时零报错 | 静默跳过 |

## Clarifications

### C1: L1 标签交叉匹配的 issue_tags 来源

**决策**：从预取结果中提取标签 + scene 匹配。L1 第一优先级用 `scene + process_name` 精确匹配，第二优先级用 `scene + issue_tags` 标签交叉匹配。`issue_tags` 从预取阶段结果中提取（如 jank 场景的 `jank_type`，其他场景从预取数据中识别关键异常标签）。如果预取结果无法提取标签，则第二优先级退化为 `scene` 维度扩大匹配。

### C2: hit_count 更新策略

**决策**：仅当分析结论的 `root_cause_tags` 与注入案例的 `root_cause_tags` 有交集时才更新 `hit_count += 1` 和 `last_used = now()`。这确保只有真正与当前分析相关的历史案例才会被标记为"被引用"。

### C3: L2 依赖安装策略

**决策**：`sentence-transformers` 和 `sqlite-vec` 作为可选依赖，通过 `pip install .[vector]` 安装。不强制用户安装。L2 不可用时静默降级到纯 L1。开发环境中安装。
