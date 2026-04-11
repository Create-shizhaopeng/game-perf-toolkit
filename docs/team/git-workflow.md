# Git 工作流规范

## 目录

- [分支策略](#分支策略)
- [提交规范](#提交规范)
- [PR 流程](#pr-流程)

## 分支策略

- 主分支：`main`（稳定版本） + `dev`（开发集成）
- 特性分支：`feat/<module>-<feature>`
- 修复分支：`fix/<module>-<description>`

## 提交规范

格式：`<type>(<scope>): <description>`

| type | 说明 |
|------|------|
| feat | 新功能 |
| fix | Bug 修复 |
| refactor | 重构（不改变功能） |
| docs | 文档更新 |
| test | 测试相关 |
| chore | 构建/配置变更 |

scope 使用模块名（如 `device_disguise`）或框架范围（`core`、`sdk`）。

## PR 流程

1. 特性分支开发完成后提交 PR
2. PR 描述 MUST 包含：变更摘要、影响范围、测试验证
3. 通用框架（`toolkit/core/`、`toolkit/sdk/`）修改需主负责人审核
