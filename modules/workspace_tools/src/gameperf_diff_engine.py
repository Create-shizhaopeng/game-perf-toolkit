"""GameOptPolicy 语义 diff 生成（lxml，不依赖 game_perf）"""

from __future__ import annotations

import hashlib
from typing import Any

from lxml import etree

from .gameperf_diff_models import DiffItem


def _make_id(comparator_index: int, semantic_path: str, salt: str) -> str:
    h = hashlib.sha256(f"{comparator_index}|{semantic_path}|{salt}".encode("utf-8")).hexdigest()
    return h[:16]


def _clip(s: str | None, n: int = 160) -> str | None:
    if s is None:
        return None
    t = s.strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def navigate_path(root: etree._Element, steps: list[dict[str, Any]]) -> etree._Element | None:
    """按 merge_spec['path'] 定位节点。"""
    node: etree._Element | None = root
    for st in steps:
        if node is None:
            return None
        tag = st["tag"]
        if "index" in st:
            idx = int(st["index"])
            matches = [c for c in node if c.tag == tag]
            if idx < 0 or idx >= len(matches):
                return None
            node = matches[idx]
            continue
        attrs = st.get("attrs") or {}
        nxt: etree._Element | None = None
        for c in node:
            if c.tag != tag:
                continue
            if all(c.get(k) == v for k, v in attrs.items()):
                nxt = c
                break
        node = nxt
    return node


def _clusters(parent: etree._Element | None, section: str) -> dict[str, etree._Element]:
    if parent is None:
        return {}
    sec = parent.find(section)
    if sec is None:
        return {}
    return {cl.get("name") or "": cl for cl in sec.findall("cluster") if cl.get("name")}


def _diff_preenv(
    b_root: etree._Element,
    c_root: etree._Element,
    comparator_index: int,
    out: list[DiffItem],
) -> None:
    b = b_root.find("PreEnv")
    c = c_root.find("PreEnv")
    if b is None and c is None:
        return
    if b is None or c is None:
        out.append(
            DiffItem(
                id=_make_id(comparator_index, "PreEnv", "block"),
                semantic_path="PreEnv",
                comparator_index=comparator_index,
                severity="missing_left" if b is None else "missing_right",
                left_snippet=_clip(etree.tostring(b, encoding="unicode") if b is not None else None),
                right_snippet=_clip(etree.tostring(c, encoding="unicode") if c is not None else None),
                mergeable=False,
                merge_spec={},
            )
        )
        return
    for section in ("CPU", "GPU"):
        bn = _clusters(b, section)
        cn = _clusters(c, section)
        for name in sorted(set(bn) | set(cn)):
            be, ce = bn.get(name), cn.get(name)
            path = [
                {"tag": "PreEnv"},
                {"tag": section},
                {"tag": "cluster", "attrs": {"name": name}},
            ]
            if be is None:
                out.append(
                    DiffItem(
                        id=_make_id(comparator_index, f"PreEnv/{section}/cluster[{name}]", "missL"),
                        semantic_path=f"PreEnv/{section}/cluster[{name}]",
                        comparator_index=comparator_index,
                        severity="missing_left",
                        left_snippet=None,
                        right_snippet=_clip((ce.text or "").strip() if ce is not None else None),
                        mergeable=False,
                        merge_spec={},
                    )
                )
                continue
            if ce is None:
                out.append(
                    DiffItem(
                        id=_make_id(comparator_index, f"PreEnv/{section}/cluster[{name}]", "missR"),
                        semantic_path=f"PreEnv/{section}/cluster[{name}]",
                        comparator_index=comparator_index,
                        severity="missing_right",
                        left_snippet=_clip((be.text or "").strip()),
                        right_snippet=None,
                        mergeable=False,
                        merge_spec={},
                    )
                )
                continue
            bt = (be.text or "").strip()
            ct = (ce.text or "").strip()
            if bt != ct:
                out.append(
                    DiffItem(
                        id=_make_id(comparator_index, f"PreEnv/{section}/cluster[{name}]", "val"),
                        semantic_path=f"PreEnv/{section}/cluster[{name}]",
                        comparator_index=comparator_index,
                        severity="value_changed",
                        left_snippet=_clip(bt),
                        right_snippet=_clip(ct),
                        mergeable=True,
                        merge_spec={"kind": "text_at_path", "path": path},
                    )
                )


