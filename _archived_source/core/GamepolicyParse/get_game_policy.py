#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 gameperfconfig.xml 中按游戏名称或包名提取指定游戏的策略配置（Game 节点及其子节点）。
不依赖将整个配置文件加载到外部上下文，便于脚本化复用。
"""

import argparse
import io
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _ensure_utf8_io():
    """确保 stdout/stderr 使用 UTF-8，避免终端中文乱码（尤其 Windows 控制台）。"""
    if sys.platform == "win32":
        try:
            ctypes = __import__("ctypes")
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleOutputCP(65001)
            kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        else:
            if hasattr(sys.stdout, "buffer"):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass


def find_game_element(root, name_or_pkg: str, match_by_pkg_only: bool = False):
    """
    在 GamePolicy 下查找匹配 name 或 pkg 的 Game 元素。
    name_or_pkg: 游戏显示名（如「和平精英」）或包名（如 com.tencent.tmgp.pubgmhd），支持部分匹配。
    match_by_pkg_only: 为 True 时仅按 pkg 匹配（用于 --pkg 参数）。
    返回 (Game 元素, 匹配方式) 或 (None, None)。
    """
    game_policy = root.find("GamePolicy")
    if game_policy is None:
        return None, None
    key = name_or_pkg.strip().lower()
    for game in game_policy.findall("Game"):
        name = (game.get("name") or "").strip().lower()
        pkg = (game.get("pkg") or "").strip().lower()
        pkgs = [s.strip().lower() for s in pkg.replace(",", " ").split() if s.strip()]
        if match_by_pkg_only:
            if key in pkg or key in pkgs or any(key in p for p in pkgs):
                return game, "pkg"
            continue
        if key in name or key in pkg:
            return game, "name" if key in name else "pkg"
        if key in pkgs:
            return game, "pkg"
    return None, None


def get_preenv(root):
    """提取 PreEnv 中的 CPU/GPU 频率表，用于解释档位索引。"""
    preenv = root.find("PreEnv")
    if preenv is None:
        return {}
    out = {"CPU": {}, "GPU": {}}
    for tag in ("CPU", "GPU"):
        parent = preenv.find(tag)
        if parent is None:
            continue
        for c in parent.findall("cluster"):
            n = c.get("name") or c.get("id") or ""
            text = (c.text or "").strip()
            freqs = [int(x) for x in text.split()] if text else []
            out[tag][n] = freqs
    return out


def hex_mask_to_binary(hex_str: str, bits: int = 8) -> str:
    """
    将绑核策略的十六进制掩码转为二进制字符串输出。
    例如 "c0" -> "11000000", "3f" -> "00111111"
    """
    if not (hex_str or "").strip():
        return ""
    hex_str = hex_str.strip()
    try:
        n = int(hex_str, 16)
        # 按给定位数输出，不足补前导零
        if n == 0:
            return "0".zfill(bits)
        b = bin(n)[2:]
        if len(b) <= bits:
            return b.zfill(bits)
        return b  # 超过默认位数则返回实际长度
    except ValueError:
        return hex_str  # 非合法十六进制则原样返回


def resolve_freq_display(value_str: str, cluster_name: str, preenv: dict) -> str:
    """
    将 CPU/GPU 频率档位（如 "5_12"）转为具体频率范围描述。
    CPU 档位 0 为最低频，索引越大频率越高；GPU 档位 0 为最高频，索引越大频率越低。
    返回如 "1.36～3.32 GHz"（CPU）或 "342～607 MHz"（GPU），-1 表示无限制。
    """
    if not value_str or not preenv:
        return value_str or ""
    value_str = value_str.strip()
    parts = value_str.split("_")
    if len(parts) != 2:
        return value_str
    try:
        low_idx = int(parts[0].strip())
        high_idx = int(parts[1].strip())
    except ValueError:
        return value_str
    if cluster_name == "Gpu":
        freqs = preenv.get("GPU", {}).get("Gpu", [])
        is_gpu = True
    else:
        freqs = preenv.get("CPU", {}).get(cluster_name, [])
        is_gpu = False
    if not freqs:
        return value_str
    if low_idx == -1 and high_idx == -1:
        return "无限制"
    if low_idx == -1:
        low_idx = 0
    if high_idx == -1:
        high_idx = len(freqs) - 1
    if low_idx < 0 or high_idx < 0 or low_idx >= len(freqs) or high_idx >= len(freqs):
        return value_str
    f_lo = min(freqs[low_idx], freqs[high_idx])
    f_hi = max(freqs[low_idx], freqs[high_idx])
    if is_gpu:
        # GPU 单位 Hz，转为 MHz 显示
        return f"{f_lo // 1_000_000}～{f_hi // 1_000_000} MHz"
    # CPU 单位 kHz，转为 GHz 显示
    return f"{f_lo / 1_000_000:.2f}～{f_hi / 1_000_000:.2f} GHz"


def game_to_dict(game_el, preenv=None):
    """将 Game 元素转为嵌套 dict（便于 JSON 输出）。preenv 用于绑核二进制掩码与频率档位转具体频率。"""
    if game_el is None:
        return None
    d = {"@name": game_el.get("name"), "@pkg": game_el.get("pkg"), "@param": game_el.get("param")}
    for child in game_el:
        tag = child.tag
        if tag == "ThermalTempType":
            d[tag] = (child.text or "").strip()
        elif tag == "FpsAdjustLevel":
            d[tag] = (child.text or "").strip()
        elif tag == "FpsAdjustTime":
            d[tag] = (child.text or "").strip()
        elif tag == "JankAdjustLevel":
            d[tag] = (child.text or "").strip()
        elif tag == "JankAdjustTime":
            d[tag] = (child.text or "").strip()
        elif tag == "BindCore":
            d[tag] = []
            for tid in child.findall("tid"):
                raw = (tid.text or "").strip()
                entry = {"@name": tid.get("name"), "value": raw}
                if raw:
                    entry["value_binary"] = hex_mask_to_binary(raw)
                d[tag].append(entry)
        elif tag == "SceneOpt":
            d[tag] = []
            for scene in child.findall("Scene"):
                s = {"@id": scene.get("id"), "@time": scene.get("time")}
                s["items"] = []
                for item in scene.findall("item"):
                    itype = item.get("type")
                    iname = item.get("name")
                    val = (item.text or "").strip()
                    entry = {"@type": itype, "@name": iname, "value": val}
                    if itype == "freq" and iname and val and preenv:
                        entry["freq_display"] = resolve_freq_display(val, iname, preenv)
                    s["items"].append(entry)
                d[tag].append(s)
        elif tag == "Mode":
            mode_name = child.get("name") or child.get("id")
            if "Mode" not in d:
                d["Mode"] = {}
            mode_d = {}
            for sub in child:
                if sub.tag == "ThermalSceneCode":
                    mode_d[sub.tag] = (sub.text or "").strip()
                elif sub.tag == "FpsAdjustLevel":
                    mode_d[sub.tag] = (sub.text or "").strip()
                elif sub.tag == "FpsAdjustTime":
                    mode_d[sub.tag] = (sub.text or "").strip()
                elif sub.tag == "JankAdjustLevel":
                    mode_d[sub.tag] = (sub.text or "").strip()
                elif sub.tag == "JankAdjustTime":
                    mode_d[sub.tag] = (sub.text or "").strip()
                elif sub.tag == "BindCore":
                    mode_d[sub.tag] = []
                    for tid_el in sub.findall("tid"):
                        raw = (tid_el.text or "").strip()
                        entry = {"@name": tid_el.get("name"), "value": raw}
                        if raw:
                            entry["value_binary"] = hex_mask_to_binary(raw)
                        mode_d[sub.tag].append(entry)
                elif sub.tag == "PerfHint":
                    mode_d[sub.tag] = []
                    for op in sub.findall("opcode"):
                        mode_d[sub.tag].append({"@id": op.get("id"), "@time": op.get("time"), "value": (op.text or "").strip()})
                elif sub.tag == "Policy":
                    mode_d[sub.tag] = []
                    for tl in sub.findall("TempLevel"):
                        level_d = {"@level": tl.get("level"), "@temp": tl.get("temp"), "items": []}
                        for item in tl.findall("item"):
                            itype = item.get("type")
                            iname = item.get("name")
                            val = (item.text or "").strip()
                            entry = {"@type": itype, "@name": iname, "value": val}
                            if itype == "freq" and iname and val and preenv:
                                entry["freq_display"] = resolve_freq_display(val, iname, preenv)
                            level_d["items"].append(entry)
                        mode_d[sub.tag].append(level_d)
            d["Mode"][mode_name] = mode_d
    return d


def _get_cluster_list(preenv: dict) -> list:
    """按 PreEnv 频率表返回 [(cluster_name, is_gpu), ...] 有序列表。"""
    clusters = []
    for name in preenv.get("CPU", {}):
        clusters.append((name, False))
    for name in preenv.get("GPU", {}):
        clusters.append((name, True))
    return clusters


def _apply_fps_boost(base_value: str, boost: int, cluster_name: str,
                     is_gpu: bool, preenv: dict) -> str:
    """
    将 FpsAdjust boost 应用到频率档位范围并解析为显示字符串。
    CPU 簇：两端索引 += boost（频率上移）；GPU：两端索引 -= boost（频率上移）。
    """
    if not base_value or not preenv:
        return "—"
    parts = base_value.strip().split("_")
    if len(parts) != 2:
        return base_value
    try:
        low_idx = int(parts[0].strip())
        high_idx = int(parts[1].strip())
    except ValueError:
        return base_value
    if is_gpu:
        freqs = preenv.get("GPU", {}).get(cluster_name, [])
    else:
        freqs = preenv.get("CPU", {}).get(cluster_name, [])
    max_idx = len(freqs) - 1 if freqs else 0

    def _adj(idx):
        if idx == -1:
            return -1
        return max(0, idx - boost) if is_gpu else min(max_idx, idx + boost)

    return resolve_freq_display(f"{_adj(low_idx)}_{_adj(high_idx)}", cluster_name, preenv)


def print_report(d: dict, preenv: dict = None) -> None:
    """
    按固定格式输出游戏策略分析报告（Markdown）。
    d 为 game_to_dict() 返回的字典。preenv 用于解析帧率调节 boost 后的频率列。
    """
    name = d.get("@name") or "—"
    pkg = d.get("@pkg") or "—"
    thermal = d.get("ThermalTempType") or "—"
    has_bind = bool(d.get("BindCore"))
    has_scene = bool(d.get("SceneOpt"))
    has_fps = bool(d.get("FpsAdjustLevel") or d.get("FpsAdjustTime"))

    # ---------- Header：仅游戏名 + 包名 ----------
    lines = [
        "# 游戏策略分析报告",
        "",
        f"**游戏名**：{name}  ",
        f"**包名**：{pkg}",
        "",
        "---",
        "",
    ]

    # ---------- 目录 ----------
    lines.extend([
        "## 目录",
        "",
        "- [一、基本信息](#一基本信息)",
        "- [二、绑核（BindCore）](#二绑核bindcore)",
        "- [三、场景策略（SceneOpt）](#三场景策略sceneopt)",
        "- [四、各模式温控与频点](#四各模式温控与频点)",
    ])
    for mn in (d.get("Mode") or {}):
        lines.append("  - [%s](#%s)" % (mn, mn.lower().replace(" ", "-")))
    lines.extend([
        "- [五、分析与建议](#五分析与建议)",
        "",
    ])

    # ---------- 一、基本信息（精简表格） ----------
    lines.extend([
        "## 一、基本信息",
        "",
        "| 项目 | 配置 |",
        "|------|------|",
        f"| ThermalTempType | {thermal} |",
        f"| 游戏级 BindCore | {'有' if has_bind else '无'} |",
        f"| 游戏级 SceneOpt | {'有' if has_scene else '无'} |",
        f"| 游戏级 FpsAdjust | {'有' if has_fps else '无'} |",
        "",
    ])

    # ---------- 二、绑核（不变） ----------
    if d.get("BindCore"):
        lines.extend([
            "## 二、绑核（BindCore）",
            "",
            "| 线程名 | mask(hex) | 二进制 |",
            "|--------|------------|--------|",
        ])
        for t in d["BindCore"]:
            bin_str = t.get("value_binary", "")
            lines.append("| %s | %s | %s |" % (t.get("@name", ""), t.get("value", ""), ("0b" + bin_str) if bin_str else "—"))
        lines.extend(["", ""])
    else:
        lines.extend(["## 二、绑核（BindCore）", "", "无。", "", ""])

    # ---------- 三、场景策略（不变） ----------
    if d.get("SceneOpt"):
        lines.extend([
            "## 三、场景策略（SceneOpt）",
            "",
        ])
        for s in d["SceneOpt"]:
            parts = []
            for it in s.get("items", []):
                p = it.get("value", "")
                if it.get("freq_display"):
                    p += " (%s)" % it["freq_display"]
                parts.append(p)
            lines.append("- **Scene id=%s**，time=%s ms：%s" % (s.get("@id", ""), s.get("@time", ""), "、".join(parts)))
        lines.extend(["", ""])
    else:
        lines.extend(["## 三、场景策略（SceneOpt）", "", "无。", "", ""])

    # ---------- 四、各模式温控与频点（帧率调节合并到此） ----------
    modes = d.get("Mode") or {}
    lines.extend(["## 四、各模式温控与频点", ""])

    game_fps_level = d.get("FpsAdjustLevel") or ""
    game_fps_time = d.get("FpsAdjustTime") or ""
    if game_fps_level or game_fps_time:
        lines.append(f"> 游戏级帧率调节：FpsAdjustLevel={game_fps_level}，FpsAdjustTime={game_fps_time} ms（适用于所有模式）")
        lines.append("")

    for mode_name, mode_d in modes.items():
        lines.append("### %s" % mode_name)
        lines.append("")
        lines.append("ThermalSceneCode=%s" % (mode_d.get("ThermalSceneCode") or "—"))
        lines.append("")

        if mode_d.get("PerfHint"):
            for op in mode_d["PerfHint"]:
                lines.append("- PerfHint：%s → %s" % (op.get("@id", ""), op.get("value", "")))
            lines.append("")

        eff_fps_level = mode_d.get("FpsAdjustLevel") or game_fps_level
        eff_fps_time = mode_d.get("FpsAdjustTime") or game_fps_time
        fps_values = [v.strip() for v in eff_fps_level.split(",")] if eff_fps_level else []

        clusters = _get_cluster_list(preenv) if preenv else []
        boost_map = {}
        if fps_values and clusters:
            for ci, (cname, _) in enumerate(clusters):
                try:
                    boost_map[cname] = int(fps_values[ci]) if ci < len(fps_values) else 0
                except ValueError:
                    boost_map[cname] = 0
        show_boost = bool(boost_map) and any(v != 0 for v in boost_map.values())

        if eff_fps_level or eff_fps_time:
            source = "模式级" if mode_d.get("FpsAdjustLevel") else "游戏级"
            lines.append("- 帧率调节（%s）：FpsAdjustLevel=%s，FpsAdjustTime=%s ms" % (source, eff_fps_level, eff_fps_time))
            lines.append("")

        policy = mode_d.get("Policy") or []
        if policy:
            base_names = []
            for it in policy[0].get("items", []):
                if (it.get("@type") or "") == "freq":
                    n = (it.get("@name") or "").strip()
                    if n:
                        base_names.append(n)
            header = ["温控档", "温度(℃)"] + base_names
            if show_boost:
                header += ["%s boost" % cn for cn, _ in clusters]
            lines.append("| " + " | ".join(header) + " |")
            lines.append("|" + "|".join(["--------"] * len(header)) + "|")
            for tl in policy:
                items = tl.get("items", [])
                freq_disp = {}
                raw_vals = {}
                for it in items:
                    n = (it.get("@name") or "").strip()
                    freq_disp[n] = it.get("freq_display") or it.get("value", "")
                    raw_vals[n] = it.get("value", "")
                cells = [tl.get("@level", ""), tl.get("@temp", "")]
                for bn in base_names:
                    cells.append(freq_disp.get(bn, "—"))
                if show_boost:
                    for cname, is_gpu in clusters:
                        bv = boost_map.get(cname, 0)
                        cells.append(_apply_fps_boost(raw_vals.get(cname, ""), bv, cname, is_gpu, preenv))
                lines.append("| " + " | ".join(cells) + " |")
        lines.append("")

        if mode_d.get("BindCore"):
            lines.append("**Mode 级 BindCore**：")
            for t in mode_d["BindCore"]:
                bin_str = t.get("value_binary", "")
                lines.append("- %s → %s%s" % (t.get("@name", ""), t.get("value", ""), " (0b%s)" % bin_str if bin_str else ""))
            lines.append("")

    # ---------- 五、分析与建议（紧接上一章节，由 agent 调用模型能力补充） ----------
    lines.extend([
        "---", "", "## 五、分析与建议", "",
        "（由 agent 根据报告前四节信息做全面分析，给出修改建议，并列出需用户提供的信息以便进一步分析。）", ""
    ])
    print("\n".join(lines))


def main():
    _ensure_utf8_io()
    parser = argparse.ArgumentParser(description="从 gameperfconfig.xml 提取指定游戏的策略配置")
    parser.add_argument("game", nargs="?", default="和平精英", help="游戏名称或包名（默认：和平精英）；与 --pkg 同用时为包名")
    parser.add_argument("-f", "--config", default="gameperfconfig.xml", help="配置文件路径（默认当前目录 gameperfconfig.xml）")
    parser.add_argument("-o", "--output", choices=["xml", "json", "summary", "report"], default="xml", help="输出格式：xml | json | summary | report")
    parser.add_argument("--pkg", action="store_true", help="按包名匹配：game 参数视为包名（或包名片段）")
    parser.add_argument("-O", "--out-file", default=None, help="将输出写入指定文件（UTF-8 编码），避免终端/重定向乱码")
    parser.add_argument("--preenv", action="store_true", help="同时输出 PreEnv 频率表（便于解释频点）")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_file():
        print(f"错误：配置文件不存在 {config_path}", file=sys.stderr)
        sys.exit(1)

    tree = ET.parse(config_path)
    root = tree.getroot()
    game_el, match_type = find_game_element(root, args.game, match_by_pkg_only=args.pkg)
    if game_el is None:
        print(f"未找到匹配「{args.game}」的游戏配置", file=sys.stderr)
        sys.exit(2)

    # 为 json/summary 的绑核二进制与频率解析需要 PreEnv；--preenv 时额外打印频率表
    preenv = get_preenv(root)
    if args.preenv:
        if args.output == "json":
            import json
            print(json.dumps({"PreEnv": preenv}, ensure_ascii=False, indent=2))
        else:
            print("=== PreEnv 频率表（节选） ===")
            for tag, clusters in preenv.items():
                for name, freqs in clusters.items():
                    print(f"  {tag} {name}: 共 {len(freqs)} 档")
            print()

    if args.output == "xml":
        # 输出 Game 子树为 XML 字符串（无命名空间时保留标签）
        from xml.etree.ElementTree import tostring
        raw = ET.tostring(game_el, encoding="unicode", method="xml")
        print(raw)
    elif args.output == "json":
        import json
        d = game_to_dict(game_el, preenv=preenv)
        print(json.dumps(d, ensure_ascii=False, indent=2))
    elif args.output == "report":
        d = game_to_dict(game_el, preenv=preenv)
        if args.out_file:
            buf = io.StringIO()
            _old = sys.stdout
            sys.stdout = buf
            print_report(d, preenv=preenv)
            sys.stdout = _old
            out_path = Path(args.out_file)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(buf.getvalue(), encoding="utf-8")
            print(f"报告已保存到 {out_path}")
        else:
            print_report(d, preenv=preenv)
    else:
        # summary 文本摘要（含绑核二进制掩码与频率具体值）
        d = game_to_dict(game_el, preenv=preenv)
        print(f"游戏: {d['@name']} (pkg: {d['@pkg']})")
        if d.get("ThermalTempType"):
            print(f"  ThermalTempType: {d['ThermalTempType']}")
        if d.get("FpsAdjustLevel") or d.get("FpsAdjustTime"):
            print(f"  FpsAdjustLevel: {d.get('FpsAdjustLevel','')}, FpsAdjustTime: {d.get('FpsAdjustTime','')}")
        if d.get("JankAdjustLevel") or d.get("JankAdjustTime"):
            print(f"  JankAdjustLevel: {d.get('JankAdjustLevel','')}, JankAdjustTime: {d.get('JankAdjustTime','')}")
        if d.get("BindCore"):
            print("  BindCore:")
            for t in d["BindCore"]:
                bin_str = t.get("value_binary", "")
                print(f"    {t['@name']} -> {t['value']} (0b{bin_str})" if bin_str else f"    {t['@name']} -> {t['value']}")
        if d.get("SceneOpt"):
            print("  SceneOpt:")
            for s in d["SceneOpt"]:
                parts = []
                for it in s["items"]:
                    p = it["value"]
                    if it.get("freq_display"):
                        p = f"{p} ({it['freq_display']})"
                    parts.append(p)
                print(f"    Scene id={s['@id']} time={s['@time']}ms: {parts}")
        if d.get("Mode"):
            print("  Mode:")
            for mode_name, mode_d in d["Mode"].items():
                line = f"    {mode_name}: ThermalSceneCode={mode_d.get('ThermalSceneCode','')}"
                extra_parts = []
                if mode_d.get("FpsAdjustLevel"):
                    extra_parts.append(f"FpsAdjustLevel={mode_d['FpsAdjustLevel']}")
                if mode_d.get("FpsAdjustTime"):
                    extra_parts.append(f"FpsAdjustTime={mode_d['FpsAdjustTime']}")
                if mode_d.get("JankAdjustLevel"):
                    extra_parts.append(f"JankAdjustLevel={mode_d['JankAdjustLevel']}")
                if mode_d.get("JankAdjustTime"):
                    extra_parts.append(f"JankAdjustTime={mode_d['JankAdjustTime']}")
                if extra_parts:
                    line += ", " + ", ".join(extra_parts)
                print(line)
                if mode_d.get("BindCore"):
                    print("      BindCore:")
                    for t in mode_d["BindCore"]:
                        bin_str = t.get("value_binary", "")
                        print(f"        {t['@name']} -> {t['value']} (0b{bin_str})" if bin_str else f"        {t['@name']} -> {t['value']}")
                for op in mode_d.get("PerfHint", []):
                    print(f"      PerfHint opcode {op['@id']} -> {op['value']}")
                for tl in mode_d.get("Policy", []):
                    parts = []
                    for it in tl["items"]:
                        p = it["value"]
                        if it.get("freq_display"):
                            p = f"{p} ({it['freq_display']})"
                        parts.append(p)
                    print(f"      TempLevel level={tl['@level']} temp={tl['@temp']}: {parts}")


if __name__ == "__main__":
    main()
