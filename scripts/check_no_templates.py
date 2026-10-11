"""
scripts/check_no_templates.py
================================
CI guard: fails with exit code 1 if any of the four forbidden template stems
are found anywhere in the repository source files.

Run after removing _fallback_batch / _fallback_question from practical_agent.py
to verify that no template question text remains in the codebase.

Usage
-----
    python scripts/check_no_templates.py            # check whole repo
    python scripts/check_no_templates.py --dir core # check a sub-directory

Exit codes
----------
    0  All clear -- no template strings found.
    1  At least one template string found -- print each location.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# The four canonical template stems that must NOT appear in source files.
FORBIDDEN_STEMS = [
    "In simple terms, what is the main purpose of",
    "Which real-world object is most similar to a",
    "What is the FIRST step when working with a",
    "can hold an unlimited number of elements",
]

# File extensions to scan.
SCAN_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx"}

# Directories / files to skip (virtual env, node_modules, __pycache__, etc.)
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}


def scan(root: Path) -> list[tuple[Path, int, str]]:
    """Return list of (file, line_number, line_content) for each match."""
    this_file = Path(__file__).resolve()
    hits: list[tuple[Path, int, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in SCAN_EXTENSIONS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        # Skip this script itself to avoid false positives from FORBIDDEN_STEMS list
        if path.resolve() == this_file:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for stem in FORBIDDEN_STEMS:
                if stem in line:
                    hits.append((path, lineno, line.rstrip()))
    return hits



def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify no template question stems exist in the codebase."
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Root directory to scan (default: repo root).",
    )
    args = parser.parse_args()

    root = args.dir.resolve()
    print(f"Scanning {root} ...")
    print(f"Forbidden stems ({len(FORBIDDEN_STEMS)}):")
    for stem in FORBIDDEN_STEMS:
        print(f"  - {stem!r}")
    print()

    hits = scan(root)

    if not hits:
        print("OK  No template strings found. All clear.")
        sys.exit(0)

    print(f"FAIL  {len(hits)} occurrence(s) of forbidden template strings found:\n")
    for path, lineno, line in hits:
        rel = path.relative_to(root) if path.is_relative_to(root) else path
        print(f"  {rel}:{lineno}: {line[:120]}")

    print(
        f"\nFix: remove the offending lines and re-run this script.\n"
        f"If these are in check_no_templates.py itself (the FORBIDDEN_STEMS list),\n"
        f"that is a false positive -- the script only reports matches in .py/.js/.jsx files\n"
        f"that are NOT this script itself."
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
