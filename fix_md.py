"""
检测并修复 Markdown 文件编码/格式问题。
修复项：
  1. 确保 UTF-8 编码（带 BOM）
  2. 统一换行符为 CRLF（Windows）
  3. 移除零宽字符等不可见 Unicode
  4. 确保文件末尾有换行符
"""

import os
import sys
import glob

INVISIBLE_CHARS = {
    0x200B: "ZERO WIDTH SPACE",
    0x200C: "ZERO WIDTH NON-JOINER",
    0x200D: "ZERO WIDTH JOINER",
    0xFEFF: "BOM (middle of file)",
    0x00A0: "NO-BREAK SPACE",
    0x2028: "LINE SEPARATOR",
    0x2029: "PARAGRAPH SEPARATOR",
    0x2060: "WORD JOINER",
    0x180E: "MONGOLIAN VOWEL SEPARATOR",
}

BOM = b"\xef\xbb\xbf"


def scan_and_fix(filepath):
    issues = []

    raw = open(filepath, "rb").read()

    has_bom = raw[:3] == BOM
    if has_bom:
        raw = raw[3:]

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        issues.append(f"  UTF-8 解码失败: {e}")
        try:
            text = raw.decode("utf-8", errors="replace")
            issues.append("  已用替换模式修复解码错误")
        except Exception:
            issues.append("  无法修复此文件，跳过")
            return issues, False

    cleaned = []
    removed_count = 0
    for i, ch in enumerate(text):
        code = ord(ch)
        if code in INVISIBLE_CHARS and code != 0x00A0:
            removed_count += 1
            issues.append(f"  移除 U+{code:04X} ({INVISIBLE_CHARS[code]}) 位置 {i}")
        else:
            cleaned.append(ch)
    text = "".join(cleaned)

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    crlf_text = "\r\n".join(lines)
    if not crlf_text.endswith("\r\n"):
        crlf_text += "\r\n"

    new_raw = BOM + crlf_text.encode("utf-8")

    if not has_bom:
        issues.append("  添加 UTF-8 BOM")

    old_raw = open(filepath, "rb").read()
    if new_raw != old_raw:
        open(filepath, "wb").write(new_raw)
        if not issues:
            issues.append("  换行符已统一为 CRLF")
        return issues, True
    else:
        return issues, False


def main():
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
    else:
        target_dir = os.path.dirname(os.path.abspath(__file__))

    md_files = glob.glob(os.path.join(target_dir, "**", "*.md"), recursive=True)

    if not md_files:
        print(f"未找到 .md 文件: {target_dir}")
        return

    print(f"扫描目录: {target_dir}")
    print(f"找到 {len(md_files)} 个 .md 文件\n")

    fixed_count = 0
    for f in sorted(md_files):
        rel = os.path.relpath(f, target_dir)
        issues, changed = scan_and_fix(f)
        if changed:
            fixed_count += 1
            print(f"[已修复] {rel}")
            for iss in issues:
                print(iss)
        else:
            print(f"[正  常] {rel}")
        print()

    print(f"---\n共扫描 {len(md_files)} 个文件，修复 {fixed_count} 个文件")
    if fixed_count > 0:
        print("请在 Cursor 中按 Ctrl+Shift+P → Reload Window 刷新缓存")


if __name__ == "__main__":
    main()
