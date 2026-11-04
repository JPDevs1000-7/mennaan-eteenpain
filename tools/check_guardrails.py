#!/usr/bin/env python3
"""Fails CI when shipped code breaks the app's hard architecture and security rules.

These rules protect users even when code is written by someone who cannot review it
(see CLAUDE.md). Scans the files that get deployed: index.html, migrate.html, css/, js/.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHIPPED = [ROOT / "index.html", ROOT / "migrate.html", *sorted((ROOT / "css").rglob("*.css")),
           *sorted((ROOT / "js").rglob("*.js"))]

RULES = [
    (r"\binnerHTML\b|\bouterHTML\b|insertAdjacentHTML|document\.write", "unsafe HTML injection (use textContent / DOM APIs)"),
    (r"\beval\s*\(|new\s+Function\s*\(", "dynamic code execution"),
    (r"\son[a-z]+\s*=\s*[\"']", "inline event handler attribute"),
    (r"<script(?![^>]*\bsrc=)[^>]*>", "inline <script>"),
    (r"https?://(?!example\.invalid)[a-z0-9.-]+", "external or hard-coded URL (app must be domain agnostic and self-contained)"),
    (r"\bXMLHttpRequest\b|navigator\.sendBeacon|new\s+WebSocket", "network channel other than fetch of same-origin content"),
    (r"document\.cookie", "cookies are not used"),
    (r"\bimport\s*\(\s*['\"]https?:", "remote module import"),
]


def strip_comments(path, text):
    if path.suffix == ".js":
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"(?m)^\s*//.*$", "", text)
    elif path.suffix == ".css":
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    elif path.suffix == ".html":
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return text


def main():
    problems = []
    for path in SHIPPED:
        text = strip_comments(path, path.read_text(encoding="utf-8"))
        for pattern, message in RULES:
            for m in re.finditer(pattern, text, flags=re.I if pattern.startswith(r"\son") else 0):
                line = text.count("\n", 0, m.start()) + 1
                problems.append(f"{path.relative_to(ROOT)}:{line}: {message}: {m.group(0).strip()[:60]}")
    for p in problems:
        print("GUARDRAIL:", p)
    if problems:
        sys.exit(1)
    print(f"Guardrails OK ({len(SHIPPED)} files scanned)")


if __name__ == "__main__":
    main()
