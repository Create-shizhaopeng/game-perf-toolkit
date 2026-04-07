---
name: knowledge-curator
description: >-
  Process raw analysis documents, experience documents, and SOP documents into
  structured Skill sub-resources. Classifies content (SOP methodology, root cause
  patterns, case studies, SQL templates), matches target Skills, and formats for
  integration. Use when the user imports raw documents, wants to enrich an existing
  Skill, or mentions document curation, knowledge extraction, or experience archiving.
---

# Knowledge Curator — 知识资产策展

将非结构化的原始文档提炼为结构化的 Skill 子资源。覆盖工具自带 Skill 和用户导入的 Skill。

## 适用场景

- 用户导入团队的分析 SOP 或经验文档
- 用户将分析结论沉淀为案例
- 用户提供外部技术文章需提炼可复用的分析模式
- 用户要求扩充某个 Skill 的知识库

## Step 1 — 接收文档

获取用户提供的原始文档：

- 本地文件路径（.md / .txt）
- 粘贴的文本内容
- URL（通过 fetch 获取）

如果文档包含图片，提示用户图片内容需文字描述替代（Skill 子资源为纯 Markdown）。

## Step 2 — 内容分类

分析文档内容，按以下规则分类：

| 类型 | 识别特征 | 目标目录 |
|------|----------|---------|
| 方法论 SOP | 步骤编号、操作指引、决策树、工具使用流程 | `sop/` |
| 根因模式 | "当X发生→原因Y→方案Z" 的条件-原因-方案结构 | `patterns/` |
| 分析案例 | 具体设备/trace/时间戳 + 完整分析过程 + 结论 | `cases/` |
| SQL 模板 | 含 `SELECT` / `FROM` 等 SQL 关键词 + 使用说明 | 嵌入关联 SOP |
| 混合内容 | 包含多种类型 → 拆分后分别处理 | 分别归类 |

**输出**：分类结果列表 + 每项内容摘要。

## Step 3 — 匹配目标 Skill

1. 列出 SkillsManager 已发现的所有 Skill（或扫描 `modules/*/skills/`）
2. 对每个分类项，与 Skill 的 `description` 和已有子资源做关键词匹配
3. 推荐最匹配的 Skill，用户可覆盖选择

**匹配优先级**：用户显式指定 > 关键词重叠度 > 已有子资源领域覆盖。

## Step 4 — 格式化与去重

1. 按目标类型套用标准模板格式化内容（模板详见 [templates.md](templates.md)）
2. 对比目标 Skill 已有子资源的标题和关键词
3. 重叠度 > 70% 时提示用户：合并 / 替换 / 跳过

**文件命名**：kebab-case（如 `binder-blocking-analysis.md`）

## Step 5 — 确认与写入

展示以下信息供用户确认：

```
策展预览:
- 文档: <原始文档名>
- 目标 Skill: perfetto-analysis
- 新增:
  ├ sop/binder-blocking-analysis.md (方法论 SOP)
  └ patterns/sf-buffer-timeout.md (根因模式)
- 跳过: 1 项（与 jank-analysis.md 重复 85%）

[确认写入] / [预览内容] / [取消]
```

用户确认后写入到目标 Skill 的对应子资源目录。

## Step 6 — 验证

1. 确认文件已创建
2. 检查 YAML frontmatter 格式合法
3. 输出策展报告

## 辅助工具

<!-- TODO: 以下工具待后续实现 -->

| 工具 | 用途 |
|------|------|
| `kc_classify_document` | 对输入文档进行内容分类 |
| `kc_match_skill` | 将分类内容匹配到目标 Skill |
| `kc_format_resource` | 按模板格式化子资源 |
| `kc_check_duplicate` | 与已有子资源做重复检测 |
| `kc_write_resource` | 写入格式化后的子资源文件 |

## 约束

- 写入前 MUST 获得用户确认
- 原始文档中的图片需文字描述替代
- 策展内容 MUST 保留 `source` 字段引用原始出处
- 混合内容 MUST 拆分为独立子资源
- 格式化模板详见 [templates.md](templates.md)
