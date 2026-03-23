# Perfetto卡顿抓取模块 Constitution

## 目录

- [继承关系](#继承关系)
- [模块边界约束](#模块边界约束)
- [技术约束](#技术约束)
  - [Ring buffer 自动估算](#ring-buffer-自动估算)
  - [Trace 本机输出路径](#trace-本机输出路径)
- [开发规范](#开发规范)

## 继承关系

本模块 Constitution 继承自项目根 Constitution（`../../.specify/memory/constitution.md`），所有根 Constitution 中定义的原则、技术栈约束和开发流程均 MUST 适用于本模块。

以下仅补充模块级约束，不重复根级内容。

## 模块边界约束

- ✅ 可以修改：`src/`、`tests/`、`specs/`、`fixtures/`
- ❌ 禁止修改：`toolkit/`、其他模块目录、项目根配置文件
- ✅ 可以导入：`toolkit.sdk.*`、`toolkit.core.hookspecs`
- ❌ 禁止导入：`toolkit.core` 内部实现（plugin_manager、db_manager 等）、其他模块的 `src/`
- 插件 context 键名 MUST 使用 `pe_` 前缀（如 `pe_service`、`pe_adb`）

## 技术约束

### Ring buffer 自动估算

- 标定基线速率 **LIGHT_RATE_KB_PER_SEC = 9200**（KB/s），对应实测 **约 90 MB / 10 s** 量级
- 超过轻载阈值后每 tag 附加速率 **HEAVY_PER_CAT_RATE_KB = 2600**（KB/s）；**tag** 含 atrace category 与 ftrace event，二者均计入 `total_tags`（与 `calculate_buffer_size(..., ftrace_count=...)` 一致）
- 安全系数 **buffer_safety_factor** 默认 **1.2**；结果 clamp 至 **MIN_BUFFER_KB = 91136**、**MAX_BUFFER_KB = 512000**（约 89 MB～500 MB）
- 具体公式与验收口径以 `specs/002-auto-buffer/spec.md` 为准

### Trace 本机输出路径

- **开发模式**：MUST 将会话导出写入模块数据目录下 **`data/output/trace/`**（`output` 为配置项 `output_dir`）
- **EXE 打包模式（`sys.frozen`）**：MUST 使用 **`<可执行文件所在目录>/output/trace/`** 作为根目录，保证用户与安装目录同盘可写、路径稳定

## 开发规范

- 遵循项目根 `scripts/doc/development-pitfalls.md` 中列出的踩坑指南
- 后台耗时操作 MUST 使用 `QThread` + `pyqtSignal` 与 GUI 线程通信
- service 层纯同步，MUST NOT 包含 PyQt6 代码

**Version**: 1.0.0 | **Last Updated**: auto-generated
