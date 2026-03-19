# Commit Message 模板（Gitee / Toolkit）

提交时请按以下结构填写（可删除本段说明，保留下方字段行）：

---

[Toolkit.util.init][(1/1)]{model名修改&配置文件导入工具开发}
适用范围:{ALL}
准入id:{NA}
分析:{model名修改&配置文件导入工具开发}
方案:{model名修改&配置文件导入工具开发}
风险及影响[快/稳/省/功能/安全隐私]:{无}
测试建议:{测试model名修改是否正常，配置文件导入是否正常}
跨组依赖(topic name):{无}

---

## 使用方式

```bash
cd cf/ModifyModelNameTool
# Windows PowerShell：将模板第 7–14 行写入 UTF-8 文件后提交
git commit -F path/to/commit_msg.txt
```

或配置为本仓库默认模板（仅影响本目录下的 Git 仓库）：

```bash
git config commit.template .github/COMMIT_MSG_TEMPLATE.md
```
