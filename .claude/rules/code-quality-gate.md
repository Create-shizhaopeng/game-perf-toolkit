# 代码质量门禁

防止低质量代码落盘和"假通过"验证。本规则优先级高于其他所有实现阶段规则。

## 硬约束

### 1. 代码移动 MUST cp+Edit，禁止 Write 重写

移动或重构现有代码时，MUST 先 `cp`（或 `git checkout`）源文件到目标位置，再用 `Edit` 做局部修改。

**禁止**：对已存在逻辑的文件使用 `Write` 工具"手写"新版本。

**原因**：手写代码频繁引入原代码不存在的低级错误（语法错误、函数签名错配、遗漏参数等）。

**适用场景**：
- 提升文件到新目录（如 `modules/agent_chat/src/tools/registry.py` → `toolkit/core/tool_registry.py`）
- 重构类/函数签名
- 拆分大文件

**例外**：全新功能文件（原位置不存在对应代码）可使用 Write。

### 2. MUST 执行实际启动验证

任何修改 `toolkit/` 或 `modules/` 中代码的变更完成后，MUST 执行实际启动路径验证：

```bash
python -m toolkit.app
```

或至少无头验证完整启动链：

```bash
.venv/Scripts/python -c "
# 验证 app.py run_gui() 的完整启动路径到 QApplication 创建前
from toolkit.app import _build_context, _load_plugins, _resolve_root
...
"
```

**禁止**：仅验证"import 不报错"就声称代码正常。
**禁止**：仅验证个别函数（如 `register()` 多态调用）就声称完整路径验证通过。

### 3. 禁止跳过测试

**禁止**使用以下手段让测试"变绿"：
- 用 `sed` 把 `def test_xxx` 重命名为 `def _skip_xxx`
- 删除测试文件使其不运行
- 修改断言使失败的测试通过但不再验证原始意图

**允许**的测试修改：
- 更新测试以匹配新的 API 签名（旧功能被刻意移除时）
- 补充新的测试用例覆盖修改后的代码路径
- 标记 `@pytest.mark.skip(reason="...")` 并写明原因

### 4. 新建模块 MUST 包含单元测试

在 `toolkit/` 或 `modules/` 中新建的 Python 模块，MUST 在对应 `tests/` 目录下创建测试文件。

**最小测试要求**：
- 每个公开类 ≥1 个初始化测试
- 每个公开方法 ≥1 个正常路径测试
- 关键错误路径 ≥1 个异常处理测试

**测试位置**：
- `toolkit/core/foo.py` → `tests/test_core_foo.py`
- `toolkit/agent/bar.py` → `tests/test_agent_bar.py`

## 验证检查清单

实现完成后 MUST 执行：

```
[ ] 语法检查: python -c "import ast; ast.parse(open('<file>').read())"  (对所有新增/修改的 .py)
[ ] 导入检查: .venv/Scripts/python -c "import <module>"  (对所有新增/修改的模块)
[ ] 启动验证: .venv/Scripts/python -c "执行完整启动路径"
[ ] 测试运行: .venv/Scripts/python -m pytest tests/<relevant>/ -v
[ ] 无 _skip_ 重命名: git diff 中无 `_skip_` 命名的测试方法
[ ] 配置文件型 Service: 是否继承 QObject + QFileSystemWatcher + config_changed 信号 (参照 config-sync-rules.md)
```

## 关联规则

- 核心逻辑修改管控: [core-logic-change-gate.md](core-logic-change-gate.md)
- 实现 Review 门禁: [review-gate.md](review-gate.md)
- 配置实时同步规范: [config-sync-rules.md](config-sync-rules.md)
