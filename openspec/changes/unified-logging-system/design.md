## Context

当前项目存在**两套完全割裂的日志体系**：

1. **Python 标准 `logging`**（61+ 文件使用）：输出到 stdout，开发者只能在启动终端查看；不与 GUI 交互；无持久化；格式固定为纯文本。
2. **GUI `LogManager`**（注入 context）：仅服务于 GUI 底部面板展示，不支持文件持久化，不向终端输出，面向用户而非开发者。

两者互不打通，导致以下痛点：
- 后台异常/警告只能在终端看到，GUI 用户完全不知情
- GUI 面板日志在重启后全部丢失，无法追溯
- `perfetto_analysis/src/engine/` 下大量使用 `print(sys.stderr)`，污染终端且不可过滤
- 模块无法方便地输出结构化日志（字段化的分析事件），不利于后期自动化聚合

## Goals / Non-Goals

**Goals:**
- 建立统一日志入口，让模块只用一个接口，输出即可同时到达「终端 + GUI 面板 + 日志文件」
- 原生支持结构化日志输出（键值对最低，JSON Lines 优选），便于后续对分析模块的日志做自动化解析
- 日志文件持久化并支持轮转（按日期/大小），用户和开发者均可回溯
- 打通 Python `logging` 与 `LogManager`（GUI），让已有 `logging.getLogger(__name__)` 代码无需重写
- 减少终端 `print` 污染，统一去处

**Non-Goals:**
- 不替换 Rich 的 `console.print` 用于 CLI 的富文本输出（CLI 命令输出属于交互 UI，不是日志）
- 不改动模块业务逻辑，仅替换日志输出方式
- 不对 GUI 底部面板做完整重设计（仅增加必要过滤/搜索/导出功能）
- 不做分布式/远程日志收集（当前项目为桌面工具，无此需求）

## Decisions

### D1: 统一日志库选型 — 选择 `loguru`

| 方案 | 优势 | 劣势 | 适配成本 |
|------|------|------|---------|
| **loguru** | 零配置即开即用；内置结构化日志（`bind`）+ 文件轮转 + 自动异常跟踪；API 极简洁（一个 `logger` 对象）; 通过 `InterceptHandler` 可无缝桥接标准 `logging` | 需引入额外依赖（但 `loguru` 无传递依赖，非常轻量） | 低：新增一个库，少量框架代码适配 |
| **structlog** | 原生为结构化日志设计；可链式构建日志对象；与标准 `logging` 配合良好 | 配置复杂度高（需要自行组装处理器链）；无内置文件轮转；学习曲线陡 | 中：需要自己写大量胶水代码 |
| **原生 logging + QueueHandler + RotatingFileHandler** | 无需新依赖，标准库即搞定 | 配置代码冗长（Handler/Formatter/Filter 需手动组合）；结构化日志需手写 JSONFormatter；异常 traceback 处理不优雅；代码量大，后续维护成本高 | 高：需要写 200+ 行配置代码，且易出 bug |

**决策：** 选择 **`loguru`**。理由如下：
- **轻量无传递依赖**：`loguru` 仅一个包，无其他依赖树膨胀风险
- **API 极简**：`logger.info("done", foo=bar)` 即可完成结构化输出，对 61+ 使用文件的迁移极友好
- **内置轮转和压缩**：`logger.add("file.log", rotation="1 day", compression="zip")` 一行搞定
- **桥接标准 logging**：通过 `logging.basicConfig(handlers=[InterceptHandler()])` 可以让所有 `logging.getLogger()` 输出自动进入 `loguru` 体系，实现无痛兼容
- **异常捕获**：`logger.catch` 可自动装饰函数捕获异常，比 `try/except + log.error` 更简洁

### D2: 架构设计 — 三层路由模型

```
┌─────────────────────────────────────────────────────────────────────┐
│  模块调用层（Module Code）                                            │
│  ─────────────────────                                                │
│  方式1：from loguru import logger                                     │
│         logger.info("msg", key="val")                                 │
│                                                                       │
│  方式2：import logging（已有代码）                                    │
│         logging.getLogger(__name__).warning("msg")                     │
│         → 被 InterceptHandler 拦截，自动路由到 loguru                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  统一路由层（UnifiedLogger）                                          │
│  ───────────────────────                                            │
│  • 维护 Loguru 的 sink 列表                                          │
│     - StreamSink: stdout（终端输出）                                  │
│     - FileSink: data/logs/app_{date}.log（文件持久化，按天轮转）       │
│     - GUISink: 向 LogManager 发射 pyqtSignal（GUI 面板）            │
│  • 提供模块级别的 sink 注册（如 perfetto_analysis 单独一个文件）        │
│  • 负责日志级别过滤和格式化策略                                        │
└─────────────────────────────────────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   终端输出        │  │   日志文件        │  │   GUI 底部面板     │
│  (stdout)        │  │  data/logs/      │  │   BottomPanel      │
│                 │  │  按模块分文件      │  │   可过滤/搜索/导出  │
│   结构化格式:    │  │   按日期轮转       │  │   结构化日志折叠    │
│   key=value     │  │   自动压缩旧文件   │  │   展开即 JSON      │
└─────────────────┘  └──────────────────┘  └──────────────────┘
```

### D3: 结构化日志格式 — 优先「键值对文本」，可选 JSON Lines

