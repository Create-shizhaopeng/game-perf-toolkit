# Perfetto卡顿抓取 — AI 开发规则

## 目录

- [模块概述](#模块概述)
- [继承的全局规则](#继承的全局规则)
- [模块边界约束](#模块边界约束)
- [模块特有规则](#模块特有规则)
  - [Buffer 自动估算](#buffer-自动估算)
  - [Trace 输出路径](#trace-输出路径)
- [测试要求](#测试要求)

## 模块概述

自动化 Perfetto trace 的抓取、管理与导出，用于分析 Android 设备上的卡顿（jank）问题。支持 trace 配置管理、自动触发抓取、trace 文件管理与分析入口。

## 继承的全局规则

> 本模块遵循项目全局编码规范（详见项目根 `.cursor/rules/`）
> - Python 3.12+，类型注解覆盖所有公共方法
> - 数据模型：公共 API 用 Pydantic，模块内部用 dataclass
> - 中文注释和文档字符串
> - CLI 输出 SHOULD 支持 JSON 格式（渐进落地）
> - 插件 context 键名使用 `pe_` 前缀（如 `pe_service`、`pe_adb`）
> - 开发前 MUST 阅读 `doc/experience/development-pitfalls.md`

## 模块边界约束

- ✅ 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`
- ❌ 禁止修改：`toolkit/`、其他模块目录、项目根配置文件
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`
- ❌ 禁止导入：`toolkit.core` 内部实现、其他模块的 `src/`

## 模块特有规则

- ADB 操作通过 `context["pe_adb"]` 调用
- Perfetto 配置文件（.pbtx）存放在 `assets/` 目录
- 抓取完成后通过 EventBus 发布 `perfetto_capture.trace_ready` 事件
- Trace 文件路径和元数据持久化到数据库

### Buffer 自动估算

- Ring buffer 大小自动估算使用 **实测标定** 数据：轻载基线 **9200 KB/s**（约 **90 MB / 10 s** 换算），与 `buffer_safety_factor` 默认 **1.2**、上下限 **91136～512000 KB** 等一致；详见 `specs/002-auto-buffer/spec.md`
- **tag 总数** = atrace categories 数量 **+** ftrace events 数量；`calculate_buffer_size` 可传入 `ftrace_count`，与配置中的 `advanced.ftrace_events` 对齐

### Trace 输出路径

- **开发环境**：Trace 会话导出根目录为 `modules/perfetto_capture/data/output/trace/`（`output` 为配置项 `output_dir`，默认 `"output"`）
- **打包可执行文件（`sys.frozen`）**：根目录为 **`<exe 所在目录>/output/trace/`**

## 测试要求

- `service.py` 中每个公共方法至少一个测试用例
- 测试数据放在 `fixtures/` 目录
