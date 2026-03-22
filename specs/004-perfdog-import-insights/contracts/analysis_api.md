# Contract: `core.perfdog` 分析 API（Python）

**Consumers**: `ui/perfdog_worker.py`、未来 CLI/测试。

## 入口函数（建议签名）

```python
# core/perfdog/__init__.py 或 facade module

def load_and_analyze(path: str, *, options: AnalyzeOptions | None = None) -> AnalysisReport:
    """
    同步解析 + 洞察。由 QThread 调用；不在主线程执行。
    raises: PerfDogParseError, PerfDogUnsupportedError
    """

def build_markdown(report: AnalysisReport) -> str:
    """FR-010：UTF-8 文本，无 BOM 或统一 BOM 策略见实现。"""

def compare_reports(a: AnalysisReport, b: AnalysisReport) -> SessionComparePair:
    """二期；应用不一致时 warnings 非空。"""
```

## AnalyzeOptions（可选配置）

| 字段 | 默认 | 说明 |
|------|------|------|
| anomaly_window_ms | 5000 | 异常窗口半宽（总窗口约 2×+1s） |
| max_frame_rows | 800_000 | 超过则降级采样或拒解析 |
| locale | zh_CN | 报告语言 |

## 错误类型

| 异常 | 含义 |
|------|------|
| PerfDogParseError | 文件损坏、非 xlsx、无法定位 Data_v4 |
| PerfDogUnsupportedError | 加密簿、宏执行拒绝等 |

## UI 契约（信号）

`PerfDogWorker`（QObject in QThread）建议暴露：

- `progress(str)` — 阶段文案  
- `finished(report: AnalysisReport)`  
- `failed(message: str)`  

**不得**在信号中传递不可序列化超大对象：若未来优化，可改为传递报告 ID + 主线程取缓存（MVP 可直接传 `AnalysisReport` 若体积可控）。

### 实现对照（lv-game-toolkit）

当前模块 **`modules/perfdog_insights/src/analysis_worker.py`** 中类 **`PerfDogAnalysisWorker`** 使用 PyQt 信号名：

| 契约（本文） | 实现 |
|--------------|------|
| `finished(report)` | **`finished_ok(object)`** |
| `failed(message)` | **`finished_err(str)`** |
| `progress(str)` | **`progress(str)`**（一致） |

语义与本文一致；详见 **[implementation.md](../implementation.md) §4**。

## 版本

- **Contract v1**：与 MVP 同步；破坏性变更递增 minor 并更新本文件。
