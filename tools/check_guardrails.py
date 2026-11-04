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

I = re.I
# (pattern, message, flags). Function( is case-sensitive: the lowercase keyword `function(` is everywhere.
RULES = [
    (r"\binnerHTML\b|\bouterHTML\b|insertAdjacentHTML|document\.write", "unsafe HTML injection (use textContent / DOM APIs)", I),
    (r"\beval\s*\(|\bFunction\s*\(", "dynamic code execution", 0),
    (r"\bset(?:Timeout|Interval)\s*\(\s*[\"'`]", "string passed to setTimeout/setInterval", I),
    (r"\son[a-z]+\s*=\s*[\"']", "inline event handler attribute", I),
    (r"<script(?![^>]*\bsrc\s*=)[^>]*>", "inline <script>", I),
    (r"https?://(?!example\.invalid)[a-z0-9.-]+", "external or hard-coded URL (app must be domain agnostic and self-contained)", I),
    (r"(?:\b(?:src|href|action|poster|srcset)\s*=\s*[\"']?|url\(\s*[\"']?|@import\s+[\"']?)//", "protocol-relative URL", I),
    (r"\bXMLHttpRequest\b|navigator\.sendBeacon|new\s+WebSocket|new\s+EventSource", "network channel other than fetch of same-origin content", I),
    (r"document\.cookie", "cookies are not used", I),
    (r"\bimport\s*\(\s*['\"`]\s*(?:https?:)?//", "remote module import", I),
]

CSP_RE = re.compile(r"<meta[^>]+http-equiv\s*=\s*[\"']Content-Security-Policy[\"'][^>]*>", I)
CSP_CONTENT_RE = re.compile(r"content\s*=\s*\"([^\"]*)\"|content\s*=\s*'([^']*)'", I)
CSP_FORBIDDEN = ("'unsafe-inline'", "'unsafe-eval'", "'unsafe-hashes'", "data:", "blob:", "http:", "https:", "*", "ws:", "wss:")
CSP_REQUIRED_SELF = ("default-src", "script-src")


def blank(match):
    """Replace a comment with spaces, keeping newlines so reported line numbers stay right."""
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_comments(suffix, text):
    # Comments are only stripped when they START a line, so a "/*" or "//" inside a string
    # literal can never hide real code from the scan.
    if suffix == ".js":
        text = re.sub(r"(?ms)^[ \t]*/\*.*?\*/", blank, text)
        text = re.sub(r"(?m)^[ \t]*//.*$", blank, text)
    elif suffix == ".css":
        text = re.sub(r"(?ms)^[ \t]*/\*.*?\*/", blank, text)
    elif suffix == ".html":
        text = re.sub(r"(?s)<!--.*?-->", blank, text)
    return text


def check_csp(name, text):
    """Every HTML page must ship a strict, self-only Content-Security-Policy."""
    meta = CSP_RE.search(text)
    if not meta:
        return [f"{name}: missing Content-Security-Policy <meta> tag"]
    m = CSP_CONTENT_RE.search(meta.group(0))
    policy = (m.group(1) or m.group(2) or "") if m else ""
    directives = {}
    for part in policy.split(";"):
        tokens = part.split()
        if tokens:
            directives[tokens[0].lower()] = [t.lower() for t in tokens[1:]]
    problems = []
    for needed in CSP_REQUIRED_SELF:
        if needed not in directives and not (needed == "script-src" and "default-src" in directives):
            problems.append(f"{name}: CSP lacks {needed}")
    for directive, sources in directives.items():
        if directive == "default-src" or directive == "script-src":
            if directive == "default-src" and sources not in (["'self'"], ["'none'"]):
                problems.append(f"{name}: CSP default-src must be exactly 'self' or 'none', found {sources}")
            if directive == "script-src" and sources not in (["'self'"], ["'none'"]):
                problems.append(f"{name}: CSP script-src must be exactly 'self' or 'none', found {sources}")
        for source in sources:
            if source in CSP_FORBIDDEN:
                problems.append(f"{name}: CSP {directive} allows {source}")
    return problems


def scan_text(name, suffix, text):
    """Return a list of problem strings for one file's text."""
    problems = []
    cleaned = strip_comments(suffix, text)
    for pattern, message, flags in RULES:
        for m in re.finditer(pattern, cleaned, flags=flags):
            line = cleaned.count("\n", 0, m.start()) + 1
            problems.append(f"{name}:{line}: {message}: {m.group(0).strip()[:60]}")
    if suffix == ".html":
        problems += check_csp(name, text)
    return problems


def main():
    problems = []
    for path in SHIPPED:
        problems += scan_text(str(path.relative_to(ROOT)), path.suffix, path.read_text(encoding="utf-8"))
    for p in problems:
        print("GUARDRAIL:", p)
    if problems:
        sys.exit(1)
    print(f"Guardrails OK ({len(SHIPPED)} files scanned)")


if __name__ == "__main__":
    main()
