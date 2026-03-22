"""游戏性能策略 × PerfDog 联合分析引擎（纯函数，无 GUI/磁盘）。"""

from __future__ import annotations

from toolkit.sdk.joint_models import (
    JointAssessmentReport,
    JointAssessOptions,
    JointSuggestion,
    ObservationsSnapshot,
    PolicySnapshot,
)

from .observations import parse_numeric_metrics_from_lines

DISCLAIMER_ZH = (
    "说明：以下为基于当前 XML 策略摘要与单份 PerfDog 导出做的**启发式对照**，"
    "不构成唯一根因结论；环境与会话差异较大，**请结合复测与业务侧配置流程**再做决策。"
)


def _norm_pkg(s: str | None) -> str:
    return (s or "").strip().lower()


def _freq_data_unusable(observations: ObservationsSnapshot) -> bool:
    return any("JA-SC-004" in g or "频点类数据" in g for g in observations.data_gaps)


def _policy_gpu_range(policy: PolicySnapshot) -> tuple[int | None, int | None]:
    """策略表 Gpu 频点：取所有温档行的最小下限与最大上限（Hz）。"""
    mins: list[int] = []
    maxs: list[int] = []
    for row in policy.freq_rows:
        if row.gpu_min_hz is not None and row.gpu_min_hz > 0:
            mins.append(row.gpu_min_hz)
        if row.gpu_max_hz is not None and row.gpu_max_hz > 0:
            maxs.append(row.gpu_max_hz)
    if not mins and not maxs:
        return None, None
    return (min(mins) if mins else None, max(maxs) if maxs else None)


def _thread_related_finding(observations: ObservationsSnapshot) -> list[str]:
    ids: list[str] = []
    for f in observations.finding_summaries:
        cat = (f.category or "").lower()
        title = f.title_or_text or ""
        if cat == "thread" or "线程" in title or "绑核" in title:
            ids.append(f.id)
    return ids


