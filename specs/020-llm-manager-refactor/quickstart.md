# Quickstart: LLM Manager 模块

## 使用方式

### 1. 配置 Provider（手动编辑 JSON）

编辑 `data/config/llm_providers.json`：

```json
{
  "providers": [
    {
      "id": "deepseek",
      "name": "DeepSeek",
      "base_url": "https://api.deepseek.com/v1/",
      "litellm_prefix": "deepseek/",
      "api_key": "sk-your-key-here",
      "enabled": true,
      "thinking": false,
      "models": [
        {"name": "deepseek-chat", "context_window": 128000},
        {"name": "deepseek-reasoner", "context_window": 128000}
      ],
      "default_model": "deepseek-chat"
    }
  ],
  "active_provider": "deepseek"
}
```

保存后重启应用或点击设置面板「保存」触发重载。

### 2. 配置 Provider（GUI）

1. 打开右上角齿轮设置 → LLM 模型设置
2. 点击「管理 Provider...」
3. 点击「+ 添加 Provider」，填写 ID/Name/Base URL/Prefix/API Key/Models
4. 保存修改
5. 回到设置面板，Provider 下拉选择新 Provider
6. Model 下拉选择模型
7. 点击保存

### 3. 开启 Thinking

1. LLM 设置面板中选择 Claude Provider
2. 勾选「启用扩展思考」
3. 保存。后续 Claude 请求自动带上 thinking 参数

### 4. 查看上下文用量

底部状态栏右侧圆环：
- 填充比例 = 当前对话已用 / 模型上下文窗口
- Hover 圆环 → 显示精确数字和百分比
- 新对话 → 自动清零

### 5. 添加自定义 Provider（OpenAI 兼容端点）

```json
{
  "id": "ollama",
  "name": "Ollama Local",
  "base_url": "http://localhost:11434/v1/",
  "litellm_prefix": "openai/",
  "api_key": "ollama",
  "enabled": true,
  "thinking": false,
  "models": [
    {"name": "llama3.1:8b", "context_window": 128000}
  ],
  "default_model": "llama3.1:8b"
}
```

### 6. 开发调试

```bash
# 查看 Provider 配置
cat data/config/llm_providers.json | python -m json.tool

# 查询 Token 用量
python -c "
import sqlite3, json
db = sqlite3.connect('data/db/llm_token_usage.db')
for row in db.execute('SELECT * FROM llm_token_usage ORDER BY timestamp DESC LIMIT 10'):
    print(row)
"

# 运行模块测试
python -m pytest modules/llm_manager/tests/ -v
```
