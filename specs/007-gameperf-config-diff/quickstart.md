# Quickstart: 007-gameperf-config-diff（开发者）

## 前置

- 仓库根：`lv-game-toolkit`
- Python 3.12 + `.venv`

## 运行模块测试（实现完成后）

```powershell
cd e:\MojitoTools\lv-game-toolkit
.\.venv\Scripts\python.exe -m pytest modules\workspace_tools\tests\test_gameperf_diff_service.py -v --tb=short
```

## Fixtures

成对样例（文件名须含 `gameperfconfig` 以满足校验）：

- `modules/workspace_tools/fixtures/gameperfconfig_diff_base.xml`
- `modules/workspace_tools/fixtures/gameperfconfig_diff_variant_a.xml`

## 手测（GUI）

1. `python -m toolkit.app`
2. 侧边栏打开 **性能配置对比** → 子页 **配置对比**
3. 选择基准 XML → 添加本地对比或 **从当前设备添加** → **开始对比** → 树中选行 → **采纳基准侧/对比侧** → **另存为…**（确认对话框与覆盖提示）

## 相关文档

- [spec.md](./spec.md)
- [plan.md](./plan.md)
- [contracts/gameperf_config_diff.md](./contracts/gameperf_config_diff.md)
- 模块内索引：`modules/workspace_tools/specs/007-gameperf-config-diff/spec.md`
