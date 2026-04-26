# 版本号规范 (SemVer)

格式: `vMAJOR.MINOR.PATCH` — 通过 `git tag` 管理，构建脚本自动读取。

## 版本递增规则

| 变更类型 | 版本位 | 示例 |
|---------|--------|------|
| Bug 修复、小调整 | PATCH +1 | v0.1.1 → v0.1.2 |
| 需求更新、功能迭代 | MINOR +1, PATCH 归零 | v0.1.2 → v0.2.0 |
| 新增模块、框架重构 | MAJOR +1, 其余归零 | v0.2.0 → v1.0.0 |

## 硬规则

- 发版前 MUST 执行 `git tag vX.Y.Z` 并 `git push origin vX.Y.Z`
- 构建脚本通过 `git describe --tags` 自动提取版本号写入 `VERSION` 文件
- `toolkit/__version__` 优先从 `VERSION` 文件读取，开发环境从 git tag 读取
- MUST NOT 在代码中硬编码版本号
- 版本号 MUST 在 `specify-rules.mdc` 的知识源指针中可查阅完整说明：`scripts/doc/build.md`

## 发版流程

```bash
git tag v0.2.0
git push origin v0.2.0
python scripts/build.py
```
