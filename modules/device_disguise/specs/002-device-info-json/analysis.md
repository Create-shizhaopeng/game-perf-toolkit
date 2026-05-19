# 002-device-info-json — 实现后一致性核对

## 目录

- [核对项](#核对项)
- [结论](#结论)

## 核对项

| 条目 | spec 要求 | 实现 | 状态 |
|------|-----------|------|------|
| FR-001 路径 | 开发 `modules/.../config/device_info.json`；frozen `exe/data/device_info.json` | `resolve_device_info_json_path()` | OK |
| FR-002 同步 | CRUD/import 写回 JSON | 沿用既有 `save()` | OK |
| FR-003 GUI 导入 | 按钮 + 合并 + 提示 + refresh | `_on_import_config` | OK |
| FR-004 迁移 | 旧 `device_profiles.json` | `_maybe_migrate_legacy` 两处候选路径 | OK |
| FR-005 CLI | 同数据源 | `ProfileManager()` 默认路径一致 | OK |
| AC | 测试覆盖路径/迁移/CRUD | `test_models.py` | OK |
| 回退打包 | config/ 下配置文件通过 `_collect_module_configs` 打包 → `data/` | `build.py` | OK |

## 结论

**FAIL 项：无。** 可合并/发布。
