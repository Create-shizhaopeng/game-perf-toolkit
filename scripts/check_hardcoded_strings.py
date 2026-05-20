#!/usr/bin/env python3
"""Check for remaining hardcoded Chinese strings in module source files.

Scans modules/<name>/src/*.py and toolkit/gui/*.py files, detecting Chinese
characters that are not in comments, docstrings, or import statements.
Excludes strings_*.py files. Returns exit code 0 if clean, 1 if violations found.
"""

import re
import sys
import io
from pathlib import Path

# Ensure UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Chinese character Unicode range
CHINESE_RE = re.compile(r"[一-鿿　-〿＀-￯]")
IMPORT_RE = re.compile(r"^\s*(import |from .+ import )")
COMMENT_RE = re.compile(r"^\s*#")
DOCSTRING_START_RE = re.compile(r'^\s*("""|\'\'\')')

STRINGS_FILE_RE = re.compile(r"strings_.*\.py$")

# Patterns to skip entirely
SKIP_EXTENSIONS = {".pyc", ".pyo", ".pyd"}
SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", "migrations", "res", "data"}


def find_python_files(root: Path) -> list[Path]:
    """Find all .py files under root/src/ and toolkit/gui/."""
    results = []
    if root.name == "src":
        search_root = root
    else:
        search_root = root / "src" if (root / "src").is_dir() else root

    for py_file in sorted(search_root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in py_file.parts):
            continue
        if py_file.suffix in SKIP_EXTENSIONS:
            continue
        if STRINGS_FILE_RE.match(py_file.name):
            continue
        results.append(py_file)
    return results


def has_chinese_in_string_literal(line: str) -> str | None:
    """Check if a line contains Chinese characters inside a string literal.

    Skips comments, imports, and lines that are purely docstring markers.
    Returns the matched Chinese text if found, None otherwise.
    """
    stripped = line.strip()

    # Skip blank lines
    if not stripped:
        return None

    # Skip pure comment lines
    if COMMENT_RE.match(line):
        return None

    # Skip import lines (even if they contain Chinese in module paths)
    if IMPORT_RE.match(line):
        return None

    # Skip docstring-only lines (triple quote markers)
    if DOCSTRING_START_RE.match(stripped) and stripped.endswith(('"""', "'''")):
        return None

    # Check for Chinese characters in the line content
    match = CHINESE_RE.search(stripped)
    if match:
        # Extract surrounding context for the match
        start = max(0, match.start() - 20)
        end = min(len(stripped), match.end() + 20)
        return stripped[start:end]

    return None


def check_file(filepath: Path) -> list[tuple[int, str]]:
    """Check a single file for hardcoded Chinese strings.

    Returns list of (line_number, context) tuples for violations.
    """
    violations = []
    in_docstring = False

    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return violations

    for line_num, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()

        # Track multi-line docstrings
        triple_double = stripped.count('"""')
        triple_single = stripped.count("'''")
        total_triples = triple_double + triple_single

        if in_docstring:
            if total_triples % 2 == 1:
                in_docstring = False
            continue
        elif total_triples > 0 and total_triples % 2 == 1:
            in_docstring = True
            continue
        elif total_triples > 0 and total_triples % 2 == 0:
            # Complete docstring on single line, skip
            continue

        # Skip comment lines
        if COMMENT_RE.match(line):
            continue

        # Skip import lines
        if IMPORT_RE.match(line):
            continue

        # Check for Chinese in string literals
        result = has_chinese_in_string_literal(line)
        if result:
            violations.append((line_num, result))

    return violations


def main() -> int:
    """Main entry point."""
    repo_root = Path(__file__).resolve().parent.parent
    modules_dir = repo_root / "modules"
    toolkit_gui_dir = repo_root / "toolkit" / "gui"

    all_violations: dict[Path, list[tuple[int, str]]] = {}
    files_scanned = 0

    # Scan module src/ directories
    if modules_dir.is_dir():
        for mod_dir in sorted(modules_dir.iterdir()):
            src_dir = mod_dir / "src"
            if not src_dir.is_dir():
                continue
            for py_file in find_python_files(src_dir):
                files_scanned += 1
                violations = check_file(py_file)
                if violations:
                    all_violations[py_file] = violations

    # Scan toolkit/gui/
    if toolkit_gui_dir.is_dir():
        for py_file in find_python_files(toolkit_gui_dir):
            files_scanned += 1
            violations = check_file(py_file)
            if violations:
                all_violations[py_file] = violations

    # Report results
    if all_violations:
        print(f"Found hardcoded Chinese strings in {len(all_violations)} file(s):")
        print()
        for filepath, violations in sorted(all_violations.items()):
            rel_path = filepath.relative_to(repo_root)
            print(f"  {rel_path}:")
            for line_num, context in violations:
                print(f"    L{line_num}: ...{context}...")
            print()
        print(f"Total: {sum(len(v) for v in all_violations.values())} line(s) with Chinese strings")
        print(f"Files scanned: {files_scanned}")
        return 1
    else:
        print(f"No hardcoded Chinese strings found ({files_scanned} files scanned).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
