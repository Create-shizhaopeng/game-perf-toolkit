# 编码规范

## 目录

- [Python 规范](#python-规范)
- [类型注解](#类型注解)
- [文档字符串](#文档字符串)
- [编码与国际化](#编码与国际化)

## Python 规范

- Python 3.12+ 为最低版本要求
- 使用 Ruff 作为 linter 和 formatter
- 遵循 `.editorconfig` 的格式设定

## 类型注解

- 所有公共方法 MUST 有完整的类型注解
- 使用 `from __future__ import annotations` 时需注意 `get_type_hints` 兼容性（参考 P25）
- Pydantic 模型用于公共 API 的入参和返回值

## 文档字符串

- 使用中文编写注释和文档字符串
- 公共方法 MUST 有文档字符串，说明功能、参数、返回值
- 私有方法仅在逻辑复杂时添加文档字符串

## 编码与国际化

- 所有文件和输出 MUST 使用 UTF-8 编码
- 中文内容不得出现乱码（Windows 环境特别注意 console 编码）
- 日志和用户提示统一使用中文