def _scene_texts(game_el: etree._Element) -> list[str]:
    sl = game_el.find("SceneList")
    if sl is None:
        return []
    return [(s.text or "").strip() for s in sl.findall("scene")]


def _diff_baseinfo(
    b_root: etree._Element,
    c_root: etree._Element,
    comparator_index: int,
    out: list[DiffItem],
) -> None:
    b = b_root.find("BaseInfo")
    c = c_root.find("BaseInfo")
    if b is None and c is None:
        return
    if b is None or c is None:
        out.append(
            DiffItem(
                id=_make_id(comparator_index, "BaseInfo", "block"),
                semantic_path="BaseInfo",
                comparator_index=comparator_index,
                severity="missing_left" if b is None else "missing_right",
                left_snippet="(无)" if b is None else "(有)",
                right_snippet="(无)" if c is None else "(有)",
                mergeable=False,
                merge_spec={},
            )
        )
        return
    bg = {g.get("name") or "": g for g in b.findall("Game") if g.get("name")}
    cg = {g.get("name") or "": g for g in c.findall("Game") if g.get("name")}
    for pkg in sorted(set(bg) | set(cg)):
        bgm, cgm = bg.get(pkg), cg.get(pkg)
        if bgm is None or cgm is None:
            out.append(
                DiffItem(
                    id=_make_id(comparator_index, f"BaseInfo/Game[{pkg}]", "game"),
                    semantic_path=f"BaseInfo/Game[{pkg}]",
                    comparator_index=comparator_index,
                    severity="missing_left" if bgm is None else "missing_right",
                    left_snippet="(无)" if bgm is None else "(有)",
                    right_snippet="(无)" if cgm is None else "(有)",
                    mergeable=False,
                    merge_spec={},
                )
            )
            continue
        bs, cs = _scene_texts(bgm), _scene_texts(cgm)
        if bs != cs:
            path = [{"tag": "BaseInfo"}, {"tag": "Game", "attrs": {"name": pkg}}, {"tag": "SceneList"}]
            out.append(
                DiffItem(
                    id=_make_id(comparator_index, f"BaseInfo/Game[{pkg}]/SceneList", "sc"),
                    semantic_path=f"BaseInfo/Game[{pkg}]/SceneList",
                    comparator_index=comparator_index,
                    severity="value_changed",
                    left_snippet=_clip(" ".join(bs)),
                    right_snippet=_clip(" ".join(cs)),
                    mergeable=True,
                    merge_spec={"kind": "scene_list_at_path", "path": path},
                )
            )


def _find_child_by_name(parent: etree._Element, tag: str, name: str) -> etree._Element | None:
    for ch in parent:
        if ch.tag == tag and ch.get("name") == name:
            return ch
    return None


def _norm_subtree(el: etree._Element) -> str:
    return etree.tostring(el, encoding="unicode", pretty_print=True).strip()


