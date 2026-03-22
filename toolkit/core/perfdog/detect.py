"""从 DataFrame 生成 Finding 列表。"""

from __future__ import annotations

import uuid
from typing import Any

import pandas as pd

from toolkit.core.perfdog.config_defaults import (
    FPS_CV_WARN,
    LOW_FPS_CONTEXT_SAMPLES,
    LOW_FPS_APP_CPU_VS_GLOBAL,
    LOW_FPS_CPU_CLOCK_LOW_SAMPLE_FRAC,
    LOW_FPS_CPU_CLOCK_WINDOW_MEDIAN_VS_GLOBAL,
    LOW_FPS_GPU_CLOCK_VS_MEDIAN,
    LOW_FPS_GPU_CLOCK_WINDOW_MEDIAN_VS_GLOBAL,
    LOW_FPS_GPU_USAGE_VS_GLOBAL,
    LOW_FPS_MILD_RATIO_VS_TARGET,
    LOW_FPS_TEMP_ABOVE_GLOBAL_MEAN,
    LOW_FPS_TOTAL_CPU_VS_GLOBAL,
    LOW_FPS_RATIO,
    SPIKE_FPS_RATIO,
    THERMAL_DELTA_WARN_C,
)
from toolkit.core.perfdog.report_types import (
    Finding,
    FindingCategory,
    FindingSeverity,
    FrameStats,
)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def finding_from_frame_stats(fs: FrameStats, target_fps: int) -> Finding | None:
    """@FrameInfo 聚合 → 一条可验收的帧时长结论（SC-009）。"""
    if not fs.count:
        return None
    budget = (1000.0 / max(target_fps, 1)) * 2.0
    ratio = fs.over_budget_count / fs.count if fs.count else 0.0
    at_txt = ""
    if fs.max_frame_at_ms is not None:
        at_txt = f"最大帧耗时出现在相对时间约 {fs.max_frame_at_ms/1000:.2f}s。"
    detail = (
        f"基于 @FrameInfo 共 {fs.count} 帧：均值 {fs.mean_ms:.2f} ms，"
        f"p99 {fs.p99_ms:.2f} ms，最大 {fs.max_ms:.2f} ms；"
        f"超过 2×目标帧时长（>{budget:.2f} ms）的帧共 {fs.over_budget_count} 帧"
        f"（约 {ratio*100:.1f}%）。{at_txt}"
        "秒级 Data_v4 与帧级表分列展示，交叉引用可按 1s bucket 对齐（见 research.md）。"
    )
    sev = FindingSeverity.warn if ratio > 0.05 or fs.max_ms > budget * 1.5 else FindingSeverity.info
    return Finding(
        id=_new_id("frameinfo"),
        category=FindingCategory.stability,
        severity=sev,
        title="帧时长统计（@FrameInfo）",
        detail=detail,
        evidence={
            "frame_stats": True,
            "target_fps": target_fps,
            "p99_ms": fs.p99_ms,
            "max_ms": fs.max_ms,
            "over_budget_count": fs.over_budget_count,
        },
    )


