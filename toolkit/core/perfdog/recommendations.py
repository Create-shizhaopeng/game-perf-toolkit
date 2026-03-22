"""由 Finding 生成可追溯的 Recommendation（FR-008 启发式措辞）。"""

from __future__ import annotations

import uuid

from toolkit.core.perfdog.report_types import Finding, FindingCategory, Recommendation


def _rid() -> str:
    return f"rec-{uuid.uuid4().hex[:8]}"


def _recommendations_for_minimum_fps(f: Finding) -> list[Recommendation]:
    """针对「全段最低帧分析」finding 生成可执行的解决建议。"""
    hints = (f.evidence or {}).get("cause_hints", [])
    blob = " ".join(hints)
    lines: list[str] = []

    if "GPU 占用" in blob:
        lines.append(
            "【画质与渲染】尝试降低分辨率、阴影、后处理或特效档位，关闭不必要的叠加层与录屏；"
            "对比最低帧是否随画质下降而明显改善。"
        )
    if "应用 CPU" in blob:
        lines.append(
            "【程序与线程】使用 CPU Profiler 或 Perfetto 查看主线程与渲染线程，"
            "减少单帧内重逻辑、同步 IO 与 GC 尖峰。"
        )
    if "整机 CPU" in blob or "后台" in blob:
        lines.append(
            "【系统环境】测试前关闭无关应用、云同步、杀毒扫描与系统更新；"
            "必要时飞行模式或固定网络条件后复测整机 CPU。"
        )
    if "GPU 频率" in blob or "限频" in blob or "降频" in blob:
        lines.append(
            "【温控与功耗】固定室温、散热条件与起始电量（如 50%～80%）复测；"
            "避免闷壳、边充边玩；可尝试降低目标帧率档位观察频率平台是否抬高。"
        )
    if "电池温度" in blob or "热状态" in blob:
        lines.append(
            "【热设计】拉长采样观察 FPS 与温度是否同步进入「平台期」；"
            "高温段与最低帧时间对齐时，优先改善散热再谈画质。"
        )
    if "窗口中位频率低于全段中位数" in blob or (
        "CPU 核" in blob and "窗口中位频率" in blob
    ):
        lines.append(
            "【CPU 与绑核】若已导出 @ThreadCpuUsageData，核对热点线程与 CPU 亲和性；"
            "避免少数大核长期打满而其它核闲置。"
        )
    if "瞬时频率低点" in blob or "不应解读为持续 CPU 限频" in blob:
        lines.append(
            "【CPU 频点】勿把秒级曲线上的**偶发频率谷底**当成持续限频；"
            "若需实锤，请用 **@ThreadCpuUsageData + Perfetto CPU 频率/线程** 与最低点对齐后再下结论。"
        )

    if not lines:
        lines.append(
            "【通用】在相同场景、画质与帧率模式下重复测试 2～3 次排除偶发；"
            "补充 @FrameInfo、Perfetto 抓取最低帧前后约 2s，对照渲染与合成耗时。"
        )

    recs: list[Recommendation] = [
        Recommendation(
            id=_rid(),
            finding_ids=[f.id],
            text=" ".join(lines) + "（以上为启发式建议，需结合项目与实机验证。）",
            category="最低帧解决建议",
        ),
    ]
    synth = (f.evidence or {}).get("synthesis_lines") or []
    if synth:
        recs.append(
            Recommendation(
                id=_rid(),
                finding_ids=[f.id],
                text=(
                    "【综合执行】将上文「综合研判」与具体排查动作对齐："
                    "**帧级**用 @FrameInfo / Perfetto 对准最低 FPS 时刻；"
                    "秒级指标仅作辅证。若 GPU 长期高占用，优先验证画质/分辨率/后处理与单帧 draw 成本。"
                ),
                category="综合排查",
            ),
        )
    return recs


def build_recommendations(findings: list[Finding]) -> list[Recommendation]:
    out: list[Recommendation] = []
    for f in findings:
        if f.category == FindingCategory.drop and "最低帧分析" in f.title:
            out.extend(_recommendations_for_minimum_fps(f))
        elif f.category == FindingCategory.drop and "尖刺" in f.title:
            out.append(
                Recommendation(
                    id=_rid(),
                    finding_ids=[f.id],
                    text=(
                        "【建议复测验证】在报告标注的时间段附近重复测试，"
                        "并同步记录场景/画质/帧率模式；必要时抓取 Perfetto 以确认线程与渲染管线。"
                    ),
                    category="采集建议",
                ),
            )
        elif f.category == FindingCategory.drop and "偏低" in f.title:
            out.append(
                Recommendation(
                    id=_rid(),
                    finding_ids=[f.id],
                    text=(
                        "【建议复测验证】将该低帧区间与关卡加载、大地图进入等事件对齐标注；"
                        "尝试降低画质或锁定目标帧率后对比曲线。"
                    ),
                    category="复现条件",
                ),
            )
        elif f.category == FindingCategory.stability and "波动" in f.title:
            out.append(
                Recommendation(
                    id=_rid(),
                    finding_ids=[f.id],
                    text=(
                        "【建议复测验证】关注帧率模式（VSync/高刷）与温控策略是否介入；"
                        "同场景多轮对比可减少偶发波动干扰。"
                    ),
                    category="环境",
                ),
            )
        elif f.category == FindingCategory.stability and "FrameInfo" in f.title:
            out.append(
                Recommendation(
                    id=_rid(),
                    finding_ids=[f.id],
                    text=(
                        "【帧级复测】用 Perfetto / 引擎工具对 p99、最大帧耗时点做抽样核对；"
                        "关注渲染、GPU 队列与合成；可对比降低画质或锁帧后是否改善。"
                        "（以上为启发式建议，需结合项目验证。）"
                    ),
                    category="采集建议",
                ),
            )
        elif f.category == FindingCategory.thermal and "未包含" in f.title:
            out.append(
                Recommendation(
                    id=_rid(),
                    finding_ids=[f.id],
                    text=(
                        "【建议复测验证】在 PerfDog 中启用温度相关指标并重新导出，"
                        "以便与帧率曲线对齐分析。"
                    ),
                    category="采集建议",
                ),
            )
        elif f.category == FindingCategory.thermal:
            out.append(
                Recommendation(
                    id=_rid(),
                    finding_ids=[f.id],
                    text=(
                        "【建议复测验证】固定室温、散热条件与起始电量；"
                        "高温告警时需区分环境温升与设备调度降频。"
                    ),
                    category="环境",
                ),
            )

    if not out:
        out.append(
            Recommendation(
                id=_rid(),
                finding_ids=[],
                text="【建议复测验证】当前结论为基于导出数据的启发式提示，请结合业务场景与实机体验综合判断。",
                category="通用",
            ),
        )
    return out
