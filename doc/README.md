# LV Game Toolkit — 文档中心

## 目录

- [文档结构](#文档结构)
- [架构设计文档](#架构设计文档)
- [开发文档](#开发文档)
- [旧版文档归档](#旧版文档归档)

## 文档结构

```text
doc/
├── README.md                    # 本文件（文档索引）
├── architecture/                # 架构设计文档
│   ├── architecture-overview.md #   完整架构设计（11 章）
│   ├── technical-decisions.md   #   技术决策记录（ADR）
│   ├── learning-roadmap.md      #   架构学习路线与材料
│   └── 项目重新设计的需求.md       #   重构需求背景
└── legacy/                      # 旧版文档归档（重构前）
    ├── README.md                #   归档说明与状态标注
    ├── spec.md                  #   旧：设备伪装规格
    ├── spec-push-policy.md      #   旧：性能配置推送规格
    ├── data-model.md            #   旧：数据模型
    ├── impl-plan.md             #   旧：实现计划
    ├── tasks.md                 #   旧：任务清单
    ├── research.md              #   旧：技术调研
    ├── quickstart.md            #   旧：快速上手
    ├── get_game_policy.md       #   旧：策略提取脚本
    ├── packaging-windows.md     #   旧：Windows 打包
    └── design/                  #   旧：UI 设计稿（SVG）
```

## 架构设计文档

| 文档 | 说明 |
|------|------|
| [architecture-overview.md](architecture/architecture-overview.md) | 项目完整架构设计，涵盖分层设计、技术选型、目录结构、核心框架、模块规范、Speckit 管理、CLI/GUI/Agent 设计、构建部署、协作流程共 11 个章节 |
| [technical-decisions.md](architecture/technical-decisions.md) | 12 项架构决策记录（ADR），包括技术栈、插件系统、仓库管理、数据存储等 |
| [learning-roadmap.md](architecture/learning-roadmap.md) | 项目涉及的核心概念解析、分阶段学习路线、技术栈学习材料、推荐书籍和参考项目 |

## 开发文档

开发相关文档位于 `scripts/doc/` 目录：

| 文档 | 说明 |
|------|------|
| [module-development-guide.md](../scripts/doc/module-development-guide.md) | 新模块开发完整指南（环境 → 创建 → Spec 工作流 → 实现 → 测试 → 提交） |
| [development-pitfalls.md](../scripts/doc/development-pitfalls.md) | 开发常见踩坑问题集（14 项），含问题描述、原因和解决方案 |
| [build.md](../scripts/doc/build.md) | PyInstaller 构建脚本使用说明（双入口、资源收集、产物结构） |
| [create_module.md](../scripts/doc/create_module.md) | 模块脚手架脚本使用说明 |
| [run_all_tests.md](../scripts/doc/run_all_tests.md) | 统一测试运行脚本说明 |

## 旧版文档归档

`legacy/` 目录保存重构前的单体应用文档，详见 [legacy/README.md](legacy/README.md)。
这些文档在新架构的 `specs/`、`modules/*/specs/`、`.specify/` 中已被部分或全部替代，
保留作为迁移参考和历史记录。
