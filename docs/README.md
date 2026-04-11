# LV Game Toolkit — 文档中心

## 目录

- [文档结构](#文档结构)
- [架构设计文档](#架构设计文档)
- [项目知识库](#项目知识库)
- [项目经验库](#项目经验库)
- [PerfDog 分析用户入口](#perfdog-分析用户入口)
- [Speckit 特性规格](#speckit-特性规格)
- [开发文档](#开发文档)

## 文档结构

```text
docs/
├── PROGRESS.md                  # 项目进度总览（跨会话锚点）
├── README.md                    # 本文件（文档索引）
├── architecture/                # 架构设计文档
│   ├── architecture-overview.md #   完整架构设计（11 章）
│   ├── technical-decisions.md   #   技术决策记录（ADR）
│   ├── learning-roadmap.md      #   学习路线
│   ├── 集成agent后缺失的能力.md #   Agent 集成后能力缺口分析
│   └── 项目重新设计的需求.md    #   项目重构需求分析
├── knowledge/                   # 项目知识库（跨模块知识）
│   ├── README.md                #   知识库索引
│   ├── module-registry.md       #   模块前缀注册表 + 事件总线
│   ├── toolkit-exceptions.md    #   框架使用例外清单
│   ├── module-development-guide.md #   新模块开发完整指南
│   └── 长期记忆其他实践.md      #   AI Agent 长期记忆外部实践参考
├── experience/                  # 项目经验库
│   ├── README.md                #   经验库索引
│   └── development-pitfalls.md  #   踩坑指南（25 项 + 子系统快速索引）
└── team/                        # 团队规范（原 context/ 内容）
    ├── git-workflow.md          #   Git 分支策略与提交规范
    ├── coding-conventions.md    #   跨项目编码规范
    ├── speckit-multi-module.md  #   多模块 Speckit 使用约定
    └── cursor-interaction.md    #   Cursor IDE 交互经验
```

## 架构设计文档

| 文档 | 说明 |
|------|------|
| [architecture-overview.md](architecture/architecture-overview.md) | 项目完整架构设计，涵盖分层设计、技术选型、目录结构、核心框架、模块规范、Speckit 管理、CLI/GUI/Agent 设计、构建部署、协作流程共 11 个章节；**代码规则总纲见 §5.0** |
| [technical-decisions.md](architecture/technical-decisions.md) | 12 项架构决策记录（ADR），包括技术栈、插件系统、仓库管理、数据存储等 |
| [learning-roadmap.md](architecture/learning-roadmap.md) | 项目涉及的核心概念解析、分阶段学习路线、技术栈学习材料、推荐书籍和参考项目 |
| [集成agent后缺失的能力.md](architecture/集成agent后缺失的能力.md) | Agent 集成后的能力缺口分析：已实现 vs 待补全（token 显示、Provider 切换、SOP 物化等） |
| [项目重新设计的需求.md](architecture/项目重新设计的需求.md) | 项目重构需求分析 |

## 项目知识库

跨模块的项目知识资产，详见 [knowledge/README.md](knowledge/README.md)。

| 文档 | 说明 |
|------|------|
| [module-registry.md](knowledge/module-registry.md) | 6 个模块的前缀注册表、EventBus 事件注册表、模块依赖关系 |
| [toolkit-exceptions.md](knowledge/toolkit-exceptions.md) | 框架使用例外清单（允许的 `toolkit.core` 导入、特殊测试位置） |
| [module-development-guide.md](knowledge/module-development-guide.md) | 新模块开发完整指南（环境 → 创建 → Spec 工作流 → 实现 → 测试 → 提交） |
| [长期记忆其他实践.md](knowledge/长期记忆其他实践.md) | AI Agent 长期记忆系统外部实践参考（文档驱动方案对比） |

## 项目经验库

开发经验的结构化索引，详见 [experience/README.md](experience/README.md)。

| 文档 | 说明 |
|------|------|
| [development-pitfalls.md](experience/development-pitfalls.md) | 25 项踩坑经验 + 按子系统快速索引（插件框架/GUI/ADB/Perfetto/构建/LLM/工具链） |

## PerfDog 分析用户入口

在 **Toolkit GUI** 侧栏打开 **「PerfDog分析」** 选项卡：拖入或选择 PerfDog 导出的 **`.xlsx` / `.xlsm`**，即可离线生成会话摘要、问题洞察、建议与可选 **@FrameInfo / @ThreadCpuUsageData** 关联结论；支持 **导出 / 复制 Markdown**、**双会话对比**（第二份文件）及（在「游戏性能配置」已加载 XML 时）**联合分析**。详细步骤与规格见 **[specs/004-perfdog-import-insights/plan.md#快速开始](../specs/004-perfdog-import-insights/plan.md#快速开始)**；模块说明见 **[modules/perfdog_insights/README.md](../modules/perfdog_insights/README.md)**。

## Speckit 特性规格

仓库根目录 `specs/` 下的主特性文档与 **实现记录** 对照：

| 特性目录 | 状态 | 说明 |
|----------|------|------|
| [001-framework-completion](../specs/001-framework-completion/) | Draft | 框架基础能力补全 |
| [002-core-enhancement](../specs/002-core-enhancement/) | Implemented | 核心框架增强 |
| [003-adb-enhancement](../specs/003-adb-enhancement/) | Implemented | ADB 能力增强 |
| [004-perfdog-import-insights](../specs/004-perfdog-import-insights/) | Draft | PerfDog 数据导入与洞察 |
| [004-adb-perfetto-support](../specs/004-adb-perfetto-support/) | spec only | ADB Perfetto 支持 |
| [006-mcp-skills-subagent](../specs/006-mcp-skills-subagent/) | Implemented | MCP Skills SubAgent 编排 |
| [007-gameperf-config-diff](../specs/007-gameperf-config-diff/) | Implemented | 游戏性能配置对比 |
| [007-fps-chart-enhancement](../specs/007-fps-chart-enhancement/) | Implemented | FPS 图表增强 |
| [008-global-settings-llm](../specs/008-global-settings-llm/) | Draft | 全局 LLM 设置 |
| [009-history-batch-analysis](../specs/009-history-batch-analysis/) | Draft | 历史记录批量分析 |
| [010-prompt-budget-management](../specs/010-prompt-budget-management/) | Draft | Prompt 预算管理 |

## 开发文档

脚本说明文档位于 `scripts/doc/` 目录：

| 文档 | 说明 |
|------|------|
| [build.md](../scripts/doc/build.md) | PyInstaller 构建脚本使用说明（双入口、资源收集、产物结构） |
| [create_module.md](../scripts/doc/create_module.md) | 模块脚手架脚本使用说明 |
| [run_all_tests.md](../scripts/doc/run_all_tests.md) | 统一测试运行脚本说明 |