def _diff_mode(
    b_game: etree._Element,
    c_game: etree._Element,
    pkg: str,
    mode_name: str,
    comparator_index: int,
    out: list[DiffItem],
) -> None:
    bm = _find_child_by_name(b_game, "Mode", mode_name)
    cm = _find_child_by_name(c_game, "Mode", mode_name)
    if bm is None and cm is None:
        return
    if bm is None or cm is None:
        out.append(
            DiffItem(
                id=_make_id(comparator_index, f"GamePolicy/{pkg}/Mode[{mode_name}]", "m"),
                semantic_path=f"GamePolicy/Game[{pkg}]/Mode[{mode_name}]",
                comparator_index=comparator_index,
                severity="missing_left" if bm is None else "missing_right",
                left_snippet="(无)" if bm is None else "(有)",
                right_snippet="(无)" if cm is None else "(有)",
                mergeable=False,
                merge_spec={},
            )
        )
        return
    base_path = [
        {"tag": "GamePolicy"},
        {"tag": "Game", "attrs": {"name": pkg}},
        {"tag": "Mode", "attrs": {"name": mode_name}},
    ]
    for leaf_tag in ("ThermalSceneCode",):
        bel, cel = bm.find(leaf_tag), cm.find(leaf_tag)
        bt = (bel.text or "").strip() if bel is not None else ""
        ct = (cel.text or "").strip() if cel is not None else ""
        if bel is None and cel is None:
            continue
        if bel is None or cel is None or bt != ct:
            path = [*base_path, {"tag": leaf_tag}]
            out.append(
                DiffItem(
                    id=_make_id(comparator_index, f"{pkg}/{mode_name}/{leaf_tag}", "t"),
                    semantic_path=f"GamePolicy/Game[{pkg}]/Mode[{mode_name}]/{leaf_tag}",
                    comparator_index=comparator_index,
                    severity="value_changed"
                    if bel is not None and cel is not None
                    else ("missing_left" if bel is None else "missing_right"),
                    left_snippet=_clip(bt) if bel is not None else None,
                    right_snippet=_clip(ct) if cel is not None else None,
                    mergeable=bel is not None and cel is not None,
                    merge_spec={"kind": "text_at_path", "path": path} if bel is not None and cel is not None else {},
                )
            )
    bph, cph = bm.find("PerfHint"), cm.find("PerfHint")
    if bph is None and cph is None:
        pass
    elif bph is None or cph is None or _norm_subtree(bph) != _norm_subtree(cph):
        path = [*base_path, {"tag": "PerfHint"}]
        out.append(
            DiffItem(
                id=_make_id(comparator_index, f"{pkg}/{mode_name}/PerfHint", "ph"),
                semantic_path=f"GamePolicy/Game[{pkg}]/Mode[{mode_name}]/PerfHint",
                comparator_index=comparator_index,
                severity="value_changed"
                if bph is not None and cph is not None
                else ("missing_left" if bph is None else "missing_right"),
                left_snippet=_clip(_norm_subtree(bph)) if bph is not None else None,
                right_snippet=_clip(_norm_subtree(cph)) if cph is not None else None,
                mergeable=bph is not None and cph is not None,
                merge_spec={"kind": "subtree_at_path", "path": path} if bph is not None and cph is not None else {},
            )
        )
    bpol, cpol = bm.find("Policy"), cm.find("Policy")
    if bpol is None and cpol is None:
        return
    if bpol is None or cpol is None:
        out.append(
            DiffItem(
                id=_make_id(comparator_index, f"{pkg}/{mode_name}/Policy", "pol"),
                semantic_path=f"GamePolicy/Game[{pkg}]/Mode[{mode_name}]/Policy",
                comparator_index=comparator_index,
                severity="missing_left" if bpol is None else "missing_right",
                left_snippet=None,
                right_snippet=None,
                mergeable=False,
                merge_spec={},
            )
        )
        return
    btls = {tl.get("level"): tl for tl in bpol.findall("TempLevel") if tl.get("level") is not None}
    ctls = {tl.get("level"): tl for tl in cpol.findall("TempLevel") if tl.get("level") is not None}
    for lvl in sorted(set(btls) | set(ctls)):
        btl, ctl = btls.get(lvl), ctls.get(lvl)
        if btl is None or ctl is None:
            out.append(
                DiffItem(
                    id=_make_id(comparator_index, f"{pkg}/{mode_name}/TL{lvl}", "tl"),
                    semantic_path=f"GamePolicy/Game[{pkg}]/Mode[{mode_name}]/TempLevel[{lvl}]",
                    comparator_index=comparator_index,
                    severity="missing_left" if btl is None else "missing_right",
                    left_snippet=None,
                    right_snippet=None,
                    mergeable=False,
                    merge_spec={},
                )
            )
            continue
        bitems = {it.get("name"): it for it in btl.findall("item") if it.get("name")}
        citems = {it.get("name"): it for it in ctl.findall("item") if it.get("name")}
        for iname in sorted(set(bitems) | set(citems)):
            bi, ci = bitems.get(iname), citems.get(iname)
            if bi is None or ci is None:
                continue
            btxt, ctxt = (bi.text or "").strip(), (ci.text or "").strip()
            if btxt != ctxt:
                path = [
                    *base_path,
                    {"tag": "Policy"},
                    {"tag": "TempLevel", "attrs": {"level": str(lvl)}},
                    {"tag": "item", "attrs": {"name": iname}},
                ]
                out.append(
                    DiffItem(
                        id=_make_id(comparator_index, f"{pkg}/{mode_name}/item{iname}{lvl}", "it"),
                        semantic_path=(
                            f"GamePolicy/Game[{pkg}]/Mode[{mode_name}]/"
                            f"TempLevel[{lvl}]/item[{iname}]"
                        ),
                        comparator_index=comparator_index,
                        severity="value_changed",
                        left_snippet=_clip(btxt),
                        right_snippet=_clip(ctxt),
                        mergeable=True,
                        merge_spec={"kind": "text_at_path", "path": path},
                    )
                )
    for extra in ("BindCore",):
        bx, cx = bpol.find(extra), cpol.find(extra)
        if bx is None and cx is None:
            continue
        if bx is None or cx is None or _norm_subtree(bx) != _norm_subtree(cx):
            path = [*base_path, {"tag": "Policy"}, {"tag": extra}]
            out.append(
                DiffItem(
                    id=_make_id(comparator_index, f"{pkg}/{mode_name}/{extra}", "bc"),
                    semantic_path=f"GamePolicy/Game[{pkg}]/Mode[{mode_name}]/Policy/{extra}",
                    comparator_index=comparator_index,
                    severity="value_changed"
                    if bx is not None and cx is not None
                    else ("missing_left" if bx is None else "missing_right"),
                    left_snippet=_clip(_norm_subtree(bx)) if bx is not None else None,
                    right_snippet=_clip(_norm_subtree(cx)) if cx is not None else None,
                    mergeable=bx is not None and cx is not None,
                    merge_spec={"kind": "subtree_at_path", "path": path} if bx is not None and cx is not None else {},
                )
            )


