---
name: knowledge-capture
description: 在需求完成或 Bug 修复后，引导结构化经验沉淀到正确的知识目录。
  当用户明确要求沉淀经验、或完成了一个重要修复时使用此技能。
compatibility: lv-game-toolkit 知识管理
metadata:
  author: lv-game-toolkit
  version: "1.0.0"
---

# 知识沉淀技能

## 适用场景

- 完成一个需求开发后的经验总结
- 修复了一个有价值的 Bug 后记录经验
- 发现了可复用的模式或方案
- 用户主动要求沉淀知识

## 执行步骤

### Step 1: 识别知识类型和层级

根据经验内容判断应沉淀到哪个位置：

| 知识特征 | 目标位置 | 示例 |
|---------|---------|------|
| 特定模块内的经验 | `modules/<name>/docs/` | perfetto_analysis 的 GUI 刷新技巧 |
| 跨模块的项目知识 | `doc/knowledge/` | 新的模块前缀注册、框架使用例外 |
| 具体的踩坑经验 | `doc/experience/development-pitfalls.md` | 新的 Pxx 条目 |
| 跨项目通用经验 | `context/experience/` | Cursor 交互模式、AI 协作技巧 |
| 团队级通用规范 | `context/team/` | Git 工作流调整、编码规范更新 |

### Step 2: 结构化记录

使用以下格式记录经验：

```markdown
## [标题]

### 现象
[描述遇到的问题或发现]

### 根因
[问题的根本原因分析]

### 解法
[具体的解决方案]

### 预防
[如何避免再次发生]
```

对于新的踩坑经验（添加到 development-pitfalls.md），MUST 遵循 Pxx 编号规范。

### Step 3: 更新索引

经验沉淀后 MUST 更新对应的索引文件：

- 新增 pitfall → 更新 `doc/experience/development-pitfalls.md` 的子系统快速索引
- 新增项目知识 → 更新 `doc/knowledge/README.md` 的知识清单
- 新增模块知识 → 更新 `modules/<name>/docs/README.md`
- 新增跨项目经验 → 更新 `context/INDEX.md`

### Step 4: 确认沉淀

向用户确认：
- 经验已记录到正确位置
- 索引已更新
- 是否需要同步更新其他文档（如 constitution、AGENTS.md）

## 注意事项

- 偶发性问题不必沉淀为永久文档
- 简单自然对话能解决的问题不需要创建文档
- 优先在已有文档中追加，而非创建新文件
- 每条知识 SHOULD 标注最后更新日期
