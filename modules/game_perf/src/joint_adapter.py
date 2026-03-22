"""GamePerfParser → PolicySnapshot（仅依赖本模块 parser/models）。"""

from __future__ import annotations

from .models import FreqRow, StrategyItem
from .parser import GamePerfParser
from toolkit.sdk.joint_models import FreqPolicyRow, PolicySnapshot


def _freq_row_to_policy_row(r: FreqRow) -> FreqPolicyRow:
    def hz(mn: int, mx: int, idx: str) -> tuple[int | None, int | None]:
        if not idx.strip() and mn <= 0 and mx <= 0:
            return None, None
        if idx.strip() and mn <= 0 and mx <= 0:
            return None, None
        return (mn if mn > 0 else None, mx if mx > 0 else None)

    gm, gx = hz(r.gold_min, r.gold_max, r.gold_index)
    pm, px = hz(r.prime_min, r.prime_max, r.prime_index)
    um, ux = hz(r.gpu_min, r.gpu_max, r.gpu_index)

    return FreqPolicyRow(
        temp_level=r.temp_level,
        trigger_temp=r.trigger_temp,
        gold_min_hz=gm,
        gold_max_hz=gx,
        prime_min_hz=pm,
        prime_max_hz=px,
        gpu_min_hz=um,
        gpu_max_hz=ux,
        gold_index=r.gold_index or "",
        prime_index=r.prime_index or "",
        gpu_index=r.gpu_index or "",
    )


def _summarize_bindcore(item: StrategyItem) -> str:
    parts: list[str] = []
    for p in item.pairs or []:
        if not isinstance(p, dict):
            continue
        h = str(p.get("header", "")).strip()
        v = str(p.get("value", "")).strip()
        if v:
            parts.append(f"{h}={v}" if h else v)
    text = "; ".join(parts)
    return text[:800] + ("…" if len(text) > 800 else "")


def _strategy_highlights(mode_items: list[StrategyItem]) -> list[str]:
    out: list[str] = []
    for item in mode_items:
        if item.tag == "BindCore":
            continue
        if item.tag == "PerfHint" and item.element is not None:
            oc = item.element.find("opcode")
            if oc is not None and (oc.text or "").strip():
                body = (oc.text or "").strip().replace("\n", " ")
                out.append(f"PerfHint：{body[:200]}{'…' if len(body) > 200 else ''}")
            continue
        # 其它块：用 tag + 少量键值
        snippet = _summarize_bindcore(item)
        if snippet:
            out.append(f"{item.tag}：{snippet[:160]}{'…' if len(snippet) > 160 else ''}")
    return out[:12]


def policy_snapshot_from_parser(
    parser: GamePerfParser,
    package: str,
    mode: str,
) -> PolicySnapshot:
    """package 为 Android 包名（与 ``get_package_for_alias`` 一致），mode 为性能模式名。"""
    rows = [r for r in parser.freq_rows if r.package_name == package and r.mode_name == mode]
    game_alias = rows[0].game_alias if rows else ""

    bindcore_summary = ""
    mode_items = parser.get_mode_level_data(package, mode)
    for item in mode_items:
        if item.tag == "BindCore":
            bindcore_summary = _summarize_bindcore(item)
            break

    highlights = _strategy_highlights(mode_items)

    return PolicySnapshot(
        package_name=package,
        mode_name=mode,
        game_alias=game_alias or None,
        freq_rows=[_freq_row_to_policy_row(r) for r in rows],
        bindcore_summary=bindcore_summary or None,
        strategy_highlights=highlights,
        source_xml_path=parser.xml_path or None,
    )
