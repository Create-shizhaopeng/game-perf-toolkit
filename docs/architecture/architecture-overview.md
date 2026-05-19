# LV Game Toolkit — 项目架构设计文档

## 目录

- [1. 架构概述与分层设计](#1-架构概述与分层设计)
  - [1.1 设计理念](#11-设计理念)
  - [1.2 分层架构](#12-分层架构)
  - [1.3 设计原则](#13-设计原则)
  - [1.4 数据流](#14-数据流)
- [2. 技术选型方案](#2-技术选型方案)
  - [2.1 核心技术栈](#21-核心技术栈)
  - [2.2 关键依赖库](#22-关键依赖库)
  - [2.3 插件系统选型](#23-插件系统选型)
  - [2.4 配置文件格式](#24-配置文件格式)
- [3. 项目目录结构](#3-项目目录结构)
  - [3.1 完整目录树](#31-完整目录树)
  - [3.2 目录设计说明](#32-目录设计说明)
  - [3.3 模块内标准目录](#33-模块内标准目录)
  - [3.4 管理归属](#34-管理归属)
  - [3.5 数据存放策略](#35-数据存放策略)
- [4. 核心框架设计](#4-核心框架设计)
  - [4.1 插件系统](#41-插件系统)
  - [4.2 事件总线](#42-事件总线)
  - [4.3 可配置工作流引擎](#43-可配置工作流引擎)
  - [4.4 服务注册表](#44-服务注册表)
  - [4.5 配置管理](#45-配置管理)
  - [4.6 外部进程桥接](#46-外部进程桥接)
  - [4.7 数据库管理](#47-数据库管理)
  - [4.8 核心服务总览](#48-核心服务总览)
- [5. 模块开发规范](#5-模块开发规范)
  - [5.0 代码规则（总纲）](#50-代码规则总纲)
  - [5.1 标准目录结构](#51-标准目录结构)
  - [5.2 manifest.json 规范](#52-manifestjson-规范)
  - [5.3 开发标准流程](#53-开发标准流程)
  - [5.4 service.py 编写规范](#54-servicepy-编写规范)
  - [5.5 AGENTS.md 模板](#55-agentsmd-模板)
  - [5.6 脚手架脚本](#56-脚手架脚本)
- [6. Speckit 分层管理方案](#6-speckit-分层管理方案)
  - [6.1 分层架构](#61-分层架构)
  - [6.2 规则传递机制](#62-规则传递机制)
  - [6.3 初始化流程](#63-初始化流程)
  - [6.4 协作场景](#64-协作场景)
  - [6.5 规则同步机制](#65-规则同步机制)
- [7. CLI 设计方案](#7-cli-设计方案)
  - [7.1 设计目标](#71-设计目标)
  - [7.2 命令结构](#72-命令结构)
  - [7.3 输出格式](#73-输出格式)
  - [7.4 统一响应格式](#74-统一响应格式)
  - [7.5 自动注册机制](#75-自动注册机制)
  - [7.6 命名空间防冲突](#76-命名空间防冲突)
- [8. GUI 框架设计](#8-gui-框架设计)
  - [8.1 主窗口布局](#81-主窗口布局)
  - [8.2 Title Bar 设计](#82-title-bar-设计)
  - [8.3 类层次结构](#83-类层次结构)
  - [8.4 BaseTab 基类](#84-basetab-基类)
  - [8.5 通用 UI 组件库](#85-通用-ui-组件库)
  - [8.6 主题系统](#86-主题系统)
- [9. Agent 智能助手模块](#9-agent-智能助手模块)
  - [9.1 设计定位](#91-设计定位)
  - [9.2 模块架构](#92-模块架构)
  - [9.3 对话循环](#93-对话循环核心流程)
  - [9.4 工具注册协议](#94-工具注册协议)
  - [9.5 LLM Provider 体系](#95-llm-provider-体系)
  - [9.6 SOP 工作流管理](#96-sop-工作流管理)
  - [9.7 GUI Agent Tab](#97-gui-agent-tab)
  - [9.8 已适配的模块工具](#98-已适配的模块工具)
- [10. 构建与部署方案](#10-构建与部署方案)
  - [10.1 构建目标](#101-构建目标)
  - [10.2 入口设计](#102-入口设计)
  - [10.3 双入口构建策略](#103-双入口构建策略)
  - [10.4 跨平台构建](#104-跨平台构建)
  - [10.5 版本管理](#105-版本管理)
- [11. 协作流程与规范](#11-协作流程与规范)
  - [11.1 团队角色分工](#111-团队角色分工)
  - [11.2 开发流程](#112-开发流程)
  - [11.3 Git 分支策略](#113-git-分支策略)
  - [11.4 提交规范](#114-提交规范)
  - [11.5 Git 管理策略](#115-git-管理策略)

---

## 1. 架构概述与分层设计

### 1.1 设计理念

本项目架构的核心理念是 **「Agent 驱动 + 模块化工具集 + 三端统一」**：

- **Agent 驱动**：AI Agent 作为未来的主要交互入口，所有工具模块作为 Agent 可调用的能力
- **模块化工具集**：每个功能独立开发、独立测试，通过插件机制注册到主框架
- **三端统一**：GUI / CLI / Agent 三种交互方式共享同一套业务逻辑，不重复实现

### 1.2 分层架构

```
     👤 人类用户                          🤖 AI Agent (speckit/Cursor)
         │                                      │
         │ 主要通过 GUI 操作                      │ 主要通过 CLI 获取数据和执行操作
         │ 也可通过 GUI 内的聊天面板与 Agent 对话    │ 也可被 GUI 中的聊天模块调用
         │                                      │
    ┌────▼─────────────────┐            ┌───────▼──────────────┐
    │      GUI (PyQt6)     │            │     CLI (Typer)       │
    │                      │            │                      │
    │  ┌──────────────┐    │            │  toolkit device list  │
    │  │ 模块功能面板   │    │            │  toolkit perf push    │
    │  │ (各模块Tab)   │    │            │  toolkit log analyze  │
    │  ├──────────────┤    │     ◄──►   │  toolkit agent ask    │
    │  │ Agent 聊天面板 │    │            │  ...                 │
    │  │ (对话+结果展示) │    │            │                      │
    │  └──────────────┘    │            │  输入/输出: JSON 格式   │
    └──────────┬───────────┘            └──────────┬───────────┘
               │                                   │
               └───────────────┬───────────────────┘
                               ▼
                ┌──────────────────────────────┐
                │      服务层 (Service API)      │
                │  统一的 Python API 层           │
                │  GUI/CLI/Agent 都调用这一层     │
                └──────────────┬───────────────┘
                               ▼
                ┌──────────────────────────────┐
                │    核心框架层 (Core Framework)  │
                │                              │
                │  Plugin Manager │ Event Bus   │
                │  ServiceRegistry│ Config Mgr  │
                │  WorkflowEngine │ ADB Manager │
                │  ProcessBridge  │ Logger      │
                └──────────────┬───────────────┘
                               ▼
                ┌──────────────────────────────┐
                │       模块层 (Plugins)        │
                │                              │
                │  device_disguise │ game_perf      │
                │  perfetto_capture│ perfdog_insights│
                │  log_analysis    │ trace          │
                │  policy_report   │ predict    │
                │  agent_chat      │ ...        │
                └──────────────────────────────┘
```

### 1.3 设计原则

| 原则 | 说明 |
|------|------|
| **依赖反转** | 模块依赖核心框架定义的接口，核心框架不依赖具体模块 |
| **单一职责** | 每个模块只负责一个功能领域 |
| **表现分离** | 业务逻辑不包含任何 GUI/CLI 代码，GUI/CLI 只做展示和输入 |
| **开闭原则** | 新增模块不需修改核心框架代码，通过注册机制自动发现 |
| **外部进程桥接** | 其他技术栈的工具通过标准化的进程调用 + JSON I/O 集成 |

### 1.4 数据流

```
用户/Agent
    │
    ▼
[表现层] 接收用户意图（GUI操作 / CLI命令 / Agent指令）
    │
    ▼
[服务API] 转化为统一的 Python 函数调用
    │
    ▼
[核心框架] 路由到对应模块，协调模块间的数据流转
    │
    ▼
[模块层] 执行具体业务逻辑，返回结构化结果
    │
    ▼
[表现层] 将结果渲染为 GUI界面 / CLI输出 / Agent可理解的文本
```

---

## 2. 技术选型方案

### 2.1 核心技术栈

| 类别 | 选型 | 理由 |
|------|------|------|
| **语言** | **Python 3.12+** | 性能显著提升，改进的错误提示，内置 `tomllib`，f-string 增强 |
| **GUI 框架** | **PyQt6** | 跨平台，原生体验，支持 QML 集成 |
| **CLI 框架** | **Typer** | 基于 click，使用类型注解，自带 Rich 美化，对 Agent 友好 |
| **插件系统** | **pluggy** | pytest 同款，成熟稳定，钩子机制灵活 |
| **打包工具** | **PyInstaller 6+** | 支持 Win/Linux 打包，onedir 模式解压即用 |

### 2.2 关键依赖库

| 库 | 用途 |
|---|------|
| `PyQt6` | GUI 框架 |
| `typer[all]` | CLI 框架（含 Rich 美化） |
| `rich` | 终端美化输出 |
| `pydantic` | 数据模型验证 |
| `pluggy` | 插件管理 |
| `lxml` | XML 处理 |
| `pandas` | 数据分析 |

### 2.3 插件系统选型

使用 **pluggy** 作为插件管理方案，其为 pytest 同款框架，提供成熟的钩子机制。

### 2.4 配置文件格式

| 格式 | 场景 |
|------|------|
| **TOML** (`pyproject.toml`) | 项目级配置、构建配置 |
| **JSON** (`manifest.json`) | 模块元数据、运行时配置 |

---

## 3. 项目目录结构

### 3.1 完整目录树

```
lv-game-toolkit/                              # 项目根目录
│
│  ── 项目级配置文件 ──
├── .gitignore
├── .gitattributes
├── .editorconfig                             # 跨 IDE 编码格式规范
├── pyproject.toml                            # Python 项目配置
├── README.md
│
│  ── Speckit 主实例 ──
├── .specify/                                 # 主 Speckit 工具配置（框架级）
│   ├── memory/                               #   AI 项目上下文记忆
│   ├── scripts/                              #   自动化脚本
│   │   ├── bash/
│   │   │   └── common.sh
│   │   └── powershell/
│   │       └── common.ps1
│   ├── templates/                            #   Handlebars 模板
│   └── out/                                  #   临时输出（gitignored）
│
├── specs/                                    # 主项目 Spec 文档（框架/全局级）
│   ├── 001-plugin-system/
│   │   ├── spec.md
│   │   ├── plan.md
│   │   └── tasks.md
│   ├── 002-cli-framework/
│   ├── 003-gui-framework/
│   └── 004-event-bus/
│
│  ── Cursor AI 规则 ──
├── .cursor/
│   └── rules/                                # 全局规则（对所有子目录生效）
│       ├── coding-standards.mdc
│       ├── module-conventions.mdc
│       ├── commit-conventions.mdc
│       └── project-structure.mdc
│
│  ── Git/GitHub 协作 ──
├── .github/
│   ├── COMMIT_MSG_TEMPLATE.md
│   └── COMMIT_使用说明.md
│
│  ── 架构设计文档 ──
├── doc/architecture/                            # 架构设计（纳入 Git）
│   ├── 项目重新设计的需求.md
│   ├── architecture-overview.md
│   ├── technical-decisions.md
│   └── learning-roadmap.md
│
│  ━━ 核心框架源码 ━━
├── toolkit/
│   ├── __init__.py                           #   版本号定义
│   ├── app.py                                #   应用引导器
│   │
│   ├── core/                                 #   核心服务层
│   │   ├── __init__.py
│   │   ├── plugin_manager.py                 #     pluggy 插件管理器
│   │   ├── hookspecs.py                      #     钩子规范定义
│   │   ├── event_bus.py                      #     事件总线
│   │   ├── workflow_engine.py                #     可配置工作流引擎
│   │   ├── service_registry.py               #     服务注册表
│   │   ├── config_manager.py                 #     全局配置管理
│   │   ├── adb_manager.py                    #     ADB 设备管理
│   │   ├── db_manager.py                     #     SQLite 数据库管理
│   │   ├── process_bridge.py                 #     外部进程桥接
│   │   ├── logger.py                         #     日志服务
│   │   └── perfdog/                          #     PerfDog 导出解析与洞察（规格 specs/004，实现记录见 plan.md#实现记录）
│   │
│   ├── sdk/                                  #   公共 SDK
│   │   ├── __init__.py
│   │   ├── base_plugin.py                    #     插件基类
│   │   ├── models.py                         #     公共数据模型（Pydantic）
│   │   ├── protocols.py                      #     接口协议定义
│   │   ├── exceptions.py                     #     统一异常体系
│   │   ├── constants.py                      #     全局常量
│   │   └── utils.py                          #     通用工具函数
│   │
│   ├── gui/                                  #   GUI 框架
│   │   ├── __init__.py
│   │   ├── main_window.py                    #     主窗口
│   │   ├── base_tab.py                       #     Tab 基类
│   │   ├── widgets/                          #     通用 UI 组件库
│   │   │   ├── __init__.py
│   │   │   ├── device_selector.py
│   │   │   ├── file_picker.py
│   │   │   ├── log_viewer.py
│   │   │   ├── progress_panel.py
│   │   │   ├── data_table.py
│   │   │   └── status_bar.py
│   │   └── themes/
│   │       ├── dark.qss
│   │       └── light.qss
│   │
│   └── cli/                                  #   CLI 框架
│       ├── __init__.py
│       ├── main.py                           #     CLI 入口（typer app）
│       ├── base_command.py                   #     命令基类
│       └── formatters.py                     #     输出格式化器
│
│  ━━ 功能模块目录 ━━
├── modules/
│   │
│   ├── device_disguise/                      #   模块：设备伪装
│   │   ├── .specify/                         #     模块 Speckit
│   │   │   ├── memory/
│   │   │   ├── scripts/
│   │   │   ├── templates/
│   │   │   └── out/
│   │   ├── specs/                            #     模块 Spec 文档
│   │   │   └── 001-core-feature/
│   │   │       ├── spec.md
│   │   │       ├── plan.md
│   │   │       └── tasks.md
│   │   ├── AGENTS.md                         #     模块级 AI 规则
│   │   ├── manifest.json                     #     模块元数据
│   │   ├── src/                              #     源代码
│   │   │   ├── __init__.py
│   │   │   ├── plugin.py                     #       插件注册入口
│   │   │   ├── service.py                    #       业务逻辑
│   │   │   ├── models.py                     #       数据模型
│   │   │   ├── gui_tab.py                    #       GUI Tab
│   │   │   ├── cli_commands.py               #       CLI 命令
│   │   │   └── migrations/                   #       数据库迁移脚本
│   │   │       └── 001_create_tables.sql
│   │   ├── assets/                           #     素材资源
│   │   ├── data/                             #     运行时数据（gitignored）
│   │   │   └── .gitkeep
│   │   ├── fixtures/                         #     测试固件（纳入 git）
│   │   └── tests/                            #     单元测试
│   │       ├── __init__.py
│   │       └── test_service.py
│   │
│   ├── game_perf/                            #   模块：游戏性能配置
│   │   └── （同上标准结构）
│   ├── perfetto_capture/                     #   模块：Perfetto 卡顿抓取
│   ├── perfdog_insights/                     #   模块：PerfDog 分析（实现记录见 specs/004-perfdog-import-insights/plan.md#实现记录）
│   ├── log_analysis/                         #   模块：日志分析（规划中）
│   ├── trace_analysis/                       #   模块：Trace 分析（规划中）
│   ├── policy_report/                        #   模块：策略报告对比（规划中）
│   ├── test_data_compare/                    #   模块：测试数据对比（规划中）
│   ├── policy_predict/                       #   模块：策略预测（规划中）
│   └── agent_chat/                           #   模块：Agent 对话（规划中）
│
│  ━━ 脚本 & 工具 ━━
├── scripts/
│   ├── build.py                              #   构建脚本
│   ├── new_module.py                         #   新模块生成器
│   ├── sync_rules.py                         #   全局规则同步脚本
│   ├── doc/
│   │   ├── build.md
│   │   ├── new_module.md
│   │   └── sync_rules.md
│   └── templates/                            #   脚手架模板文件
│       ├── manifest.json.tpl
│       ├── plugin.py.tpl
│       ├── AGENTS.md.tpl
│       └── spec.md.tpl
│
│  ━━ 文档 & 数据 ━━
├── doc/
│   ├── architecture.md
│   ├── developer-guide.md
│   ├── module-dev-guide.md
│   ├── cli-reference.md
│   ├── speckit-guide.md
│   └── design/
│       ├── ui-design.md
│       └── assets/
│
├── data/                                     #   全局运行时数据（gitignored）
│   ├── config/                               #     配置文件
│   │   ├── toolkit_config.json               #       全局配置（JSON）
│   │   └── <module>_<file>                   #       模块配置（构建时从 modules/*/config/ 复制）
│   ├── db/                                   #     数据库
│   │   └── toolkit.db                        #       SQLite 主数据库
│   │   └── <module>_<db>.db                  #       模块数据库
│   ├── backup/                               #     备份文件
│   │   └── <module>/                         #       模块备份目录
│   ├── reports/                              #     报告文件（Markdown，AI可读）
│   ├── traces/                               #     Trace 原始文件
│   ├── logs/                                 #     日志原始文件
│   └── exports/                              #     导出文件
│
├── tests/                                    #   集成测试
│   ├── conftest.py
│   ├── test_plugin_loading.py
│   ├── test_cli_integration.py
│   └── test_data_pipeline.py
│
└── checklists/
    ├── requirements.md
    └── module-review.md
```

### 3.2 目录设计说明

- **`toolkit/`**：主 Speckit 管理的部分，只有框架维护者修改。提供 SDK、基类、公共服务
- **`modules/`**：子 Speckit 管理的部分，各开发者独立开发各自模块。通过 manifest.json 注册，遵循 toolkit/sdk/ 定义的接口
- **模块命名规范**：使用 snake_case（如 `device_disguise`），与 Python 包命名一致

### 3.3 模块内标准目录

| 目录/文件 | 必须 | 说明 |
|-----------|------|------|
| `manifest.json` | ✅ | 模块元数据 |
| `AGENTS.md` | ✅ | 子 Speckit 规则 |
| `spec/` | ✅ | 功能规格、数据模型、设计文档 |
| `src/plugin.py` | ✅ | 插件注册入口 |
| `src/service.py` | ✅ | 业务逻辑 |
| `src/gui_tab.py` | ⭕ | GUI Tab（provides.gui=true 时必须） |
| `src/cli_commands.py` | ⭕ | CLI 命令（provides.cli=true 时必须） |
| `assets/` | ⭕ | 素材资源（按需） |
| `data/` | ⭕ | 运行时数据（gitignored） |
| `fixtures/` | ⭕ | 测试固件（纳入 git） |
| `tests/` | ✅ | 测试代码 |

### 3.4 管理归属

| 目录 | 归属 | 谁来维护 |
|------|------|---------|
| `toolkit/` | 🔷 主框架 | 框架维护者 |
| `scripts/` | 🔷 主框架 | 框架维护者 |
| `doc/` | 🔷 主框架 | 框架维护者 |
| `data/` | 🔷 主框架 | 运行时自动管理 |
| `tests/`（根级） | 🔷 主框架 | 框架维护者（跨模块集成测试） |
| `modules/xx/` | 🔶 各模块 | 模块开发者 |
| `modules/xx/tests/` | 🔶 各模块 | 模块开发者（模块内单元测试） |

### 3.5 数据存放策略

采用**分布式方案 + 全局共享层**：

- **全局配置**：`data/config/toolkit_config.json` — 全局配置（主题、ADB 路径等）
- **模块配置**：`modules/<name>/config/<file>`（开发）→ `data/config/<name>_<file>`（打包）— 构建时从模块 config 目录复制，扁平命名避免冲突
- **数据库**：`data/db/` — 命名规范 `<module>_<db>.db`（如 `toolkit.db`、`agent_chat_conversation.db`）
- **备份文件**：`data/backup/<module>/` — 模块备份文件（如 `data/backup/game_perf/`）
- **测试固件**：`modules/<name>/fixtures/` — 测试样本数据（纳入 git）
- **跨模块数据交换**：通过事件总线和服务注册表，不通过文件目录

---

## 4. 核心框架设计

### 4.1 插件系统

#### 工作流程

```
应用启动
    │
    ▼
Plugin Manager 初始化
  1. 扫描 modules/ 目录
  2. 读取 manifest.json
  3. 检查依赖关系
  4. 按依赖顺序加载模块
  5. 注册 pluggy hooks
    │
    ▼
各模块初始化
  plugin.register()
    → 注册 CLI 命令
    → 注册 GUI Tab
    → 注册 Agent 工具
    → 注册事件监听
    │
    ▼
应用就绪
```

#### Hookspec 定义

```python
# toolkit/core/hookspecs.py
import pluggy

hookspec = pluggy.HookspecMarker("lv_toolkit")
hookimpl = pluggy.HookimplMarker("lv_toolkit")

class ToolkitHookSpec:

    @hookspec
    def get_plugin_info(self) -> dict:
        """返回模块信息"""

    @hookspec
    def register_cli_commands(self, cli_app) -> None:
        """注册 CLI 子命令到 typer app"""

    @hookspec
    def register_gui_tab(self) -> "BaseTab | None":
        """返回 GUI Tab 实例"""

    @hookspec
    def register_agent_tools(self) -> list:
        """返回 Agent 可调用的工具列表"""

    @hookspec
    def on_startup(self, context: dict) -> None:
        """应用启动时的初始化"""

    @hookspec
    def on_shutdown(self) -> None:
        """应用关闭时的清理"""
```

#### 模块实现示例

```python
# modules/device_disguise/src/plugin.py
from toolkit.core.hookspecs import hookimpl
from toolkit.sdk.base_plugin import BasePlugin

class DeviceDisguisePlugin(BasePlugin):

    @hookimpl
    def get_plugin_info(self) -> dict:
        return {
            "name": "device_disguise",
            "display_name": "设备伪装工具",
            "version": "1.0.0",
        }

    @hookimpl
    def register_cli_commands(self, cli_app):
        from .cli_commands import device_app
        cli_app.add_typer(device_app, name="device")

    @hookimpl
    def register_gui_tab(self):
        from .gui_tab import DeviceDisguiseTab
        return DeviceDisguiseTab()

    @hookimpl
    def register_agent_tools(self) -> list:
        return []

    @hookimpl
    def on_startup(self, context: dict):
        self.adb = context["adb_manager"]

    @hookimpl
    def on_shutdown(self):
        pass
```

### 4.2 事件总线

模块间松耦合通信，模块不需要直接引用其他模块。

```python
# toolkit/core/event_bus.py
class EventBus:
    def on(self, event: str, callback: Callable):
        """注册事件监听"""

    def off(self, event: str, callback: Callable):
        """移除事件监听"""

    def emit(self, event: str, **kwargs: Any):
        """触发事件"""
```

#### 事件命名规范

```
{模块名}.{动作}

device.connected            设备连接
device.disconnected         设备断开
device_disguise.disguised   设备已伪装
device_disguise.restored    设备已恢复
log_analysis.started        日志分析开始
log_analysis.progress       日志分析进度
log_analysis.complete       日志分析完成
game_perf.config_pushed     性能配置已推送
workflow.stage_complete     工作流阶段完成
```

### 4.3 可配置工作流引擎

Agent 是核心编排者，可按任意顺序调用模块。工作流引擎允许用户/Agent 自定义步骤组合并保存为可复用模板。

```
          ┌─────────────┐
          │   Agent     │
          │  (编排中心)  │
          └──────┬──────┘
                 │
    可以按任意顺序、任意组合调用
                 │
   ┌─────┬──────┼──────┬──────┐
   ▼     ▼      ▼      ▼      ▼
 设备   性能   日志   Trace  预测
 伪装   配置   分析   分析   ...
```

#### 工作流配置格式

```json
{
    "name": "性能全分析流程",
    "description": "从 trace 和日志全面分析性能，给出优化建议",
    "steps": [
        {
            "id": "step_1",
            "module": "trace_analysis",
            "action": "analyze",
            "input_mapping": { "trace_file": "$input.trace_file" }
        },
        {
            "id": "step_2",
            "module": "log_analysis",
            "action": "analyze",
            "input_mapping": { "log_file": "$input.log_file" },
            "parallel_with": "step_1"
        },
        {
            "id": "step_3",
            "module": "policy_predict",
            "action": "predict",
            "depends_on": ["step_1", "step_2"],
            "input_mapping": {
                "trace_result": "$step_1.output",
                "log_result": "$step_2.output"
            }
        }
    ]
}
```

#### 工作流引擎接口

```python
# toolkit/core/workflow_engine.py
class WorkflowEngine:
    def create_workflow(self, config: dict) -> Workflow: ...
    def run_workflow(self, workflow: Workflow, input_data: dict) -> dict: ...
    def save_workflow(self, name: str, config: dict): ...
    def list_workflows(self) -> list[str]: ...
    def load_workflow(self, name: str) -> dict: ...
```

### 4.4 服务注册表

Agent 通过 ServiceRegistry 发现和调用工具。

```python
# toolkit/core/service_registry.py
class ServiceRegistry:
    def register(self, name: str, service: Any): ...
    def get(self, name: str) -> Any: ...
    def list_services(self) -> list[str]: ...
    def get_service_schema(self, name: str) -> dict:
        """获取服务的输入/输出 JSON Schema，Agent 用此了解调用方式"""
```

### 4.5 配置管理

```python
# toolkit/core/config_manager.py
class ConfigManager:
    def get(self, key: str, module: str = None) -> Any: ...
    def set(self, key: str, value: Any, module: str = None): ...
```

### 4.6 外部进程桥接

用于集成其他技术栈（如 QML）的工具，通过标准化的 JSON stdin/stdout 交互。

```python
# toolkit/core/process_bridge.py
class ProcessBridge:
    def call(self, executable: str, args: list[str],
             input_data: dict = None, timeout: int = 30) -> dict: ...
```

### 4.7 数据库管理

采用 **混合存储方案**：JSON 文件（配置）+ SQLite（结构化数据）+ 文件系统（大型文档/报告）。

#### 存储分层

| 存储方式 | 适用数据 | 举例 |
|---------|---------|------|
| **JSON 文件** | 全局配置、简单键值对 | ADB 路径、主题设置 |
| **SQLite 数据库** | 结构化记录、需要查询/过滤/关联 | 设备库、分析结果、报告索引 |
| **文件系统** | 大型文档、AI 需要读取的原始内容 | Trace 文件、性能报告、日志 |

#### 数据库位置

```
data/
├── config/                       # 配置文件
│   ├── toolkit_config.json       # 全局配置
│   └── <module>_<file>           # 模块配置（构建时从 modules/*/config/ 复制，扁平命名）
├── db/                           # 数据库
│   ├── toolkit.db                # SQLite 主数据库
│   └── <module>_<db>.db          # 模块数据库（命名规范：模块名_功能.db）
├── backup/                       # 备份文件
│   └── <module>/                 # 模块备份目录
├── reports/                      # 报告文件（AI 可直接读取 Markdown）
├── traces/                       # Trace 原始文件
├── logs/                         # 日志原始文件
└── exports/                      # 导出文件
```

#### 关键表结构

**公共表**：
- `devices` — 设备记录（序列号、品牌、型号等）
- `workflow_runs` — 工作流执行记录
- `analysis_results` — 分析结果索引（含报告文件路径，各分析模块共用）
- `comparisons` — 报告对比记录

**模块表**（由各模块迁移脚本管理）：
- `device_profiles` — 设备伪装配置库
- `disguise_history` — 伪装操作记录
- `perf_push_history` — 性能配置推送记录

#### 模块数据库迁移

每个模块在 `src/migrations/` 下放置 SQL 迁移脚本，框架在加载模块时自动执行：

```
modules/device_disguise/src/migrations/
├── 001_create_tables.sql
└── 002_add_notes_column.sql
```

#### Agent 与报告文件的交互

报告存储为 Markdown 文件，AI Agent 可直接读取。数据库中 `analysis_results.report_file` 字段存储文件路径。

```python
# toolkit/core/db_manager.py
class DatabaseManager:
    def connect(self): ...
    def run_migrations(self, module_name, migrations_dir): ...
    def execute(self, sql, params=()): ...
    def close(self): ...
```

### 4.8 核心服务总览

| 服务 | 职责 | 模块可访问 |
|------|------|-----------|
| **PluginManager** | 模块发现、加载、生命周期管理 | ❌ 框架内部 |
| **EventBus** | 模块间松耦合事件通知 | ✅ 通过 context |
| **WorkflowEngine** | 可配置的预设流程 | ✅ 通过注册 stage |
| **ServiceRegistry** | 注册和查找模块服务 | ✅ 通过 context |
| **ConfigManager** | 分层配置读写 | ✅ 通过 context |
| **DatabaseManager** | SQLite 数据库管理 | ✅ 通过 context |
| **AdbManager** | ADB 设备管理 | ✅ 通过 context |
| **ProcessBridge** | 外部进程调用 | ✅ 通过 context |
| **Logger** | 统一日志输出 | ✅ 通过 context |

---

## 5. 模块开发规范

### 5.0 代码规则（总纲）

以下为仓库内 **代码与协作的硬性约定**，与 [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) 一致；细节实现另见 [module-development-guide.md](../knowledge/module-development-guide.md)、[development-pitfalls.md](../experience/development-pitfalls.md)。

| 类别 | 规则 |
|------|------|
| **最高准则** | 以 **Constitution** 为治理源；新功能优先 **Spec-Driven**（spec → plan → tasks → implement → analysis）。 |
| **语言与编码** | **Python 3.12+**；所有源码与文本输出 **UTF-8**。 |
| **格式与静态检查** | 遵守仓库根 [**`.editorconfig`**](../../.editorconfig)；使用 **Ruff** 做 lint（配置见根 `pyproject.toml`）。合并前对改动路径执行 `ruff check`，必要时 `ruff format`。 |
| **分层** | 业务逻辑在 **`service.py`**（纯同步、无 GUI/CLI 依赖）；**`gui_tab.py` / `cli_commands.py`** 只做展示与参数/输出；测试优先覆盖 **Service**。 |
| **依赖方向** | 模块 **禁止** 直接 `import` 其他模块的 `src/` 实现；跨模块通过约定接口、EventBus 等；允许依赖 **`toolkit.sdk.*`**、**`toolkit.core.hookspecs`**，**禁止**依赖 **`toolkit.core`** 内部实现模块（Constitution IV）。 |
| **框架修改** | 普通需求 **不得** 修改 **`toolkit/core/`、`toolkit/sdk/`**；确需改动须单独评审（Constitution VI）。 |
| **共享 context** | `plugin` 写入 `context` 的键 **必须** 带 **模块前缀**（如 `gp_service`），禁止占用通用键名（与 [P01](../experience/development-pitfalls.md#p01--插件-context-键名冲突严重) 一致）。 |
| **数据模型** | 跨 GUI/CLI/Agent 的结构化载荷 **Pydantic v2**；纯内部算法可用标准库/dataclass，边界选型见 [P12](../experience/development-pitfalls.md#p12--pydantic-vs-dataclass-选型)。 |
| **GUI 线程** | 耗时操作在 **`QThread`**（或等价）中执行，通过 **signal/slot** 回传结果；**禁止**在工作线程直接操作控件（[P05](../experience/development-pitfalls.md#p05--qthread-信号安全gui-线程通信)）。 |
| **子进程输出** | 读取 `AdbCmdResult` / `subprocess` 结果时 **`stdout`/`stderr` 使用 `or ""`**（[P02](../experience/development-pitfalls.md#p02--adb-命令输出可能为-none)）。 |
| **合并前** | 相关 **`pytest`** 通过；可运行 [`scripts/run_all_tests.py`](../../scripts/doc/run_all_tests.md) 做全量回归。 |
| **打包注意** | 发布构建见 [build.md](../../scripts/doc/build.md)；frozen 模式与资源路径遵守 [P13/P14](../experience/development-pitfalls.md)。 |

### 5.1 标准目录结构

```
modules/my_module/
├── .specify/                     # 模块 Speckit
├── specs/                        # 模块 Spec 文档
├── AGENTS.md                     # Cursor AI 开发规则
├── manifest.json                 # 模块元数据
├── src/
│   ├── __init__.py
│   ├── plugin.py                 # 插件注册入口（必须）
│   ├── service.py                # 业务逻辑层（必须）
│   ├── models.py                 # 模块数据模型
│   ├── gui_tab.py                # GUI Tab
│   └── cli_commands.py           # CLI 命令
├── assets/
├── data/
├── fixtures/
└── tests/
```

### 5.2 manifest.json 规范

```json
{
    "name": "device_disguise",
    "display_name": "设备伪装工具",
    "version": "1.0.0",
    "description": "修改 Android 设备的品牌、型号、厂商信息",
    "author": "开发者A",
    "python_requires": ">=3.12",
    "entry": "src.plugin",
    "service_entry": "src.service",
    "dependencies": {
        "toolkit_modules": [],
        "python_packages": ["lxml>=4.9.0"]
    },
    "provides": {
        "gui": true,
        "cli": true,
        "agent_tools": true,
        "workflow_stages": ["analyze", "compare"]
    },
    "cli_namespace": "device",
    "events": {
        "emits": ["device_disguise.disguised", "device_disguise.restored"],
        "listens": ["device.connected", "device.disconnected"]
    },
    "external_tools": []
}
```

#### 字段说明

| 字段 | 必须 | 说明 |
|------|------|------|
| `name` | ✅ | 模块唯一标识（snake_case） |
| `display_name` | ✅ | 显示名称 |
| `version` | ✅ | 语义化版本号 |
| `description` | ✅ | 功能描述 |
| `author` | ✅ | 作者 |
| `python_requires` | ✅ | Python 版本要求 |
| `entry` | ✅ | 插件入口模块路径 |
| `service_entry` | ✅ | 服务入口模块路径 |
| `dependencies` | ✅ | 依赖声明 |
| `provides` | ✅ | 能力声明 |
| `cli_namespace` | ⭕ | CLI 子命令命名空间 |
| `events` | ⭕ | 事件声明 |
| `external_tools` | ⭕ | 外部工具集成 |

### 5.3 开发标准流程

```
1. 初始化模块骨架
   python scripts/new_module.py --name my_module --display "模块名称"

2. 初始化模块 Speckit（关键步骤）
   cd modules/my_module
   uvx --from git+https://github.com/github/spec-kit.git specify init --here --no-git --ai cursor --script ps
   修改 .specify/scripts/powershell/common.ps1 应用 monorepo 补丁

3. 编写 Spec
   在 Cursor Agent 对话框中执行 /specify → spec.md
   /plan → plan.md
   /tasks → tasks.md

4. 实现业务逻辑
   service.py：核心功能，输入/输出用 Pydantic model
   models.py：定义数据模型

5. 实现插件注册
   plugin.py：实现 hookspecs 中定义的钩子

6. 实现表现层
   gui_tab.py：继承 BaseTab
   cli_commands.py：使用 typer 定义命令

7. 编写测试
   tests/test_service.py

8. 更新 manifest.json
```

### 5.4 service.py 编写规范

核心原则：
1. 不依赖 GUI 或 CLI（纯 Python 逻辑）
2. 输入/输出使用 Pydantic 模型
3. 所有方法都可以被 GUI/CLI/Agent 调用
4. 通过 context 获取共享服务

```python
# modules/my_module/src/service.py
from pydantic import BaseModel

class MyInput(BaseModel):
    """操作输入"""
    param_a: str
    param_b: int = 0

class MyResult(BaseModel):
    """操作结果"""
    success: bool
    data: dict
    message: str

class MyModuleService:
    def __init__(self, adb_manager, config_manager):
        self.adb = adb_manager
        self.config = config_manager

    def do_something(self, input: MyInput) -> MyResult:
        """执行操作"""
        ...
```

### 5.5 AGENTS.md 模板

```markdown
# 模块名称 — AI 开发规则

## 模块概述
[简要描述模块功能]

## 继承的全局规则
> - Python 3.12+，类型注解覆盖所有公共方法
> - 数据模型使用 Pydantic，输入输出结构化
> - 中文注释和文档字符串

## 模块边界约束
- ✅ 可以修改：src/、tests/、specs/、fixtures/
- ❌ 禁止修改：toolkit/、其他模块目录、项目根配置文件
- ✅ 可以导入：toolkit.sdk.*、toolkit.core.hookspecs
- ❌ 禁止导入：toolkit.core 内部实现、其他模块的 src/

## 模块特有规则
[模块特定的开发约束]
```

### 5.6 脚手架脚本

```
scripts/new_module.py 功能：
  --name：模块名称（snake_case）
  --display：中文显示名称
  --cli-namespace：CLI 命名空间（自动检查冲突）

自动创建完整模块骨架目录并生成模板文件。
```

---

## 6. Speckit 分层管理方案

### 6.1 分层架构

```
主 Speckit（项目根）
  职责：框架级 spec、全局 constitution、通用 SDK spec
  规则下发：.cursor/rules/ → 全局生效
            toolkit/sdk/ → 代码层面强制
            doc/ → 人类可读开发指南

  ▼ 规则继承

模块 Speckit（各模块目录）
  职责：模块功能 spec、模块内任务
  约束：继承全局规则、只能修改 src/、不可修改 toolkit/
```

### 6.2 规则传递机制

**层级 1：Cursor Rules（自动继承）**

`.cursor/rules/` 中的规则在主项目工作区自动对所有文件生效。当模块开发者单独打开模块目录时，通过脚手架将核心规则复制到模块的 `.cursor/rules/` 或 AGENTS.md 中。

**层级 2：AGENTS.md（模块级 AI 规则）**

每个模块的 AGENTS.md 继承全局规则要点 + 定义模块特有规则。

**层级 3：Code-Level 强制（SDK 接口）**

通过 BasePlugin 基类和 Protocol 类型在代码层面强制接口规范。

### 6.3 初始化流程

#### 前置环境要求

- Python 3.12+
- uv（提供 uvx 命令）：`pip install uv`

#### 主项目 Speckit 初始化

```powershell
cd lv-game-toolkit
uvx --from git+https://github.com/github/spec-kit.git specify init --here --ai cursor --script ps
```

#### 模块 Speckit 初始化

```powershell
cd modules/my_module
uvx --from git+https://github.com/github/spec-kit.git specify init --here --no-git --ai cursor --script ps
```

命令参数说明：
- `--here`：在当前目录初始化
- `--no-git`：不使用 git root 检测（模块级必须加，避免 specs 跑到项目根）
- `--ai cursor`：适配 Cursor 的提示词格式
- `--script ps`：生成 PowerShell 脚本（Windows）；Linux 用 `--script sh`

#### Monorepo 补丁

修改 `.specify/scripts/powershell/common.ps1` 中的 `Get-RepoRoot` 函数：

```powershell
function Get-RepoRoot {
    $scriptRelativeRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
    if ($scriptRelativeRoot -and (Test-Path (Join-Path $scriptRelativeRoot ".specify"))) {
        return $scriptRelativeRoot
    }
    try {
        $result = git rev-parse --show-toplevel 2>$null
        if ($LASTEXITCODE -eq 0) { return $result }
    } catch {}
    return $scriptRelativeRoot
}
```

### 6.4 协作场景

| 场景 | 操作方式 |
|------|---------|
| 框架维护者修改核心框架 | 在项目根目录打开 Cursor，使用主 Speckit |
| 模块开发者开发模块 | 在模块目录打开 Cursor（新窗口），使用模块 Speckit |
| 模块开发者查看框架 API | 在模块 Cursor 中打开 `toolkit/sdk/` 作为参考 |
| 更新全局规则 | 框架维护者修改 `.cursor/rules/`，运行同步脚本 |

### 6.5 规则同步机制

```
1. 框架维护者更新 .cursor/rules/
2. 运行 python scripts/sync_rules.py
   → 更新各模块的 AGENTS.md
3. git commit + push
4. 模块开发者 git pull 后自动获得最新规则
```

---

## 7. CLI 设计方案

### 7.1 设计目标

- **完整替代 GUI**：所有 GUI 能做的操作，CLI 都能做
- **Agent 友好**：输出结构化 JSON
- **人类友好**：默认 Rich 美化输出
- **模块自动注册**：新模块 CLI 命令自动挂载

### 7.2 命令结构

```
toolkit                              主命令
├── device                           设备伪装模块
│   ├── list                         列出设备
│   ├── disguise                     执行伪装
│   ├── restore                      恢复属性
│   └── profiles list|add|delete     配置管理
├── perf                             游戏性能模块
│   ├── parse                        解析 XML
│   ├── push                         推送配置
│   ├── backup                       备份配置
│   └── validate                     验证 XML
├── log                              日志分析（规划）
├── trace                            Trace 分析（规划）
├── policy                           策略报告（规划）
├── predict                          策略预测（规划）
├── workflow                         工作流管理
│   ├── list|run|create|delete
├── config                           全局配置
│   ├── show|set|reset
├── plugin                           插件管理
│   ├── list|info|status
└── version                          版本信息
```

### 7.3 输出格式

每个命令支持 `--format` 参数：

```powershell
# 默认 Rich 美化输出
toolkit device list

# JSON 格式（Agent 友好）
toolkit device list --format json
```

### 7.4 统一响应格式

```json
{
    "success": true,
    "data": {},
    "message": "操作成功",
    "errors": [],
    "metadata": {
        "timestamp": "2026-03-20T10:30:00",
        "module": "device_disguise",
        "command": "device list",
        "duration_ms": 150
    }
}
```

### 7.5 自动注册机制

框架通过 pluggy 钩子自动注册所有已加载模块的 CLI 命令，无需手动修改框架代码。

### 7.6 命名空间防冲突

三层防护：
1. `manifest.json` 声明 `cli_namespace`
2. PluginManager 加载时检查唯一性
3. 脚手架创建时预检查

预留命名空间（模块不可使用）：`config`、`plugin`、`workflow`、`version`、`help`、`gui`

---

## 8. GUI 框架设计

### 8.1 主窗口布局

混合模式：Agent Tab + 工具集 Tab

```
┌──────────────────────────────────────────────────────────────┐
│ 🔷 LV Toolkit │ 📱 ADB-001 Samsung S24 [已伪装] ▼ │🌙 ⚙️│─□✕│
├──────────────────────────────────────────────────────────────┤
│  [🤖 Agent]  [🔧 工具集]                                     │
├────────┬─────────────────────────────────────────────────────┤
│        │                                                     │
│ 📱伪装  │  当前选中模块的操作面板                                │
│ 🎮性能  │                                                     │
│ 📋日志  │  根据左侧导航选中的模块动态加载                        │
│ 📊Trace │                                                     │
│ 📈报告  │  所有模块的操作作用于 Title Bar 选中的设备              │
│ 🔮预测  │                                                     │
│        │                                                     │
├────────┴─────────────────────────────────────────────────────┤
│  模块: 6 已加载 | ADB: ✅ 正常                                │
└──────────────────────────────────────────────────────────────┘
```

### 8.2 Title Bar 设计

自定义标题栏，始终显示设备状态：

| 区域 | 内容 | 交互 |
|------|------|------|
| 应用 Logo + 名称 | `🔷 LV Toolkit` | 固定 |
| 设备信息区 | 设备序列号、品牌型号、伪装状态 | 点击 ▼ 展开设备列表（支持多选） |
| 主题切换 | 🌙/☀️ | 点击切换 |
| 设置 | ⚙️ | 打开设置面板 |
| 窗口控制 | ─ □ ✕ | 标准窗口操作 |

多设备时 Title Bar 显示 "N台设备已连接"，点击展开勾选框列表。

### 8.3 类层次结构

```
QMainWindow → MainWindow
  ├── CustomTitleBar
  ├── TopTabBar（Agent / 工具集）
  ├── AgentTab（预留）
  ├── ToolboxWidget
  │     ├── ModuleNavPanel（左侧导航）
  │     └── ModuleContentArea（右侧内容）
  │           └── BaseTab → 各模块 Tab
  ├── StatusBar
  └── SettingsDialog
```

### 8.4 BaseTab 基类

```python
class BaseTab(QWidget):
    def get_tab_info(self) -> dict: ...      # 名称、图标、排序
    def on_activated(self): ...              # Tab 被选中
    def on_deactivated(self): ...            # Tab 切走
    def set_context(self, context: dict): ...  # 注入共享服务
    def subscribe_events(self): ...          # 注册事件监听
```

### 8.5 通用 UI 组件库

| 组件 | 功能 |
|------|------|
| DeviceSelector | ADB 设备下拉选择器 |
| FilePicker | 文件选择器（支持拖拽） |
| LogViewer | 实时日志查看器 |
| ProgressPanel | 多步骤进度面板 |
| DataTable | 通用数据表格 |
| StatusBar | 底部状态栏 |

### 8.6 主题系统

提供 `dark.qss` 和 `light.qss` 两套主题，模块 GUI 使用框架定义的 CSS 类名确保主题切换一致。

---

## 9. Agent 智能助手模块

### 9.1 设计定位

Agent 智能助手（`modules/agent_chat/`）是项目的核心交互入口，通过 LLM 驱动的对话方式编排各模块工具，实现自动化性能分析工作流。所有模块按照「提供结构化 Service + 声明 Agent Tools」的规范开发，Agent 通过 `register_agent_tools` 钩子自动发现并调用各模块能力。

### 9.2 模块架构

```
modules/agent_chat/
├── src/
│   ├── models.py              ← Pydantic/dataclass 数据模型（AgentConfig, Message, ToolDefinition 等）
│   ├── service.py             ← AgentService 对话循环核心（LLM 调用 → 工具执行 → 递归）
│   ├── plugin.py              ← pluggy 注册入口（on_startup, register_gui_tab, register_cli 等）
│   ├── cli_commands.py        ← Typer CLI: agent ask / agent sop list / agent sop show
│   ├── gui_tab.py             ← PyQt6 GUI Tab（聊天、历史、SOP管理、设置）
│   ├── llm/
│   │   ├── base.py            ← LLMProvider 抽象基类（stream_chat, count_tokens）
│   │   ├── glm_provider.py    ← 智谱 GLM Provider（zhipuai SDK）+ 消息清洗
│   │   └── claude_provider.py ← Anthropic Claude Provider（anthropic SDK）
│   ├── tools/
│   │   ├── registry.py        ← ToolRegistry — 收集各模块工具 + 自动 JSON Schema 生成
│   │   ├── executor.py        ← ToolExecutor — 安全执行 + 结果序列化/截断 + report_paths 提取
│   │   └── builtin.py         ← 内置工具: create_workspace / list_workspace_files
│   ├── sop/
│   │   └── manager.py         ← SOPManager — 加载/导入/导出/删除 SOP Markdown 文档
│   ├── memory/
│   │   └── conversation.py    ← ConversationStore — SQLite 对话/消息持久化
│   ├── workflow/
│   │   ├── tracker.py         ← WorkflowTracker — 记录工具调用序列 + 沉淀条件检测
│   │   └── generator.py       ← SOP 自动生成: generate_sop_from_trace + save_sop
│   └── knowledge/
│       └── report_index.py    ← ReportIndex — 扫描历史报告目录提取摘要
├── config/
│   ├── config.json            ← 默认配置模板（开发路径: modules/agent_chat/config/config.json）
│   └── sops/                  ← 内置 SOP 文档（trace/perfdog/strategy/comprehensive）
├── tests/                     ← 10 个测试文件，208 项测试
└── specs/001-agent-core/      ← Speckit 工作流文档
```

### 9.3 对话循环（核心流程）

```
用户消息
  ↓
AgentService.chat()
  ↓ 构建 system prompt（SOP 元数据 + 工具列表 + 历史报告摘要）
  ↓ 加载对话上下文
  ↓
_run_loop（最多 10 轮递归）
  ↓ 调用 LLMProvider.stream_chat() 流式输出
  ↓
  ├── LLM 返回纯文本 → 保存消息 → 返回 LLMResponse
  └── LLM 返回 tool_use → ToolExecutor 执行 → 结果反馈 → 递归 _run_loop
      ↓ WorkflowTracker 记录每次工具调用
      ↓ 失败时自动重试 1 次
  ↓
检查工作流沉淀条件 → 触发 WORKFLOW_DEPOSIT 事件
```

### 9.4 工具注册协议

各模块通过 `register_agent_tools` 钩子暴露工具，格式与 LLM Function Calling 对齐：

```python
@hookimpl
def register_agent_tools(self) -> list:
    return [
        {
            "name": "pa_analyze",
            "description": "执行 Perfetto Trace 完整分析",
            "parameters": {
                "type": "object",
                "properties": {
                    "trace_path": {"type": "string", "description": "trace 文件路径"},
                },
                "required": ["trace_path"],
            },
            "method": self._service.analyze,
        },
    ]
```

ToolRegistry 自动增强：对缺少 `parameters` 的工具通过 `inspect.signature()` + `get_type_hints()` 自动生成 JSON Schema，并过滤 `Callable` 类型参数。

### 9.5 LLM Provider 体系

```python
class LLMProvider(ABC):
    def stream_chat(self, messages, tools=None, system_prompt="") -> Iterator[StreamChunk]: ...
    def count_tokens(self, messages) -> int: ...
    def get_available_models(self) -> list[str]: ...
    @property
    def provider_name(self) -> str: ...
```

| Provider | SDK | 预设模型 | 特性 |
|----------|-----|---------|------|
| GLM | `zhipuai` | glm-4-plus, glm-4-flash, glm-4-long | 默认 Provider，含消息清洗 (`_sanitize_messages`) |
| Claude | `anthropic` | claude-sonnet-4-20250514, claude-3-5-haiku | 复杂分析推荐，流式 tool_use 处理 |

### 9.6 SOP 工作流管理

SOP（Standard Operating Procedure）以 Markdown + YAML frontmatter 格式定义，指导 Agent 按步骤完成分析任务：

- **内置 SOP**：`assets/sops/` 下的预置流程（trace_analysis, perfdog_analysis, strategy_review, jank_comprehensive）
- **自定义 SOP**：`data/sops/` 下用户创建或自动沉淀的工作流
- **自动沉淀**：WorkflowTracker 检测到符合条件时（2+ 工具无 SOP / SOP 偏差），提示保存为新 SOP

### 9.7 GUI Agent Tab

AgentTab 继承 `BaseTab`，提供完整对话界面：

- 左侧 220px 固定面板：会话历史（按日期分组）+ SOP 树形管理
- 右侧聊天区：消息气泡（用户/Agent）+ 工具调用卡片（可折叠）+ 工作流沉淀卡片
- 输入区：自适应高度 QTextEdit + 发送/停止按钮 + 文件拖拽
- 设置弹窗：模型配置 + SOP 管理 + 高级设置
- 异步执行：`_AgentWorker(QThread)` + `pyqtSignal` 流式更新

### 9.8 已适配的模块工具

| 模块 | 注册工具 | 功能 |
|------|---------|------|
| perfetto_analysis | pa_analyze, pa_parse, pa_analyze_dims, pa_list_dims, pa_history | Trace 分析全流程 |
| perfdog_insights | pdi_load_report, pdi_summarize | PerfDog 报告解析 |
| game_perf | gp_analyze_config, perf_push, perf_reset, perf_info | 策略配置管理 |
| agent_chat (内置) | create_workspace, list_workspace_files | 分析工作目录管理 |

---

## 10. 构建与部署方案

### 10.1 构建目标

- 跨平台：Windows + Linux
- 解压即用：无需安装 Python
- 模块打包：所有已启用模块一起打包
- 体积可控：排除不需要的 Qt 模块

### 10.2 入口设计

```python
# toolkit/app.py
def main():
    if len(sys.argv) > 1:
        run_cli()     # 带参数 → CLI 模式
    else:
        run_gui()     # 无参数 → GUI 模式
```

使用方式：
- 双击 `Toolkit.exe` → GUI（无控制台窗口）
- 终端执行 `toolkit-cli plugin list` → CLI

### 10.3 双入口构建策略

```
lv-game-toolkit-v1.0.0-windows/
├── Toolkit.exe            # console=False，GUI 入口（双击启动）
├── toolkit-cli.exe        # console=True，CLI 入口（终端使用）
├── _internal/             # 共享运行时
│   ├── modules/           #   模块文件
│   └── assets/            #   资源文件（app.ico 等）
├── data/                  # 运行时数据目录
└── adb/                   # 可选 ADB 工具
```

构建命令：`python scripts/build.py`（详见 [构建脚本文档](../../scripts/doc/build.md)）

### 10.4 跨平台构建

PyInstaller 不支持交叉编译，需在目标平台上分别构建：
- Windows → `lv-game-toolkit-v1.0.0-windows.zip`
- Linux → `lv-game-toolkit-v1.0.0-linux.tar.gz`

### 10.5 版本管理

版本号在 `pyproject.toml` 中统一管理，`toolkit/__init__.py` 和构建脚本从中读取。

---

## 11. 协作流程与规范

### 11.1 团队角色分工

| 角色 | 职责 | 管理范围 |
|------|------|---------|
| 框架维护者 | 核心框架、SDK、全局规则、构建 | `toolkit/`、`.cursor/rules/`、`scripts/` |
| 模块开发者 | 独立功能模块 | `modules/{自己的模块}/` |
| 集成测试负责人 | 跨模块集成测试 | `tests/` |

### 11.2 开发流程

```
1. 需求确认
2. 创建模块骨架（scripts/new_module.py）
3. 初始化模块 Speckit
4. 编写 Spec（/specify → /plan → /tasks）
5. 开发实现（/implement）
6. 测试（pytest）
7. 代码审查 & 合并（PR）
8. 构建发布
```

### 11.3 Git 分支策略

```
main                    稳定发布
  ├── develop           开发集成
  │     ├── feature/*   功能分支
  │     └── fix/*       修复分支
  └── release/*         发布准备
```

| 分支类型 | 命名 | 从哪分出 | 合并到 |
|---------|------|---------|--------|
| main | 固定 | — | — |
| develop | 固定 | main | main |
| feature/* | `feature/{模块}-{功能}` | develop | develop |
| fix/* | `fix/{描述}` | develop | develop |
| release/* | `release/v{版本}` | develop | main + develop |

### 11.4 提交规范

```
<type>(<scope>): <subject>

type: feat / fix / refactor / docs / test / chore
scope: framework / sdk / gui / cli / {模块名}

示例：
  feat(device_disguise): 添加批量伪装功能
  fix(framework): 修复插件加载顺序问题
  docs(sdk): 更新 BasePlugin 文档
```

### 11.5 Git 管理策略

**纳入 Git 的内容**：
- 源代码（`toolkit/`、`modules/*/src/`）
- Spec 文档（`specs/`）
- 配置声明（`pyproject.toml`、`manifest.json`）
- 测试代码和固件（`tests/`、`fixtures/`）
- Speckit 配置（`.specify/memory/`、`.specify/scripts/`、`.specify/templates/`）
- 编码格式规范（`.editorconfig`）
- 模板文件（`scripts/templates/`）

**不纳入 Git 的内容**：
- 虚拟环境（`.venv/`）— pip install 可重建
- 构建产物（`dist/`、`build/`）— 构建脚本可重建
- 运行时数据（`data/config/`、`data/db/`、`data/backup/`）— 运行时生成
- Python 缓存（`__pycache__/`）— 自动生成
- Speckit 临时输出（`.specify/out/`）— 命令可重建
- IDE 个人配置（`.idea/`、`.vscode/`）— 个人偏好
- 打包文件（`*.zip`、`*.tar.gz`）— 构建脚本可重建
- 架构设计文档已迁移至 `doc/architecture/`（纳入 Git）

---

> 文档版本：v1.1.0
> 创建日期：2026-03-20
> 最后更新：2026-03-20
