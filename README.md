# Toolkit（lv-game-toolkit）

桌面端 **Toolkit**：设备型号伪装（ModifyModelNameTool 选项卡）与游戏策略配置推送（push policy 选项卡）。

- 详细说明见 [quickstart.md](quickstart.md)
- Push 策略需求见 [spec-push-policy.md](spec-push-policy.md)

**远程仓库**：<https://gitee.com/lv-game-toolkit/lv-game-toolkit>  
克隆：`git clone https://gitee.com/lv-game-toolkit/lv-game-toolkit.git`

### Git 与提交说明

- 本目录为**独立仓库**（与上级 `mojito` 仓库分离）；首次推送前需在 Gitee 配置账号/令牌或 SSH。
- **提交信息模板**（须纳入版本库，协作者 `git pull` 后可见）：[.github/COMMIT_MSG_TEMPLATE.md](.github/COMMIT_MSG_TEMPLATE.md)。
- **忽略规则**：根目录 [.gitignore](.gitignore)（含 `source/dist/`、`source/build/`、`source/.venv/`、`source/data/backups/`、`source/data/config.json`、本地提交草稿 `commit_msg*.txt` 等）。**请勿**将 `.github/COMMIT_MSG_TEMPLATE.md` 或 `.gitignore` 本身忽略。

#### 协作者首次拉取后（建议执行）

```bash
cd <本仓库根目录>
git pull
git config commit.template .github/COMMIT_MSG_TEMPLATE.md
```

之后在本仓库内 `git commit`（无 `-m`）时会自动打开模板；或使用 `git commit -F <按模板填好的文件>`。

#### 确保提交「有用」的检查

- `git status` 无编译产物、虚拟环境、备份目录、个人 `config.json`。
- 提交说明符合模板字段（见 `COMMIT_MSG_TEMPLATE.md` 第 7–14 行）。

**推送示例**（HTTPS，需输入 Gitee 用户名与私人令牌）：

```bash
cd cf/ModifyModelNameTool
git remote -v
git push -u origin master
```

**SSH 示例**（将 `origin` 改为 SSH 地址后）：

```bash
git remote set-url origin git@gitee.com:lv-game-toolkit/lv-game-toolkit.git
git push -u origin master
```
