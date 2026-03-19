# Commit Message 模板使用说明

提交时请按 [COMMIT_MSG_TEMPLATE.md](COMMIT_MSG_TEMPLATE.md) 中的字段结构填写，保留字段行、替换 `{}` 内内容。

## 使用方式

```bash
cd Toolkit
# 将模板内容写入 UTF-8 文件后提交
git commit -F path/to/commit_msg.txt
```

或配置为本仓库默认模板（**每名协作者拉取代码后在本仓库根目录执行一次**）：

```bash
# 仓库根目录 = 本 Toolkit 目录（含 .github 与 source 的那一层）
git config commit.template .github/COMMIT_MSG_TEMPLATE.md
```

之后在本仓库内 `git commit`（无 `-m`）时会自动打开模板；或使用 `git commit -F <按模板填好的文件>`。

## 协作者必读（与 .gitignore 配合）

1. **`git pull`** 后应能看到 `.github/COMMIT_MSG_TEMPLATE.md` 与根目录 `.gitignore`；二者**不要**加入 `.gitignore`，需随仓库同步。根目录 `UI示意图/`、`UI.jpg`、`ui.png`、`ui2.png`、`ui3.png`、`model名修改重置工具.md` 为**本地资源**（已在 `.gitignore`），远程不包含，需要时请自备或从设计/产品侧获取。
2. 提交前确认 **`git status`** 中仅包含**有意提交的源码/文档**；`source/dist/`、`source/build/`、`source/.venv/`、`source/data/backups/`、`source/data/config.json` 等已被忽略，**勿强行 `git add -f`**。
3. 使用模板提交示例：将 `COMMIT_MSG_TEMPLATE.md` 复制到临时 UTF-8 文本，按字段填写后执行 `git commit -F my_commit_msg.txt`。
4. 团队约定：**每次提交信息须符合本模板**，便于评审与追溯；无功能变更时不要提交编译产物或个人配置。
