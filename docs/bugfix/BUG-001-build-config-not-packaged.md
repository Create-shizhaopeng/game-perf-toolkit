<!--
  id: BUG-001
  title: 构建打包时 device_info.json 等模块配置文件未被复制到 dist/data/
  type: bugfix
  status: fixed
  created: 2026-05-18
  updated: 2026-05-19
  tags: [build, pyinstaller, device_disguise, packaging]
-->

# BUG-001: 构建打包时模块配置文件未被复制到 dist/data/

## 目录

- [现象](#现象)
- [根因分析](#根因分析)
- [修复方案](#修复方案)
- [变更文件](#变更文件)
- [副作用修复](#副作用修复)
- [验证](#验证)

## 现象

`python scripts/build.py` 构建后，`dist/Toolkit/data/` 目录不存在，`device_info.json` 配置文件未随分发包一起分发。用户首次启动 exe 后无法正确加载默认设备档案。

## 根因分析

`scripts/build.py` 的 `_collect_modules()` 函数（第 85 行）将 `"data"` 加入 `skip_dirs` 集合，导致 `os.walk(modules_dir)` 遍历时跳过所有 `modules/*/data/` 目录：

```python
skip_dirs = {
    "__pycache__", "data", ".pytest_cache", ...
}
```

原本 `modules/device_disguise/data/device_info.json` 是该模块的分发配置文件，但 `data/` 目录设计上存放的是测试资源和运行时数据（如 `push_records`、`output`），不应打包。配置文件需要一条独立路径。

## 修复方案

### 1. 路径分离

- `modules/<name>/data/` — 运行时数据 / 测试资源 → **不打包**（维持原设计）
- `modules/<name>/config/` — 分发配置文件 → **构建时复制到 `dist/<name>/data/`**

将 `device_info.json` 从 `modules/device_disguise/data/` 迁移到 `modules/device_disguise/config/`。

### 2. build() 构建后自动创建 data/

PyInstaller 打包完成后，`build()` 遍历 `modules/*/config/` 将配置文件复制到 `dist/<name>/data/`。这样 `package()` 通过 `copytree` 自然携带 `data/` 目录及配置文件。

### 3. 命令行 → .spec 文件

由于 Windows 命令行有 32768 字符限制，大量 `--add-data` 和 `--hidden-import` 参数会超限。改为 `_write_spec()` 生成 PyInstaller `.spec` 文件，通过文件传递参数。

### 4. 时间戳构建目录名

构建输出目录使用带时间戳的名称（如 `Toolkit_143052`），避免旧的 `dist/Toolkit` 目录被外部进程（文件资源管理器、杀毒软件等）锁定导致 `PermissionError`。

## 变更文件

| 文件 | 变更 |
|------|------|
| `modules/device_disguise/config/device_info.json` | 从 `data/` 迁移到新建的 `config/` 目录 |
| `modules/device_disguise/src/models.py` | `resolve_device_info_json_path()` 开发环境路径指向 `config/` |
| `modules/device_disguise/tests/test_models.py` | `test_dev_points_to_module_data` 断言 `parent.name` 改为 `"config"` |
| `scripts/build.py` | 新增 `_write_spec()`；`build()` 返回目录名 + 构建后创建 `data/`；`package()` 接受动态目录名 |
| `.gitignore` | 移除旧的 `modules/device_disguise/data/` 例外规则 |
| `modules/device_disguise/specs/001-migration/spec.md` | 路径引用 `data/` → `config/` |
| `modules/device_disguise/specs/001-migration/plan.md` | 路径引用 `data/` → `config/` |
| `modules/device_disguise/specs/001-migration/tasks.md` | 路径引用 `data/` → `config/` |
| `modules/device_disguise/specs/002-device-info-json/spec.md` | 路径引用 `data/` → `config/` |
| `modules/device_disguise/specs/002-device-info-json/plan.md` | 构建方案更新 |
| `modules/device_disguise/specs/002-device-info-json/analysis.md` | 核对项更新 |

## 副作用修复

- **PyInstaller `--clean` 移除**：会导致 `COLLECT` 阶段删除输出目录，若目录被锁定则失败
- **`_copy_as_cli` exe 查找方式**：从硬编码文件名改为 glob 匹配（构建目录含时间戳后缀）

## 验证

- `modules/device_disguise/tests/test_models.py` 21 个测试全部通过
- 构建后 `dist/<name>/data/device_info.json` 存在且内容正确
- `package()` 生成的 zip 分发包中 `data/` 目录随带配置文件