def _diff_gamepolicy(
    b_root: etree._Element,
    c_root: etree._Element,
    comparator_index: int,
    out: list[DiffItem],
) -> None:
    b = b_root.find("GamePolicy")
    c = c_root.find("GamePolicy")
    if b is None and c is None:
        return
    if b is None or c is None:
        out.append(
            DiffItem(
                id=_make_id(comparator_index, "GamePolicy", "block"),
                semantic_path="GamePolicy",
                comparator_index=comparator_index,
                severity="missing_left" if b is None else "missing_right",
                left_snippet="(无)" if b is None else "(有)",
                right_snippet="(无)" if c is None else "(有)",
                mergeable=False,
                merge_spec={},
            )
        )
        return
    bg = {g.get("name") or "": g for g in b.findall("Game") if g.get("name")}
    cg = {g.get("name") or "": g for g in c.findall("Game") if g.get("name")}
    for pkg in sorted(set(bg) | set(cg)):
        bgm, cgm = bg.get(pkg), cg.get(pkg)
        if bgm is None or cgm is None:
            out.append(
                DiffItem(
                    id=_make_id(comparator_index, f"GamePolicy/Game[{pkg}]", "g"),
                    semantic_path=f"GamePolicy/Game[{pkg}]",
                    comparator_index=comparator_index,
                    severity="missing_left" if bgm is None else "missing_right",
                    left_snippet=None,
                    right_snippet=None,
                    mergeable=False,
                    merge_spec={},
                )
            )
            continue
        path_game = [{"tag": "GamePolicy"}, {"tag": "Game", "attrs": {"name": pkg}}]
        btsc, ctsc = bgm.find("ThermalSceneCode"), cgm.find("ThermalSceneCode")
        btxt = (btsc.text or "").strip() if btsc is not None else ""
        ctxt = (ctsc.text or "").strip() if ctsc is not None else ""
        if btxt != ctxt and (btsc is not None or ctsc is not None):
            sev: Any = "value_changed"
            if btsc is None or ctsc is None:
                sev = "missing_left" if btsc is None else "missing_right"
            out.append(
                DiffItem(
                    id=_make_id(comparator_index, f"{pkg}/gameThermal", "gt"),
                    semantic_path=f"GamePolicy/Game[{pkg}]/ThermalSceneCode",
                    comparator_index=comparator_index,
                    severity=sev,
                    left_snippet=_clip(btxt) if btsc is not None else None,
                    right_snippet=_clip(ctxt) if ctsc is not None else None,
                    mergeable=btsc is not None and ctsc is not None,
                    merge_spec={"kind": "text_at_path", "path": [*path_game, {"tag": "ThermalSceneCode"}]}
                    if btsc is not None and ctsc is not None
                    else {},
                )
            )
        b_modes = {m.get("name") or "" for m in bgm.findall("Mode") if m.get("name")}
        c_modes = {m.get("name") or "" for m in cgm.findall("Mode") if m.get("name")}
        for mn in sorted(b_modes | c_modes):
            _diff_mode(bgm, cgm, pkg, mn, comparator_index, out)


