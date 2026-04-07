# Quickstart: 全局设置与 LLM 能力抽象

**Feature**: 008-global-settings-llm | **Date**: 2026-04-03

## 目录

- [模块使用 LLM 能力](#模块使用-llm-能力)
- [配置 LLM](#配置-llm)
- [开发新 Provider](#开发新-provider)

## 模块使用 LLM 能力

模块通过 context 获取 LLM Manager：

```python
# 在模块 service.py 中
class MyService:
    def __init__(self, context: dict):
        self._llm_manager = context.get("llm_manager")

    async def analyze(self, data: str) -> str:
        if not self._llm_manager:
            raise RuntimeError("LLM 未初始化")

        provider = self._llm_manager.get_provider()
        if not provider:
            raise RuntimeError("LLM 未配置，请在设置中配置 API Key")

        messages = [{"role": "user", "content": f"分析以下数据:\n{data}"}]
        result = []
        async for chunk in provider.stream_chat(messages):
            if chunk.type == "text":
                result.append(chunk.content)
            elif chunk.type == "usage" and chunk.usage:
                self._llm_manager.record_tokens(
                    chunk.usage.get("total_tokens", 0)
                )
        return "".join(result)
```

## 配置 LLM

1. 点击标题栏齿轮图标 → 「LLM 模型设置」
2. 选择 Provider (GLM / Claude)
3. 输入对应 API Key
4. 选择模型
5. 保存

快捷切换：点击底部状态栏模型名 → 选择模型

## 开发新 Provider

1. 在 `toolkit/core/llm/` 下创建新文件（如 `openai_provider.py`）
2. 继承 `LLMProvider` 并实现所有抽象方法
3. 在 `LLMManager._create_provider()` 中添加新 Provider 分支
4. 在 `LLMConfig` 中添加对应的 `api_key` 字段
5. 更新 LLM 设置对话框添加新 Provider 按钮