def _minimum_fps_root_cause_findings(dfv: pd.DataFrame, target_fps: int) -> list[Finding]:
    """定位全段最低 FPS 采样点，并在邻域内与全段对比 GPU/CPU/温度/频点，输出启发式成因。"""
    findings: list[Finding] = []
    fps = pd.to_numeric(dfv["fps"], errors="coerce")
    tcol = pd.to_numeric(dfv["time_ms"], errors="coerce")
    if fps.dropna().empty:
        return findings

    imin = int(fps.idxmin())
    min_fps = float(fps.iloc[imin])
    t_at = float(tcol.iloc[imin]) if not pd.isna(tcol.iloc[imin]) else 0.0
    n = len(dfv)
    W = LOW_FPS_CONTEXT_SAMPLES
    lo = max(0, imin - W)
    hi = min(n - 1, imin + W)
    w_bt_max: float | None = None

    def _global_mean(col: str) -> float | None:
        if col not in dfv.columns:
            return None
        s = pd.to_numeric(dfv[col], errors="coerce").dropna()
        if s.empty:
            return None
        return float(s.mean())

    def _window_mean(col: str) -> float | None:
        if col not in dfv.columns:
            return None
        s = pd.to_numeric(dfv[col].iloc[lo : hi + 1], errors="coerce").dropna()
        if s.empty:
            return None
        return float(s.mean())

    def _window_min(col: str) -> float | None:
        if col not in dfv.columns:
            return None
        s = pd.to_numeric(dfv[col].iloc[lo : hi + 1], errors="coerce").dropna()
        if s.empty:
            return None
        return float(s.min())

    def _window_median(col: str) -> float | None:
        if col not in dfv.columns:
            return None
        s = pd.to_numeric(dfv[col].iloc[lo : hi + 1], errors="coerce").dropna()
        if s.empty:
            return None
        return float(s.median())

    def _global_median(col: str) -> float | None:
        if col not in dfv.columns:
            return None
        s = pd.to_numeric(dfv[col], errors="coerce").dropna()
        if s.empty:
            return None
        return float(s.median())

    hints: list[str] = []
    metrics_compare: dict[str, Any] = {}

    g_gpu = _global_mean("gpu_usage_pct")
    w_gpu = _window_mean("gpu_usage_pct")
    if g_gpu is not None and w_gpu is not None and g_gpu > 1e-6:
        metrics_compare["gpu_usage_pct"] = (round(g_gpu, 2), round(w_gpu, 2))
        if w_gpu > g_gpu * LOW_FPS_GPU_USAGE_VS_GLOBAL:
            hints.append(
                "最低帧附近 GPU 占用明显高于全段均值，存在 **图形负载偏高 / GPU 瓶颈** 的可能"
                "（如分辨率、特效、带宽或驱动合成）。",
            )

    g_app = _global_mean("app_cpu_pct")
    w_app = _window_mean("app_cpu_pct")
    if g_app is not None and w_app is not None and g_app > 1e-6:
        metrics_compare["app_cpu_pct"] = (round(g_app, 2), round(w_app, 2))
        if w_app > g_app * LOW_FPS_APP_CPU_VS_GLOBAL:
            hints.append(
                "最低帧附近 **应用 CPU** 明显高于全段均值，可能与 **游戏逻辑、主线程或脚本** 压力有关。",
            )

    g_tot = _global_mean("total_cpu_pct")
    w_tot = _window_mean("total_cpu_pct")
    if g_tot is not None and w_tot is not None and g_tot > 1e-6:
        metrics_compare["total_cpu_pct"] = (round(g_tot, 2), round(w_tot, 2))
        if w_tot > g_tot * LOW_FPS_TOTAL_CPU_VS_GLOBAL:
            app_also_up = (
                w_app is not None
                and g_app is not None
                and g_app > 1e-6
                and w_app > g_app * 1.08
            )
            if not app_also_up and w_tot > 55:
                hints.append(
                    "最低帧附近 **整机 CPU** 明显抬升，而 **应用 CPU** 未同幅升高，"
                    "可能存在 **后台进程 / 系统服务** 与其它应用抢占 CPU。",
                )

    g_gcm = _global_median("gpu_clock_mhz")
    w_gmin = _window_min("gpu_clock_mhz")
    w_gmed = _window_median("gpu_clock_mhz")
    if g_gcm is not None and g_gcm > 100:
        if w_gmin is not None:
            metrics_compare["gpu_clock_mhz_global_median_vs_window_min"] = (
                round(g_gcm, 0),
                round(w_gmin, 0),
            )
        if w_gmed is not None:
            metrics_compare["gpu_clock_mhz_global_median_vs_window_median"] = (
                round(g_gcm, 0),
                round(w_gmed, 0),
            )
        if (
            w_gmed is not None
            and w_gmed < g_gcm * LOW_FPS_GPU_CLOCK_WINDOW_MEDIAN_VS_GLOBAL
        ):
            hints.append(
                "最低帧邻域 **GPU 频率（窗口中位数）** 明显低于全段中位数，可能与 **温控/省电限频** 或 **负载突变** 有关。",
            )
        elif (
            w_gmin is not None
            and w_gmed is not None
            and w_gmin < g_gcm * LOW_FPS_GPU_CLOCK_VS_MEDIAN
            and w_gmed >= g_gcm * 0.92
        ):
            hints.append(
                "GPU 频率在邻域内**出现过瞬时低点**，但**窗口中位频率与全段接近**，"
                "不宜单独解读为持续 GPU 降频；可结合 @FrameInfo 看单帧耗时尖峰。",
            )

    g_bt_mean = _global_mean("battery_temp")
    w_bt_max = None
    if "battery_temp" in dfv.columns:
        seg = pd.to_numeric(dfv["battery_temp"].iloc[lo : hi + 1], errors="coerce").dropna()
        if not seg.empty:
            w_bt_max = float(seg.max())
        if g_bt_mean is not None and w_bt_max is not None:
            metrics_compare["battery_temp_mean_vs_window_max"] = (
                round(g_bt_mean, 2),
                round(w_bt_max, 2),
            )
            if w_bt_max > g_bt_mean + LOW_FPS_TEMP_ABOVE_GLOBAL_MEAN:
                hints.append(
                    "最低帧附近 **电池温度** 高于全段均值，**热状态** 可能促使 SoC/GPU 降频，需结合环境与散热条件判断。",
                )

    # 各核频率：以「窗口中位数」为主判定持续偏低；min + 中位数正常 → 统一提示「瞬时下探」勿误判持续限频
    throttle_cores: list[int] = []
    transient_cpu_pattern = False
    for i in range(8):
        col = f"cpu_clock_{i}_mhz"
        if col not in dfv.columns:
            continue
        gmed = _global_median(col)
        if gmed is None or gmed <= 100:
            continue
        wmed = _window_median(col)
        wmn = _window_min(col)
        seg = pd.to_numeric(dfv[col].iloc[lo : hi + 1], errors="coerce")
        if wmed is not None and wmed < gmed * LOW_FPS_CPU_CLOCK_WINDOW_MEDIAN_VS_GLOBAL:
            throttle_cores.append(i)
        elif (
            wmn is not None
            and wmed is not None
            and wmn < gmed * LOW_FPS_GPU_CLOCK_VS_MEDIAN
            and wmed >= gmed * 0.92
        ):
            transient_cpu_pattern = True
        elif wmn is not None and wmn < gmed * LOW_FPS_GPU_CLOCK_VS_MEDIAN:
            below = int((seg < gmed * 0.80).sum())
            total = int(seg.notna().sum())
            if total > 0 and (below / total) >= LOW_FPS_CPU_CLOCK_LOW_SAMPLE_FRAC:
                transient_cpu_pattern = True

    if throttle_cores:
        hints.append(
            f"最低帧邻域内 **CPU 核 {throttle_cores}** 的**窗口中位频率**低于全段中位数，"
            "更支持 **持续性的 CPU 侧频率偏低或调度变化**（需结合 @ThreadCpuUsageData 看线程与绑核）。",
        )
    elif transient_cpu_pattern:
        hints.append(
            "多核 CPU 在邻域内**出现过瞬时频率低点**，但 **窗口中位频率与全段中位数基本一致**，"
            "更符合 **少数采样下探或调度抖动**，**不应解读为持续 CPU 限频**。"
            "若该点 FPS 仍相对偏低，请结合下方「综合研判」与 **GPU 单帧 / @FrameInfo** 继续排查。"
        )

    # 卡顿相关列（若存在）：最低帧邻域 vs 全段
    for col, label in (
        ("stutter_pct", "卡顿时长占比"),
        ("jank", "Jank"),
        ("jank_big", "BigJank"),
    ):
        if col not in dfv.columns:
            continue
        gm = _global_mean(col)
        wm = _window_mean(col)
        if gm is None or wm is None:
            continue
        metrics_compare[f"{col}_global_vs_window"] = (round(gm, 3), round(wm, 3))
        if wm > gm * 1.25 and gm > 0.01:
            hints.append(
                f"最低帧邻域 **{label}** 高于全段均值，**卡顿类指标与最低点在时间上对齐**，"
                "可结合同时间点场景标签与 @FrameInfo 查长尾帧。",
            )

    if not hints:
        hints.append(
            "当前导出在最低帧邻域内 **未触发** GPU/CPU/温度/频点的显著对比规则；"
            "不代表无瓶颈，建议补充 **@FrameInfo、Perfetto** 或提高采样密度后重导。",
        )

    ratio_tgt = (min_fps / target_fps) if target_fps else 1.0
    if min_fps < target_fps * 0.45:
        sev = FindingSeverity.critical
    elif ratio_tgt >= LOW_FPS_MILD_RATIO_VS_TARGET:
        sev = FindingSeverity.info
    else:
        sev = FindingSeverity.warn

    detail_parts = [
        f"全段 **最低 FPS** 为 **{min_fps:.1f}**（推断目标约 **{target_fps}**，相对约 **{100*ratio_tgt:.1f}%**），"
        f"出现在相对时间约 **{t_at/1000:.2f}s**（邻域 ±{W} 个采样点与全段对比）。",
        "",
        "**可能成因（启发式，非唯一结论）**：",
    ]
    for h in hints:
        detail_parts.append(f"- {h}")

    # 综合研判：多指标互证，减少单一指标误读
    synthesis: list[str] = []
    if ratio_tgt >= LOW_FPS_MILD_RATIO_VS_TARGET:
        synthesis.append(
            f"相对目标帧率，最低点仍在 **{100*ratio_tgt:.0f}%+** 水平，属 **轻度落差**；"
            "若对局体感流畅，可更关注 **长尾帧 / @FrameInfo**，勿过度依赖单点秒级采样。",
        )
    if (
        w_app is not None
        and g_app is not None
        and g_app > 3
        and w_app < g_app * 0.93
    ):
        synthesis.append(
            "邻域内 **应用 CPU 低于全段均值**，与「该点仅因游戏逻辑把应用 CPU 打满而掉帧」的假设 **一致性偏弱**；"
            "可优先怀疑 **GPU 单帧尖峰、显示合成、VSync** 等与图形管线相关因素。",
        )
    if (
        w_bt_max is not None
        and g_bt_mean is not None
        and w_bt_max <= g_bt_mean + 1.5
    ):
        synthesis.append(
            "该邻域 **电池温度未明显高于全段典型水平**，将 **热节流** 视为该点 **主因** 的依据 **偏弱**。",
        )
    if (
        g_gpu is not None
        and w_gpu is not None
        and g_gpu > 50
        and w_gpu >= g_gpu * 0.92
    ):
        synthesis.append(
            "全段与邻域 **GPU 占用均较高**，说明图形侧 **持续有负载**；"
            "秒级最低点常与 **单帧耗时波动** 叠加，需 **帧级数据** 才能精确定位。",
        )

    if synthesis:
        detail_parts.append("")
        detail_parts.append("**综合研判（多指标互证）**：")
        for s in synthesis:
            detail_parts.append(f"- {s}")

    findings.append(
        Finding(
            id=_new_id("minfps"),
            category=FindingCategory.drop,
            severity=sev,
            title=f"全段最低帧分析（{min_fps:.0f} FPS @ {t_at/1000:.1f}s）",
            detail="\n".join(detail_parts),
            time_start_ms=t_at,
            time_end_ms=t_at,
            evidence={
                "min_fps": min_fps,
                "at_time_ms": t_at,
                "target_fps": target_fps,
                "cause_hints": hints,
                "synthesis_lines": synthesis,
                "metrics_compare": metrics_compare,
                "window_sample_indices": [lo, imin, hi],
            },
        ),
    )
    return findings