def assess_joint(
    policy: PolicySnapshot,
    observations: ObservationsSnapshot,
    *,
    options: JointAssessOptions | None = None,
) -> JointAssessmentReport:
    opts = options or JointAssessOptions()
    warnings: list[str] = []

    pol_pkg = (policy.package_name or "").strip()
    obs_pkg = (observations.package_name or "").strip()
    if not pol_pkg or not obs_pkg:
        warnings.append(
            "无法校验包名：策略侧或 PerfDog 侧包名为空，联合结论未对齐到具体应用包名。",
        )
    elif _norm_pkg(pol_pkg) != _norm_pkg(obs_pkg):
        if not opts.skip_package_warning:
            warnings.append(
                f"包名不一致：游戏性能配置为「{pol_pkg}」，PerfDog 会话为「{obs_pkg}」。"
                "请确认是否为同一应用后再解读结论。",
            )

    policy_section: list[str] = [
        f"包名：{policy.package_name or '（未填）'}；性能模式：{policy.mode_name or '（未填）'}。",
    ]
    if policy.game_alias:
        policy_section.append(f"展示别名：{policy.game_alias}。")
    if policy.bindcore_summary:
        policy_section.append(f"BindCore 摘要：{policy.bindcore_summary}")
    else:
        policy_section.append("BindCore：当前模式未生成可读摘要（可能未配置或结构未识别）。")
    if policy.freq_rows:
        policy_section.append(
            f"策略频点表：共 {len(policy.freq_rows)} 个温档行（Gold/Prime/GPU 上下限以 XML 解析为准）。",
        )
    else:
        policy_section.append("策略频点表：当前包/模式下无温档行。")
    for h in policy.strategy_highlights[:6]:
        policy_section.append(f"其他策略要点：{h}")

    observation_section: list[str] = []
    if observations.package_name:
        observation_section.append(f"PerfDog 识别包名：{observations.package_name}。")
    if observations.duration_ms is not None:
        observation_section.append(f"记录时长约 {observations.duration_ms} ms。")
    if observations.target_fps_hint is not None:
        observation_section.append(f"推断目标帧率：{observations.target_fps_hint}。")
    if observations.metric_lines:
        observation_section.append("核心摘要指标（节选）：")
        observation_section.extend(f"- {line}" for line in observations.metric_lines[:12])
    if observations.finding_summaries:
        observation_section.append(
            f"洞察条目数：{len(observations.finding_summaries)}（详见 PerfDog 报告主体）。",
        )
    if observations.data_gaps:
        observation_section.append("数据缺口：")
        observation_section.extend(f"- {g}" for g in observations.data_gaps)

    nums = parse_numeric_metrics_from_lines(observations.metric_lines)
    gpu_mean = nums.get("GPU 频率均值(MHz)")
    cpu_min_mean = nums.get("CPU 各核频率均值最小(MHz)")

    consistency_section: list[str] = []
    g_lo, g_hi = _policy_gpu_range(policy)
    if gpu_mean is not None and g_lo is not None and g_hi is not None and not _freq_data_unusable(observations):
        if gpu_mean < g_lo * 0.92:
            consistency_section.append(
                "观测 GPU 频率均值低于策略表 Gpu 下限较多：可能与温控、功耗墙或场景调度有关，"
                "也可能与导出列映射/采样粒度有关，需结合温度与功耗复测后再判断。",
            )
        elif gpu_mean > g_hi * 1.05:
            consistency_section.append(
                "观测 GPU 频率均值高于策略表 Gpu 上限较多：可能当前会话未命中该温档策略，"
                "或策略表与实机调度存在偏差，建议对照热等级与场景码。",
            )
        else:
            consistency_section.append(
                "GPU 频率均值落在策略表 Gpu 频点区间内（粗粒度对照），与策略表未出现明显矛盾。",
            )
    elif policy.freq_rows and not _freq_data_unusable(observations) and gpu_mean is None:
        consistency_section.append(
            "策略表存在频点配置，但摘要中未能解析到 GPU 频率均值数值，仅做定性并列展示。",
        )
    else:
        consistency_section.append(
            "在缺少一侧频点数据或策略温档行时，仅并列展示策略与观测摘要，不做数值强绑定推断。",
        )

    if policy.bindcore_summary and _thread_related_finding(observations):
        consistency_section.append(
            "策略侧存在 BindCore 摘要，且观测侧出现线程/绑核相关洞察：可对照线程负载与绑核配置做复查。",
        )
    elif policy.bindcore_summary:
        consistency_section.append(
            "策略侧有 BindCore 摘要，但本次报告未突出线程类洞察：绑核与帧率关系需更多上下文再评估。",
        )

    if opts.skip_package_warning and pol_pkg and obs_pkg and _norm_pkg(pol_pkg) != _norm_pkg(obs_pkg):
        consistency_section.append(
            "用户已确认在包名不一致情况下继续：以下结论仅作参考，务必核对是否同一应用会话。",
        )

    bindcore_suggestions: list[JointSuggestion] = []
    freq_suggestions: list[JointSuggestion] = []
    bindcore_insufficient_reason: str | None = None
    freq_insufficient_reason: str | None = None

    bsum = (policy.bindcore_summary or "").strip()
    thread_ids = _thread_related_finding(observations)
    if bsum and thread_ids:
        bindcore_suggestions.append(
            JointSuggestion(
                id="ja-bind-1",
                text=(
                    "结合 BindCore 配置与线程类洞察，建议在测试计划中增加「绑核与关键线程 CPU 占用」"
                    "的对照采集（如固定场景复测），观察帧率与功耗变化。"
                ),
                basis="策略中存在 BindCore 摘要，且观测报告含线程/绑核相关 finding。",
                related_finding_ids=thread_ids,
                severity_hint="warn",
            ),
        )
    elif bsum:
        bindcore_suggestions.append(
            JointSuggestion(
                id="ja-bind-2",
                text=(
                    "策略已配置 BindCore，但本次 PerfDog 报告未突出线程瓶颈；"
                    "若实机仍有卡顿，可补充线程采样或场景化复测后再评估绑核收益。"
                ),
                basis="策略侧存在 BindCore 摘要；观测侧未发现显著线程类 finding。",
                related_finding_ids=[],
                severity_hint="info",
            ),
        )
    else:
        if not thread_ids:
            bindcore_insufficient_reason = (
                "当前策略未提供 BindCore 可读摘要，且报告中无线程类洞察，"
                "无法给出可溯源的绑核调整建议。"
            )
        else:
            bindcore_insufficient_reason = (
                "观测侧存在线程类信息，但策略未提供 BindCore 摘要，无法与 XML 绑核配置逐项对照。"
            )

    if _freq_data_unusable(observations):
        freq_insufficient_reason = (
            "观测侧缺少 CPU/GPU 频点类摘要指标（JA-SC-004），"
            "无法与策略频点表做数值对照，不提供频点启发式建议。"
        )
    elif not policy.freq_rows:
        freq_insufficient_reason = (
            "当前游戏/模式下策略表无温档频点行，无法与 PerfDog 频率摘要对照。"
        )
    elif gpu_mean is not None and g_lo is not None and g_hi is not None:
        if gpu_mean < g_lo * 0.92:
            freq_related = [f.id for f in observations.finding_summaries if f.category == "freq"]
            freq_suggestions.append(
                JointSuggestion(
                    id="ja-freq-1",
                    text=(
                        "观测 GPU 频率均值明显低于策略 Gpu 下限：可能与温控/限频或负载有关，"
                        "可结合温度、功耗与场景复测；不宜单凭一条曲线断定唯一根因。"
                    ),
                    basis=(
                        f"PerfDog 摘要 GPU 频率均值约为 {gpu_mean:.0f} MHz；"
                        f"策略 Gpu 区间约 [{g_lo}, {g_hi}] MHz。"
                    ),
                    related_finding_ids=freq_related or None,
                    severity_hint="warn",
                ),
            )
        elif cpu_min_mean is not None and cpu_min_mean > 0:
            freq_suggestions.append(
                JointSuggestion(
                    id="ja-freq-2",
                    text=(
                        "已同时具备策略频点表与 CPU/GPU 频率摘要："
                        "建议按温档与场景记录对照，关注是否长期贴近策略下限运行。"
                    ),
                    basis="策略表含多温档频点；摘要含 CPU 各核与 GPU 频率统计。",
                    related_finding_ids=None,
                    severity_hint="info",
                ),
            )
        else:
            freq_suggestions.append(
                JointSuggestion(
                    id="ja-freq-3",
                    text=(
                        "策略频点表与 GPU 频率摘要可同时参考："
                        "若出现帧率问题，可记录当时热等级并对照策略温档行做复测矩阵。"
                    ),
                    basis="策略表存在温档行且观测侧含 GPU 频率均值。",
                    related_finding_ids=None,
                    severity_hint="info",
                ),
            )
    else:
        freq_insufficient_reason = (
            "策略或观测侧信息不足以形成频点数值对照（例如缺少 GPU 频率摘要或策略 Gpu 区间）。"
        )

    return JointAssessmentReport(
        policy_section=policy_section,
        observation_section=observation_section,
        consistency_section=consistency_section,
        bindcore_suggestions=bindcore_suggestions,
        freq_suggestions=freq_suggestions,
        bindcore_insufficient_reason=bindcore_insufficient_reason,
        freq_insufficient_reason=freq_insufficient_reason,
        warnings=warnings,
        disclaimer=DISCLAIMER_ZH,
    )
