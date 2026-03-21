# Windows 打包为 EXE

## 环境要求

- Windows 10/11，64 位
- Python 3.10+（建议 3.11），安装时勾选 **Add Python to PATH**
- 项目在：`lv-game-toolkit/source/`

## 方式一：双击脚本（推荐）

1. 进入目录 `lv-game-toolkit/source/`
2. 双击 **`build_windows.bat`**
3. 等待结束

## 方式二：命令行

```powershell
cd e:\MojitoTools\lv-game-toolkit\source
python -m pip install -r requirements.txt
python build.py
```

## 输出位置

| 内容 | 路径 |
|------|------|
| 可执行程序 | `source/dist/Toolkit/Toolkit.exe` |
| 依赖与资源 | 同目录下 `_internal/` 等（**整文件夹一起拷贝**） |
| 压缩包 | `source/dist/Toolkit-v1.0.0.zip` |

**分发时请打包整个 `dist/Toolkit` 文件夹**（或发 zip），不要只发单个 exe（当前为 **onedir** 模式，启动更稳）。

## 运行说明

- 首次运行会在 `Toolkit.exe` 同级的 `data/` 下生成配置（若 `build.py` 已写入默认 `config.json` 则直接使用）。
- 若自带 `adb` 目录，打包时会一并打进 `dist/Toolkit/adb/`（见 `build.spec`）。

## 仅重新生成 exe（不打包 zip）

```powershell
cd lv-game-toolkit\source
pyinstaller build.spec --noconfirm
```

## 常见问题

1. **`pyinstaller` 不是内部命令**  
   使用 `python -m PyInstaller build.spec --noconfirm` 代替。

2. **杀毒软件误报**  
   PyInstaller 生成的 exe 偶发误报，可加入白名单或使用代码签名（需证书）。

3. **单文件 exe（onefile）**  
   当前 `build.spec` 为目录模式。若需要单个 `.exe`，可再建一份 `onefile` 的 spec（启动会稍慢、解压到临时目录）。
