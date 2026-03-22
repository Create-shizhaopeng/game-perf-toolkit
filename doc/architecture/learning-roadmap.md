# 架构学习路线与材料

## 目录

- [1. 本项目涉及的核心概念](#1-本项目涉及的核心概念)
  - [1.1 插件化架构](#11-插件化架构)
  - [1.2 分层架构](#12-分层架构)
  - [1.3 事件驱动架构](#13-事件驱动架构)
  - [1.4 CLI 设计](#14-cli-设计)
  - [1.5 Agent / Tool Use 模式](#15-agent--tool-use-模式)
- [2. 推荐学习路线](#2-推荐学习路线)
  - [2.0 开始编码前（项目代码规则）](#20-开始编码前项目代码规则)
  - [2.1 入门阶段](#21-入门阶段)
  - [2.2 进阶阶段](#22-进阶阶段)
  - [2.3 深入阶段](#23-深入阶段)
- [3. 具体技术栈学习材料](#3-具体技术栈学习材料)
  - [3.1 pluggy 插件系统](#31-pluggy-插件系统)
  - [3.2 Typer CLI 框架](#32-typer-cli-框架)
  - [3.3 Pydantic 数据模型](#33-pydantic-数据模型)
  - [3.4 PyQt6 GUI](#34-pyqt6-gui)
  - [3.5 spec-kit 规范驱动开发](#35-spec-kit-规范驱动开发)
  - [3.6 PyInstaller 打包](#36-pyinstaller-打包)
- [4. 架构设计通用知识](#4-架构设计通用知识)
  - [4.1 设计原则](#41-设计原则)
  - [4.2 设计模式](#42-设计模式)
  - [4.3 推荐书籍](#43-推荐书籍)
- [5. 参考项目](#5-参考项目)

---

## 1. 本项目涉及的核心概念

### 1.1 插件化架构

**是什么**：应用核心框架定义接口（钩子），功能模块实现接口并注册，核心框架在运行时发现和加载模块。

**为什么重要**：使得新功能可以独立开发和部署，不修改核心框架代码。

**本项目应用**：pluggy 钩子系统 + manifest.json 模块声明。

**学习关键词**：Plugin Architecture, Hook System, Dependency Injection

### 1.2 分层架构

**是什么**：将系统按职责分为多个层次（表现层、服务层、核心层、数据层），每层只依赖下一层。

**为什么重要**：实现 GUI/CLI/Agent 三端共享同一套业务逻辑。

**本项目应用**：表现层（GUI/CLI/Agent）→ 服务 API → 核心框架 → 模块层。

**学习关键词**：Layered Architecture, Separation of Concerns, Hexagonal Architecture

### 1.3 事件驱动架构

**是什么**：组件通过发布/订阅事件来通信，而不是直接调用彼此。

**为什么重要**：模块间松耦合，一个模块的变化不影响其他模块。

**本项目应用**：EventBus 实现模块间异步通知。

**学习关键词**：Event-Driven Architecture, Pub/Sub, Observer Pattern

### 1.4 CLI 设计

**是什么**：通过命令行接口暴露应用功能，支持参数、选项、子命令。

**为什么重要**：让 AI Agent 能通过命令行调用工具获取数据。

**本项目应用**：Typer 框架，每个模块注册自己的子命令。

**学习关键词**：CLI Design, Command Pattern, POSIX Conventions

### 1.5 Agent / Tool Use 模式

**是什么**：AI Agent 根据用户意图，自动选择和调用合适的工具（函数），组合多个工具完成复杂任务。

**为什么重要**：这是本项目的远期核心形态。

**本项目应用**：ServiceRegistry + register_agent_tools 钩子 + LLM Function Calling。

**学习关键词**：Function Calling, Tool Use, ReAct, Agent Framework

---

## 2. 推荐学习路线

### 2.0 开始编码前（项目代码规则）

动手改 `modules/` 或 `toolkit/` 前，请先阅读 **[architecture-overview.md §5.0 代码规则（总纲）](./architecture-overview.md#50-代码规则总纲)** 与 **`.specify/memory/constitution.md`**。其中约定：分层（Service / GUI / CLI）、Ruff + `.editorconfig`、context 键模块前缀、框架边界与合并前测试等。再按需查阅 [module-development-guide.md](../../scripts/doc/module-development-guide.md)、[development-pitfalls.md](../../scripts/doc/development-pitfalls.md)。

### 2.1 入门阶段

目标：理解本项目用到的具体技术。

```
1. Python 高级特性
   └─ 类型注解、抽象基类、Protocol、dataclass
   └─ importlib 动态导入
   └─ 异步编程基础（asyncio）

2. pluggy 插件框架
   └─ 官方文档 + 示例
   └─ 钩子规范定义和实现
   └─ 插件发现和加载

3. Typer CLI 框架
   └─ 官方教程
   └─ 子命令、选项、参数
   └─ Rich 美化输出

4. Pydantic 数据验证
   └─ Model 定义
   └─ JSON Schema 生成
   └─ 数据序列化/反序列化
```

### 2.2 进阶阶段

目标：理解架构设计的原理。

```
1. SOLID 设计原则
   └─ 单一职责、开闭原则、依赖反转
   └─ 在插件系统中的应用

2. 设计模式
   └─ 观察者模式（EventBus）
   └─ 策略模式（LLMProvider）
   └─ 工厂模式（PluginManager）
   └─ 注册表模式（ServiceRegistry）

3. 分层架构实践
   └─ 表现层 vs 业务层 vs 数据层
   └─ 如何实现层间解耦

4. spec-kit 规范驱动开发
   └─ 需求 → 方案 → 任务 → 实现 的流程
   └─ constitution.md 的编写
```

### 2.3 深入阶段

目标：能独立设计类似系统。

```
1. 微内核架构（Microkernel Architecture）
   └─ 核心系统 + 插件模块
   └─ 与本项目架构的对应关系

2. Agent 架构
   └─ LLM Function Calling / Tool Use
   └─ ReAct 模式
   └─ Agent 记忆和上下文管理

3. 构建系统设计
   └─ 模块化构建
   └─ 跨平台打包策略

4. 大型项目协作
   └─ Monorepo 管理最佳实践
   └─ 代码所有权和审查机制
```

---

## 3. 具体技术栈学习材料

### 3.1 pluggy 插件系统

| 资源 | 链接 |
|------|------|
| 官方文档 | https://pluggy.readthedocs.io/ |
| GitHub 仓库 | https://github.com/pytest-dev/pluggy |
| 实战教程 | 搜索 "pluggy tutorial python plugin system" |

**快速入门要点**：
- `HookspecMarker` 定义钩子接口
- `HookimplMarker` 标记钩子实现
- `PluginManager` 管理插件注册和调用
- 支持 firstresult、trylast 等排序控制

### 3.2 Typer CLI 框架

| 资源 | 链接 |
|------|------|
| 官方文档 | https://typer.tiangolo.com/ |
| GitHub 仓库 | https://github.com/tiangolo/typer |
| 官方教程 | https://typer.tiangolo.com/tutorial/ |

**快速入门要点**：
- 类型注解自动生成参数
- `typer.Typer()` 创建应用
- `app.command()` 定义命令
- `app.add_typer()` 添加子命令组

### 3.3 Pydantic 数据模型

| 资源 | 链接 |
|------|------|
| 官方文档 | https://docs.pydantic.dev/ |
| GitHub 仓库 | https://github.com/pydantic/pydantic |

**快速入门要点**：
- `BaseModel` 定义数据模型
- 自动类型验证和转换
- `.model_json_schema()` 生成 JSON Schema（Agent Tool 描述）
- `.model_dump()` / `.model_dump_json()` 序列化

### 3.4 PyQt6 GUI

| 资源 | 链接 |
|------|------|
| 官方文档 | https://www.riverbankcomputing.com/static/Docs/PyQt6/ |
| 教程网站 | https://www.pythonguis.com/pyqt6/ |

**本项目关注点**：
- QMainWindow 自定义标题栏
- QTabWidget 标签页管理
- QSS 主题样式
- 信号/槽机制与 EventBus 的配合

### 3.5 spec-kit 规范驱动开发

| 资源 | 链接 |
|------|------|
| 官方网站 | https://speckit.org/ |
| GitHub 仓库 | https://github.com/github/spec-kit |
| Monorepo 讨论 | https://github.com/github/spec-kit/issues/581 |
| Mono-repo 支持 | https://github.com/github/spec-kit/issues/790 |

**关键概念**：
- Constitution（宪法）：项目基本原则
- Specify → Clarify → Plan → Tasks → Implement 五阶段流程
- `.specify/` 目录与 `specs/` 目录的关系

### 3.6 PyInstaller 打包

| 资源 | 链接 |
|------|------|
| 官方文档 | https://pyinstaller.org/ |
| GitHub 仓库 | https://github.com/pyinstaller/pyinstaller |

**本项目关注点**：
- onedir 模式 vs onefile 模式
- hiddenimports 动态导入处理
- datas 资源文件打包
- 跨平台构建注意事项

---

## 4. 架构设计通用知识

### 4.1 设计原则

| 原则 | 说明 | 本项目应用 |
|------|------|-----------|
| **SOLID** | 面向对象五大原则 | BasePlugin 接口设计 |
| **KISS** | 保持简单 | 自研轻量组件优先于过度设计 |
| **DRY** | 不重复自己 | SDK 公共代码复用 |
| **YAGNI** | 不提前实现不需要的功能 | Agent 只做预留不实现 |

### 4.2 设计模式

| 模式 | 本项目应用 |
|------|-----------|
| **观察者模式** | EventBus 事件总线 |
| **策略模式** | LLMProvider 多后端切换 |
| **工厂模式** | PluginManager 模块创建 |
| **注册表模式** | ServiceRegistry 服务发现 |
| **模板方法模式** | BaseTab / BasePlugin 基类 |
| **命令模式** | CLI 命令封装 |

### 4.3 推荐书籍

| 书籍 | 适合阶段 | 说明 |
|------|---------|------|
| 《Clean Architecture》Robert C. Martin | 进阶 | 整洁架构，分层设计的经典 |
| 《Design Patterns》GoF | 进阶 | 设计模式圣经 |
| 《Python 架构模式》Harry Percival | 入门-进阶 | Python 项目的架构实践 |
| 《Fluent Python》Luciano Ramalho | 入门 | Python 高级特性 |
| 《Building AI Applications》 | 深入 | Agent 和 LLM 应用开发 |

---

## 5. 参考项目

| 项目 | 参考价值 | 链接 |
|------|---------|------|
| **pytest** | pluggy 插件系统的标杆实现 | https://github.com/pytest-dev/pytest |
| **Home Assistant** | Python 插件化架构的大型项目 | https://github.com/home-assistant/core |
| **Calibre** | Python + Qt 桌面应用 + 插件系统 | https://github.com/kovidgoyal/calibre |
| **Open Interpreter** | Agent + CLI + Tool Use 架构 | https://github.com/OpenInterpreter/open-interpreter |
| **LangChain** | Agent / Tool 调用模式 | https://github.com/langchain-ai/langchain |
| **Typer** | CLI 框架最佳实践 | https://github.com/tiangolo/typer |

---

> 文档版本：v1.0.0
> 创建日期：2026-03-20
