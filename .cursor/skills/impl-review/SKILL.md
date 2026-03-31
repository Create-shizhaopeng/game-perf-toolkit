---
name: impl-review
description: 实现阶段的变更 review 技能。在完成一组代码变更后，检查变更与 spec 的对齐情况，
  输出变更摘要和一致性报告。当实现完成或需要阶段性 review 时使用。
compatibility: lv-game-toolkit spec-driven 开发
metadata:
  author: lv-game-toolkit
  version: "1.0.0"
---

# 实现 Review 技能

## 适用场景

- 完成一组代码变更后的自检
- spec implement 步骤完成后、进入 analysis 之前
- 用户要求检查当前实现与 spec 的对齐情况

## 执行步骤

### Step 1: 收集变更范围

1. 检查当前工作目录下的 git 变更（`git diff --stat`、`git status`）
2. 列出所有修改、新增、删除的文件
3. 按模块分组整理变更

### Step 2: 加载 Spec 上下文

1. 定位当前功能对应的 `spec.md`（在 `specs/` 或 `modules/<name>/specs/` 下）
2. 读取 spec.md 中的功能需求（FR）和验收标准（SC）
3. 如果有 `plan.md`，读取关键设计决策

### Step 3: 一致性检查

逐项检查：

| 检查项 | 说明 |
|--------|------|
| FR 覆盖 | 每个功能需求是否有对应的代码实现 |
| SC 满足 | 每个验收标准是否可通过当前实现验证 |
| 边界约束 | 是否遵循了模块 AGENTS.md 的导入/修改边界 |
| 质量门禁 | 公共方法是否有类型注解和测试用例 |
| 文档同步 | 是否有需要同步更新的文档 |

### Step 4: 输出 Review 报告

```markdown
## 实现 Review 报告

### 变更摘要
- 修改文件：[N] 个
- 新增文件：[N] 个
- 涉及模块：[模块列表]

### FR 对齐情况
| FR ID | 描述 | 状态 | 备注 |
|-------|------|------|------|
| FR-1 | ... | ✅/⚠️/❌ | ... |

### 发现的问题
[按严重程度排列]

### 建议
[后续需要完成的事项]
```

### Step 5: 经验标记

如果在 review 过程中发现了值得沉淀的经验模式：
- 标记为「待沉淀」，建议使用 knowledge-capture 技能处理

## 注意事项

- 本技能是辅助性自检，不替代 `spec analysis` 步骤
- 关注「实现是否偏离预期」而非「代码风格是否完美」
- 如发现严重偏离，SHOULD 在修复前与用户确认方向