def diff_root_attrs(
    b_root: etree._Element,
    c_root: etree._Element,
    comparator_index: int,
    out: list[DiffItem],
) -> None:
    ba = (b_root.get("version") or "").strip()
    ca = (c_root.get("version") or "").strip()
    if ba != ca:
        out.append(
            DiffItem(
                id=_make_id(comparator_index, "GameOptPolicy@version", "v"),
                semantic_path="GameOptPolicy@version",
                comparator_index=comparator_index,
                severity="value_changed",
                left_snippet=ba or "(空)",
                right_snippet=ca or "(空)",
                mergeable=True,
                merge_spec={"kind": "root_attr", "attr": "version"},
            )
        )


def build_diff_items(
    baseline: etree._Element,
    comparator: etree._Element,
    comparator_index: int,
) -> list[DiffItem]:
    out: list[DiffItem] = []
    diff_root_attrs(baseline, comparator, comparator_index, out)
    _diff_preenv(baseline, comparator, comparator_index, out)
    _diff_baseinfo(baseline, comparator, comparator_index, out)
    _diff_gamepolicy(baseline, comparator, comparator_index, out)
    return out


def apply_merge_spec(
    working: etree._Element,
    source: etree._Element,
    spec: dict[str, Any],
) -> None:
    """将 source 中对应路径的值应用到 working 树。"""
    kind = spec.get("kind")
    if kind == "root_attr":
        attr = spec["attr"]
        working.set(attr, source.get(attr))
        return
    if kind == "text_at_path":
        path: list[dict[str, Any]] = spec["path"]
        wn = navigate_path(working, path)
        sn = navigate_path(source, path)
        if wn is None or sn is None:
            return
        wn.text = sn.text
        return
    if kind == "subtree_at_path":
        path = spec["path"]
        parent_steps, leaf = path[:-1], path[-1]
        w_parent = navigate_path(working, parent_steps) if parent_steps else working
        s_parent = navigate_path(source, parent_steps) if parent_steps else source
        if w_parent is None or s_parent is None:
            return
        tag = leaf["tag"]
        w_old = None
        s_new = None
        if "attrs" in leaf:
            for ch in w_parent:
                if ch.tag == tag and all(ch.get(k) == v for k, v in (leaf.get("attrs") or {}).items()):
                    w_old = ch
                    break
            for ch in s_parent:
                if ch.tag == tag and all(ch.get(k) == v for k, v in (leaf.get("attrs") or {}).items()):
                    s_new = ch
                    break
        elif "index" in leaf:
            idx = int(leaf["index"])
            wm = [c for c in w_parent if c.tag == tag]
            sm = [c for c in s_parent if c.tag == tag]
            if idx < len(wm):
                w_old = wm[idx]
            if idx < len(sm):
                s_new = sm[idx]
        else:
            w_old = w_parent.find(tag)
            s_new = s_parent.find(tag)
        if w_old is None or s_new is None:
            return
        repl = etree.fromstring(etree.tostring(s_new, encoding="utf-8"))
        w_parent.replace(w_old, repl)
        return
    if kind == "scene_list_at_path":
        path = spec["path"]
        w_sl = navigate_path(working, path)
        s_sl = navigate_path(source, path)
        if w_sl is None or s_sl is None:
            return
        for ch in list(w_sl):
            w_sl.remove(ch)
        for ch in s_sl:
            w_sl.append(etree.fromstring(etree.tostring(ch, encoding="utf-8")))
        return
