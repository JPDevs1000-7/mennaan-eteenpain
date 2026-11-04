#!/usr/bin/env python3
"""Runs every check that must pass before a change can be merged or deployed.

One place defines the checks; CI (ci.yml), deploy (pages.yml) and people all run:
    python tools/run_checks.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def steps():
    npm = shutil.which("npm")
    return [
        ("JavaScript tests", [npm or "npm", "test"]),
        ("Python tests", [sys.executable, "-I", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]),
        ("Content validation", [sys.executable, "manage.py", "validate"]),
        ("Guardrails", [sys.executable, "tools/check_guardrails.py"]),
    ]


def main():
    failed = []
    for name, cmd in steps():
        print(f"\n=== {name} ===", flush=True)
        try:
            code = subprocess.run(cmd, cwd=ROOT).returncode
        except FileNotFoundError:
            print(f"Could not run {cmd[0]!r}: is it installed?")
            code = 1
        if code != 0:
            failed.append(name)
    print("\n=== Summary ===")
    for name, _ in steps():
        print(("FAIL  " if name in failed else "ok    ") + name)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
