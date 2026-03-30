# 002-device-info-json — 任务清单

## 目录

- [任务列表](#任务列表)
- [完成定义](#完成定义)

## 任务列表

- [x] T001 回退 `build.py` / `build.md` 中设备伪装专用 `--add-data` 逻辑
- [x] T002 `models.py`：`resolve_device_info_json_path`、`_maybe_migrate_legacy`、`ProfileManager` 默认路径切换为 `device_info.json`
- [x] T003 仓库数据：`device_info.json` 提交默认三条；删除 `device_profiles.json`
- [x] T004 `gui_tab.py`：「导入配置」按钮与 `_on_import_config`
- [x] T005 `test_models.py`：路径、迁移、既有用例调整
- [x] T006 规格：`002-device-info-json/spec.md`、`plan.md`、`tasks.md`、`analysis.md`
- [x] T007 `001-migration/spec.md` Clarifications 指向 002

## 完成定义

- `pytest modules/device_disguise/tests/ -v` 全部通过
- 与 spec FR/AC 一致；无对 `toolkit/` 的修改