def detect_findings(df: pd.DataFrame, target_fps: int) -> list[Finding]:
    findings: list[Finding] = []
    fps = pd.to_numeric(df["fps"], errors="coerce")
    t = pd.to_numeric(df["time_ms"], errors="coerce")
    valid = fps.notna() & t.notna()
    if not valid.any():
        findings.append(
            Finding(
                id=_new_id("data"),
                category=FindingCategory.stability,
                severity=FindingSeverity.warn,
                title="帧率数据不可用",
                detail="Data_v4 中 FPS 列无法解析为数值，跳过掉帧/尖刺检测。",
            ),
        )
        return findings

    dfv = df.loc[valid].reset_index(drop=True)
    fps_v = pd.to_numeric(dfv["fps"], errors="coerce")
    t_v = pd.to_numeric(dfv["time_ms"], errors="coerce")

    # 优先：全段最低帧 + 关联指标（用户最关心的「为什么最低」）
    findings.extend(_minimum_fps_root_cause_findings(dfv, target_fps))

    low_th = target_fps * LOW_FPS_RATIO
    spike_th = target_fps * SPIKE_FPS_RATIO

    # 低帧段：连续低于阈值（简化：按窗口聚合）
    bad = fps_v < low_th
    if bad.any():
        starts: list[int] = []
        ends: list[int] = []
        in_run = False
        start_i = 0
        for i, is_bad in enumerate(bad):
            if is_bad and not in_run:
                in_run = True
                start_i = i
            elif not is_bad and in_run:
                in_run = False
                if i - start_i >= 3:
                    starts.append(start_i)
                    ends.append(i - 1)
        if in_run and len(bad) - start_i >= 3:
            starts.append(start_i)
            ends.append(len(bad) - 1)

        for si, ei in zip(starts, ends, strict=False):
            ts0 = float(t_v.iloc[si])
            ts1 = float(t_v.iloc[ei])
            seg_fps = float(fps_v.iloc[si : ei + 1].mean())
            findings.append(
                Finding(
                    id=_new_id("lowfps"),
                    category=FindingCategory.drop,
                    severity=FindingSeverity.warn,
                    title="持续偏低帧时段",
                    detail=(
                        f"约 {ts0/1000:.1f}s ~ {ts1/1000:.1f}s 区间 FPS 均值约 {seg_fps:.1f}，"
                        f"低于目标 {target_fps} 的 {int(LOW_FPS_RATIO*100)}% 阈值。"
                        "可能与场景加载、画质压力或后台抢占有关，建议结合场景标注复测。"
                    ),
                    time_start_ms=ts0,
                    time_end_ms=ts1,
                    evidence={"mean_fps": seg_fps, "target_fps": target_fps},
                ),
            )

    # 尖刺（若与全局最低点重复叙述，仍保留：尖刺强调单点暴跌）
    spike_idx = fps_v[fps_v < spike_th].index
    if len(spike_idx) > 0:
        i = int(spike_idx[0])
        ts = float(t_v.iloc[i])
        fv = float(fps_v.iloc[i])
        findings.append(
            Finding(
                id=_new_id("spike"),
                category=FindingCategory.drop,
                severity=FindingSeverity.critical,
                title="帧率尖刺",
                detail=(
                    f"在约 {ts/1000:.2f}s 出现 FPS 跌至 {fv:.1f} 的尖刺。"
                    "建议在该时刻附近用 Perfetto / 场景标记对照 CPU/GPU 与线程热点。"
                ),
                time_start_ms=ts,
                time_end_ms=ts,
                evidence={"fps": fv, "target_fps": target_fps},
            ),
        )

    # 帧不稳：变异系数
    mean_fps = float(fps_v.mean())
    std_fps = float(fps_v.std()) if len(fps_v) > 1 else 0.0
    cv = std_fps / mean_fps if mean_fps > 0 else 0.0
    if cv >= FPS_CV_WARN:
        findings.append(
            Finding(
                id=_new_id("stab"),
                category=FindingCategory.stability,
                severity=FindingSeverity.info,
                title="帧率波动较大",
                detail=(
                    f"全时段 FPS 变异系数约 {cv:.2f}（均值为 {mean_fps:.1f}），"
                    "体感上可能表现为不够「稳」。可关注画质档位、帧率模式与温控策略。"
                ),
                evidence={"cv": cv, "mean_fps": mean_fps},
            ),
        )

    # 温度（全段）
    if "battery_temp" in dfv.columns:
        bt = pd.to_numeric(dfv["battery_temp"], errors="coerce").dropna()
        if len(bt) >= 10:
            dt = bt.diff().abs()
            if dt.max() >= THERMAL_DELTA_WARN_C:
                findings.append(
                    Finding(
                        id=_new_id("thermal"),
                        category=FindingCategory.thermal,
                        severity=FindingSeverity.warn,
                        title="电池温度变化明显",
                        detail=(
                            f"相邻采样间温度变化最大约 {float(dt.max()):.1f}℃，"
                            "可能与散热条件或负载突变相关；建议固定室温与电量复测。"
                        ),
                        evidence={"max_step_c": float(dt.max())},
                    ),
                )
        elif not bt.empty:
            findings.append(
                Finding(
                    id=_new_id("thermal"),
                    category=FindingCategory.thermal,
                    severity=FindingSeverity.info,
                    title="温度数据可用",
                    detail="导出包含电池温度列，但未达到异常跃迁阈值；仍建议关注高负载段环境温度。",
                    evidence={"max_temp": float(bt.max())},
                ),
            )
    else:
        findings.append(
            Finding(
                id=_new_id("thermal-miss"),
                category=FindingCategory.thermal,
                severity=FindingSeverity.info,
                title="本文件未包含温度项",
                detail="当前导出未映射到电池温度列，无法进行温升类洞察；可在 PerfDog 中开启相关指标后重导。",
            ),
        )

    # 若完全没有其它掉帧类 finding，补一条说明（已有「最低帧分析」时不重复「未检出」）
    has_drop = any(
        f.category == FindingCategory.drop and "最低帧分析" not in f.title
        for f in findings
    )
    has_min_fps_analysis = any("最低帧分析" in f.title for f in findings)
    if not has_drop and mean_fps > 0 and not has_min_fps_analysis:
        findings.append(
            Finding(
                id=_new_id("drop-ok"),
                category=FindingCategory.drop,
                severity=FindingSeverity.info,
                title="未检出明显持续低帧段",
                detail=(
                    f"在默认阈值下未识别长段低帧；目标帧率按 {target_fps} 推断。"
                    "若仍体感卡顿，建议导出 @FrameInfo 或提高采样密度后重试。"
                ),
                evidence={"mean_fps": mean_fps},
            ),
        )

    return findings
