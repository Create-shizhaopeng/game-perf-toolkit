"""PerfDog 分析默认常量（与 plan / research 对齐，可在此统一调参）。"""

from __future__ import annotations

# 异常窗口半宽（ms），总窗口约 2× + 中间 1s 采样
ANOMALY_WINDOW_MS: int = 5000

# 解析 / 帧表保护
MAX_DATA_V4_ROWS: int = 800_000

# UI/日志：超过该秒数仍无阶段进展时可打「慢解析」日志（供后续接入）
ANALYSIS_SLOW_SEC: float = 3.0

# Stat 行 FPS 与 Data_v4 重算均值相对差异超过此比例时写入 stat_row_disclaimer
STAT_FPS_DIFF_RATIO: float = 0.01

# 低帧：FPS < 目标 × 该系数视为「明显偏低」
LOW_FPS_RATIO: float = 0.85

# 尖刺：单点 FPS < 目标 × 该系数
SPIKE_FPS_RATIO: float = 0.50

# 帧率不稳：变异系数超过该值
FPS_CV_WARN: float = 0.12

# 温度环比窗口内上升（℃）视为异常提示
THERMAL_DELTA_WARN_C: float = 3.0

# 最低帧分析：最低点附近 ±N 个采样点与全段对比
LOW_FPS_CONTEXT_SAMPLES: int = 5

# 窗口内指标相对全段均值的倍数/差值阈值（启发式，非诊断结论）
LOW_FPS_GPU_USAGE_VS_GLOBAL: float = 1.12
LOW_FPS_APP_CPU_VS_GLOBAL: float = 1.18
LOW_FPS_TOTAL_CPU_VS_GLOBAL: float = 1.15
# 窗口内 GPU 频率最小值 < 全段中位数 × 该比例 → 提示可能降频
LOW_FPS_GPU_CLOCK_VS_MEDIAN: float = 0.72
# 窗口内温度峰值高于全段均值（℃）
LOW_FPS_TEMP_ABOVE_GLOBAL_MEAN: float = 2.5

# CPU 各核：用「窗口中位数」相对全段中位数判断是否持续偏低（避免单点 min 误判）
LOW_FPS_CPU_CLOCK_WINDOW_MEDIAN_VS_GLOBAL: float = 0.88
# 若窗口中位数正常，但窗口内低于「全段中位×0.80」的采样占比 ≥ 该值，再提示「瞬时频点下探」
LOW_FPS_CPU_CLOCK_LOW_SAMPLE_FRAC: float = 0.42

# GPU 频率：同样用窗口中位数对比全段中位数，避免单点 min 误判
LOW_FPS_GPU_CLOCK_WINDOW_MEDIAN_VS_GLOBAL: float = 0.88

# 最低 FPS 相对目标占比 ≥ 该值时，文案中强调「轻度落差」、严重度可降级
LOW_FPS_MILD_RATIO_VS_TARGET: float = 0.88

# spec 附录 B §6 / FR-008：导出与 GUI 共用的「方法与局限性」正文（Markdown 段落，空行分段）
REPORT_METHODS_AND_LIMITATIONS_ZH: str = (
    "本报告由规则与阈值驱动的启发式分析生成，用于辅助在数据中定位异常区段与指标对照，"
    "不构成系统级或唯一根因结论，也不能替代专业排障裁定。\n\n"
    "结论不能替代 Systrace、Perfetto、内核跟踪等工具的深入分析；若需认定性能根因，请结合实机跟踪、"
    "业务场景与复测后再下判断。\n\n"
    "PerfDog 导出列因版本而异；「尚未登记别名的列」仅表示内部别名表未映射该列名，"
    "不代表 Excel 中未读入数据。洞察中若缺少某类字段会明确提示数据缺口或不可用。"
)
