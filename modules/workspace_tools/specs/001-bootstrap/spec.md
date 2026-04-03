# Feature Specification: 工作区工具（模块占位）

**Branch**: （按需创建）  
**Status**: Bootstrap — 骨架已就绪，具体能力待 Clarify / Specify  
**Created**: 2026-04-03

## 背景

在 LVGT 侧边栏末尾增加 **`工作区工具`** 模块入口，遵循 `modules/` 插件约定（`manifest.json` + `plugin.py` + `service` / `gui_tab` / `cli`），用于后续挂载与工作区相关的辅助功能（文件、路径、批处理等），而不挤占现有业务 Tab。

## 用户故事（占位）

- **US-B1**: 作为用户，我能在侧边栏看到「工作区工具」并可打开该 Tab。  
- **US-B2**: 作为开发者，我能在 `specs/` 下按 speckit 流程补充正式 spec/plan/tasks 并实现功能。

## 功能需求（Bootstrap 阶段）

- **FR-B01**: 模块 MUST 被主程序发现并加载，GUI 显示 Tab 标题「工作区工具」与图标。  
- **FR-B02**: `on_startup` MUST 向 `context` 注册 `wo_service`（`WorkspaceToolsService` 实例）。  
- **FR-B03**: CLI MUST 提供 `toolkit workspace info`（或等价入口）用于烟测。  
- **FR-B04**: MUST NOT 修改 `toolkit/` 目录。

## 后续工作（非本期必交付）

- 在 Clarify 中确定：具体工具列表、是否依赖设备、与 `data_dir` / 工作区路径的关系。  
- 按 `spec-workflow.mdc` 补充 plan / tasks 后实现业务逻辑。

## Clarifications

- （待填）
