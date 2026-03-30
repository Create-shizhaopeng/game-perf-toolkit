# 002-device-info-json — 实现计划

## 目录

- [技术方案](#技术方案)
- [涉及文件](#涉及文件)
- [风险与回滚](#风险与回滚)

## 技术方案

1. **路径解析**：在 `models.py` 提供 `resolve_device_info_json_path()`，基于 `sys.frozen` 分支；常量 `DEVICE_INFO_FILENAME` 便于测试断言。
2. **迁移**：`ProfileManager.__init__` 在 `load` 前调用 `_maybe_migrate_legacy()`，仅在目标文件不存在时尝试从旧路径 `copy2`。
3. **GUI**：`gui_tab.py` 增加 `QFileDialog` + `_on_import_config`，捕获 `OSError`、`json.JSONDecodeError` 及未预期异常；导入成功后 `refresh_completers()`。
4. **构建**：不在 `build.py` 为设备伪装单独 `add-data`；与 001 一致，`modules/*/data` 仍被通用收集规则排除，运行依赖用户目录或首次拷贝仓库随带文件到安装目录（或由导入填充）。
5. **数据**：仓库内删除 `device_profiles.json`，新增 `device_info.json`（内容迁移自原默认三条）。

## 涉及文件

- `modules/device_disguise/src/models.py`
- `modules/device_disguise/src/gui_tab.py`
- `modules/device_disguise/data/device_info.json`（新增）
- `modules/device_disguise/data/device_profiles.json`（删除）
- `modules/device_disguise/tests/test_models.py`
- `modules/device_disguise/specs/001-migration/spec.md`（Clarifications 增补指向 002）
- `scripts/build.py` / `scripts/doc/build.md`（移除上一轮设备伪装打包收集逻辑，若仍存在）

## 风险与回滚

- 老用户本地仅有 `device_profiles.json`：由迁移逻辑覆盖。
- 若迁移失败：打日志，表现为空库，可手动将文件改名为 `device_info.json` 或使用导入配置。