**决策：** 对终端输出使用「键值对文本格式」（如 `2026-05-20 10:00:00 | INFO | module.name | event=analysis_done process=Game fps=59.8`），对文件输出和 GUI 面板内部则保留完整结构化数据。

理由：
- 键值对文本在终端中可读性远好于纯 JSON
- `loguru` 的 `bind()` 让这变得极简单：`logger.bind(foo="bar").info("msg")`
- 如果需要机器解析，文件 sink 可配置 `serialize=True` 直接输出 JSON Lines，无需修改调用代码
- GUI 面板可以解析绑定的字段，在界面中做「折叠/展开」展示

### D4: GUI 面板增强 — 最小必要改动

**决策：** 对 `BottomPanel` 做以下针对性的最小增强：
- **新增「控制台」源**：显示来自 `InterceptHandler` 的后台日志
- **搜索过滤**：在已有源过滤基础上增加文本搜索框，支持大小写不敏感匹配
- **导出当前过滤结果**：将面板中当前可见日志导出为 `.log` 文件
- **结构化日志展示**：对于带 `bind` 字段的日志，显示一个可折叠的字段面板

不改动面板布局的底层框架，只在现有基础上做加法。

### D5: `LogTextEdit` 处理 — 彻底移除

**决策：** 删除 `toolkit/gui/log_widget.py`（`LogTextEdit` 类），因为调研确认没有任何模块实际引用此组件。如果后续需要独立日志 widget，应由模块自己创建或提出新的共享组件需求。

### D6: `print()` 替换策略

**决策：**
- `perfetto_analysis/src/engine/` 下的 `print()`（约 15 处）全部替换为 `logger.info()` / `logger.warning()`
- `modules/*/plugin.py` 中的 startup `print()`（3 处）替换为 `logger.info()`
- `scripts/` 下的 `print()` 属于脚手架/脚本输出，不改动（这些不是应用运行时代码）

## Risks / Trade-offs

| Risk | 影响 | Mitigation |
|------|------|-----------|
| `loguru` 与 PyInstaller 打包不兼容（动态导入 sink） | 构建失败或日志不工作 | 提前在 build 脚本中测试，确认 `loguru` 的 hiddenimports 已正确配置；`loguru` 本身纯 Python，PyInstaller 支持良好 |
| 61+ 文件迁移工作量大，容易遗漏 | 部分日志仍以原生 logging 输出，体系不统一 | 先完成框架层（UnifiedLogger + InterceptHandler），大部分文件无需改动；只迁移明确需要结构化的文件；分阶段实施 |
| `InterceptHandler` 将 logging 发给 GUI 可能导致性能问题（高频日志阻塞 UI） | GUI 卡顿 | GUISink 使用非阻塞队列缓冲（`asyncio.Queue` 或 `collections.deque` + 定时批量 emit），避免逐条同步信号 |
| `game_perf` 硬编码颜色映射到 level 的逻辑不兼容新主题 | 亮色主题下颜色错误 | 修改 `_append_log()` 使其不再传递颜色字符串，改为直接传递 level 到 `theme_colors.get_colors()` |

## Migration Plan

1. **Phase 1 — 框架搭建（可独立回滚）**
   - 安装 `loguru` 依赖
   - 创建 `toolkit/core/unified_logger.py`（UnifiedLogger 类 + GUISink + InterceptHandler）
   - 修改 `toolkit/core/logger.py` 使其基于 UnifiedLogger
   - 在 `toolkit/app.py` 的 `setup_logging()` 中接入新体系
   - 验证：终端日志正常输出，GUI 面板新增「控制台」频道

2. **Phase 2 — 日志文件持久化**
   - 在 `data/logs/` 下启用文件 sink，配置按天轮转
   - 为关键模块启用模块级文件 sink（如 `perfetto_analysis`）
   - 验证：文件正确生成、轮转正常

3. **Phase 3 — `print()` 替换**
   - 扫描并替换 `perfetto_analysis/src/engine/` 下的 `print` 为 `logger`
   - 替换 `plugin.py` 中的 startup `print`
   - 验证：运行 module 测试，确认终端无新污染

4. **Phase 4 — GUI 面板增强**
   - BottomPanel 增加搜索框/导出按钮
   - 结构化日志字段折叠展示
   - 验证：搜索过滤和导出功能正常

5. **Phase 5 — 清理与收尾**
   - 移除 `toolkit/gui/log_widget.py`
   - 修复 `game_perf` 颜色问题
   - 更新 `docs/knowledge/module-development-guide.md` 的日志开发指南
   - 更新 `pyproject.toml` build hiddenimports
   - 回归测试全量测试

**回退方案：** 如果 `loguru` 在打包时出现问题，可快速回退到 Phase 1 之前的状态（基于标准 `logging` + 手动 `RotatingFileHandler` 的文件日志方案），因为 `InterceptHandler` 是可选桥接层，原生 `logging` 代码不受影响。

## Open Questions

1. 日志文件默认保留天数 — 建议 7 天轮转 + 30 天自动清理旧日志，待确认是否合理
2. `game_perf` 颜色硬编码的精确修改方案 — 需查看 `_append_log()` 实际代码后确定映射表
3. `perfetto_analysis` 是否需要独立的结构化日志文件（JSON Lines），还是统一放在 `app.log` 中即可
