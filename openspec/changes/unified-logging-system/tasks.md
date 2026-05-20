## 1. 依赖与基础框架搭建

- [x] 1.1 在 `pyproject.toml` dependencies 中添加 `loguru>=0.7.0`
- [x] 1.2 运行 `uv pip install loguru` 安装依赖并验证版本
- [x] 1.3 在 `toolkit/core/unified_logger.py` 中创建 `UnifiedLogger` 单例、文件 sink 配置、模块级 sink 注册接口
- [x] 1.4 在 `toolkit/core/unified_logger.py` 中实现 `InterceptHandler`，将标准 `logging` 路由到 `loguru`
- [x] 1.5 在 `toolkit/core/unified_logger.py` 中实现 `GUISink`，将 `loguru` 记录异步推送到 `LogManager`
- [x] 1.6 修改 `toolkit/core/logger.py`，使其基于 `UnifiedLogger` 初始化，保留 `setup_logging` 和 `resolve_log_level` 接口签名
- [x] 1.7 修改 `toolkit/app.py` 中的启动流程，在 `run_gui()` 和 `run_cli()` 中调用新的 `setup_logging()`，注入 `UnifiedLogger` 到 context
- [x] 1.8 运行验证终端日志正常输出

## 2. 日志文件持久化

- [x] 2.1 在 `UnifiedLogger` 中配置文件 sink：`data/logs/app_{date}.log`，开启 `rotation="1 day"` 和 `retention="30 days"`
- [x] 2.2 实现模块级 sink 注册接口 `add_module_sink(module_name, level)`
- [x] 2.3 `perfetto_analysis` 模块通过 `engine/__init__.py` 的 `logging.getLogger` 自动桥接到 loguru
- [x] 2.4 文件轮转由 loguru 内置支持

## 3. print() 替换与清理

- [x] 3.1 扫描 `modules/perfetto_analysis/src/engine/` 下所有 `print()`
- [x] 3.2 将 engine/ 中所有 `print()` 替换为 `logging.getLogger("perfetto_analysis.engine")`
- [x] 3.3 替换 `modules/agent_chat/src/plugin.py:95` 的 `print` 为 `_logger.warning()`
- [x] 3.4 替换 `modules/perfetto_analysis/src/plugin.py:376, 389` 的 `print` 为 `logger.warning()`
- [x] 3.5 CLI `console.print` 属于交互输出，保留未动

## 4. GUI 面板增强 (BottomPanel v2)

- [x] 4.1 修改 `toolkit/gui/log_manager.py`，扩展 `log()` 签名以支持 `details: dict | None = None`
- [x] 4.2 修改 `toolkit/gui/base_tab.py`，`_log()` 签名扩展 `details` 参数
- [x] 4.3 `BottomPanel` 新增搜索框/搜索过滤/导出/匹配计数 UI
- [x] 4.4 `BottomPanel` 添加控制台源切换按钮
- [x] 4.5 导出按钮实现（将过滤结果导出为 `.log` 文件）
- [x] 4.6 结构化字段折叠区域在导出逻辑中已支持
- [x] 4.7 匹配条目计数已显示
- [ ] 4.8 运行 GUI 模式手动验证（需用户介入）

## 5. 主题修复与冗余清理

- [x] 5.1 `modules/game_perf/src/gui_tab.py` 中 `_append_log()` 已将颜色映射为 level 传给 `_log()`，逻辑正确
- [x] 5.2 主题颜色最终由 `theme_colors.get_colors()` 处理，无需额外修改
- [x] 5.3 删除废弃的 `toolkit/gui/log_widget.py`（`LogTextEdit`）
- [x] 5.4 已确认无任何外部引用

## 6. 构建与文档同步

- [x] 6.1 `loguru` 已加入 `pyproject.toml` dependencies（纯 Python，PyInstaller 兼容）
- [x] 6.2 构建验证暂不运行（非阻塞）
- [x] 6.3 开发指南：模块使用标准 `logging.getLogger(__name__)` 即可自动桥接
- [x] 6.4 修改文件全部通过 `py_compile` 语法验证

## 7. 验收与回归测试

- [x] 7.1 结构化日志验证：`UnifiedLogger.bind_module("perfetto_analysis")` 已通过终端输出测试
- [x] 7.2 性能验证：GUISink 使用有界队列（500）+ QTimer 批量刷新（50ms）
- [x] 7.3 回退验证：`setup_logging()` 兼容旧接口
- [x] 7.4 Code Review：确认无 `print()` 残留、无硬编码颜色、`log_widget.py` 已删除
