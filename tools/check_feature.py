#!/usr/bin/env python3
"""Checks one feature against the gates of the feature process (process/README.md).

Everything is read through git (`git show <ref>:<path>`) and the GitHub CLI `gh`, never
from the working tree. So a branch can be checked without checking it out, and the
branch's own code is never run. Rules the checks need (the approver, the languages, the
protected paths) are always read from `origin/main`, never from the branch being checked.

    python tools/check_feature.py gate 1 <feature-id>      phase 1 gate (proposal)
    python tools/check_feature.py gate 2 <feature-id>      phase 2 gate (build), includes gate 1
    python tools/check_feature.py gate 3 <feature-id>      phase 3 gate (review), includes gates 1 and 2
    python tools/check_feature.py gate 4 <feature-id>      phase 4 gate (deploy record on deploy/<id>)
    python tools/check_feature.py gate stop <feature-id>   a stop record (stop/<id>, or feature/<id> in phase 1)
    python tools/check_feature.py gate rollback <feature-id>   a rollback pull request (revert/<id>)
    python tools/check_feature.py review <feature-id>      phase 3: add this round's section to checks.md
    python tools/check_feature.py diff <feature-id>        phase 3: the reviewer's diff (output/ folders left out)

Options: --ref REF checks another ref than the default branch; --no-fetch skips `git fetch`.
Exit code 0: every check passed. 1: at least one check failed. 2: the command could not run.
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = "origin/main"
LEVELS = ("low", "medium", "high")
PHASE_DIRS = ("1-propose", "2-build", "3-review", "4-deploy")
HARD_RULES = 9  # the numbered hard rules in CLAUDE.md (a test keeps this in step)
FILL = "[fill]"
NOT_REACHED = "[not reached]"

# The protected paths of README section 7. A test keeps them in step with the README's command.
PROTECTED_DIRS = ("tools/", ".github/", ".claude/", ".vscode/", ".devcontainer/")
PROTECTED_FILES = ("package.json", "process/README.md", ".mcp.json")
PROTECTED_NAMES = ("CLAUDE.md", "CLAUDE.local.md")  # in any folder
PROTECTED_RULES = re.compile(r"process/.+/(?:guide|template)\.md")  # git's "process/*/guide.md" also crosses "/"

# What a feature branch may change (phase 2 guide, "Write only"), besides its own output folders.
FEATURE_FILES = ("index.html", "migrate.html", "manage.py", "docs/product-spec.md")
FEATURE_DIRS = ("css/", "js/", "tests/", "content/")

# Risk floor (phase 2 guide, Step 4).
HIGH_FILES = ("js/codec.js", "js/migrate.js", "migrate.html")
MEDIUM_FILES = ("manage.py", "js/dates.js", "js/streaks.js", "js/timeline.js")
SENSITIVE_WORDS = ("localstorage", "sessionstorage", "email", "clipboard", "location")

INDEX_COLUMNS = 7
CSP_RE = re.compile(r"<meta[^>]+Content-Security-Policy[^>]*>", re.I)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
ID_RE = re.compile(r"F-(\d{8})-([a-z0-9]+(?:-[a-z0-9]+){1,3})")


class CheckError(Exception):
    """A command could not run (git or gh failed, a branch is missing)."""


# ---------------------------------------------------------------- pure helpers

def valid_id(fid):
    m = ID_RE.fullmatch(fid or "")
    if not m or len(m.group(2)) > 30:
        return False
    try:
        datetime.datetime.strptime(m.group(1), "%Y%m%d")
    except ValueError:
        return False
    return True


def paths_for(fid):
    return {
        "proposal": f"process/1-propose/output/{fid}/proposal.md",
        "build": f"process/2-build/output/{fid}/build.md",
        "review": f"process/3-review/output/{fid}/review.md",
        "checks": f"process/3-review/output/{fid}/checks.md",
        "deploy": f"process/4-deploy/output/{fid}/deploy.md",
    }


def own_folders(fid, phases=PHASE_DIRS):
    return tuple(f"process/{d}/output/{fid}/" for d in phases)


def is_protected(path):
    return (path in PROTECTED_FILES or path.startswith(PROTECTED_DIRS)
            or path.rsplit("/", 1)[-1] in PROTECTED_NAMES or bool(PROTECTED_RULES.fullmatch(path)))


def outside_feature_allowlist(paths, fid):
    own = own_folders(fid, PHASE_DIRS[:3])
    return [p for p in paths if not (p in FEATURE_FILES or p.startswith(FEATURE_DIRS + own))]


def strip_comments(text):
    return COMMENT_RE.sub("", text)


def parse_header(text):
    """The `---` header of a handoff file as {key: value}; quotes and `# comments` removed."""
    m = re.match(r"﻿?---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    header = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        value = value.strip()
        if value[:1] in ("'", '"'):
            end = value.find(value[0], 1)
            value = value[1:end] if end > 0 else value[1:]
        else:
            value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
        header[key.strip()] = value
    return header


def body_of(text):
    return strip_comments(re.sub(r"\A﻿?---\n.*?\n---\n", "", text, count=1, flags=re.S))


def sections(text):
    """{heading: text} for every ## and ### heading, lowercased, without a leading "1." number."""
    out, current = {}, None
    for line in body_of(text).splitlines():
        m = re.match(r"#{2,3}\s+(?:\d+\.\s+)?(.*?)\s*$", line)
        if m:
            current = m.group(1).lower()
            out[current] = []
        elif current is not None:
            out[current].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def table(text):
    """Rows of the first Markdown table in text, header row first, separator row dropped."""
    rows = []
    for line in (text or "").splitlines():
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                rows.append(cells)
        elif rows:
            break
    return rows


def plain(cell):
    return (cell or "").strip().strip("`*").strip().lower()


def first_word(text):
    m = re.match(r"[\W_]*([a-z][a-z-]*)", (text or "").lower())
    return m.group(1) if m else ""


def need(problems, header, key, allowed, file):
    value = header.get(key)
    if value is None or value.lower() not in [a.lower() for a in allowed]:
        problems.append(f"{file}: {key} is {value!r}, must be {' or '.join(allowed)}")


def owner_from_codeowners(text):
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) > 1 and parts[0] == "*":
            return parts[1].lstrip("@").lower()
    return None


def langs_from_codec(text):
    m = re.search(r"export const LANGS\s*=\s*\[([^\]]*)\]", text or "")
    return re.findall(r"['\"]([a-z]{2})['\"]", m.group(1)) if m else []


def exported_names(text):
    return re.findall(r"(?m)^export\s+(?:async\s+)?(?:function\*?|const|let|class)\s+([A-Za-z_$][\w$]*)", text or "")


def markers(test_files, fid):
    """{AC id: ["path:line"]} for every `// <id> AC-n` or `# <id> AC-n` comment in the test files."""
    found = {}
    pattern = re.compile(r"^\s*(?://|#)\s*" + re.escape(fid) + r"\s+(AC-\d+)\b")
    for path, text in sorted(test_files.items()):
        for n, line in enumerate(text.splitlines(), 1):
            m = pattern.match(line)
            if m:
                found.setdefault(m.group(1), []).append(f"{path}:{n}")
    return found


def risk_floor(changes, changed_lines, codec_names):
    """The minimum risk level from the changed files: (level, [reasons])."""
    names = re.compile(r"\b(?:" + "|".join(map(re.escape, codec_names)) + r")\b") if codec_names else None
    high, medium = [], []
    for status, path in changes:
        if path in HIGH_FILES:
            high.append(f"{path} changed")
        elif path in MEDIUM_FILES:
            medium.append(f"{path} changed")
        elif path.startswith("js/") and path != "js/i18n.js":
            for line in changed_lines.get(path, []):
                if any(w in line.lower() for w in SENSITIVE_WORDS) or (names and names.search(line)):
                    high.append(f"{path}: a changed line touches saved data, the email, the link or the codec")
                    break
        if path.startswith("tests/") and status[:1] in ("M", "D"):
            medium.append(f"{path}: an existing test changed or was deleted")
    level = "high" if high else "medium" if medium else "low"
    return level, high + medium


def check_proposal(text, langs, owner, stop=False):
    """Problems with proposal.md for gate 1 (or for a stop record), and its criterion ids."""
    h = parse_header(text)
    if h is None:
        return ["proposal.md: no header"], []
    p, f = [], "proposal.md"
    if FILL in strip_comments(text):
        p.append(f"{f}: [fill] left")
    need(p, h, "status", ("ready",), f)
    if stop:
        need(p, h, "verdict", ("park", "no-go", "go"), f)
        return p, []
    if NOT_REACHED in body_of(text):
        p.append(f"{f}: a section says [not reached]")
    need(p, h, "verdict", ("go",), f)
    need(p, h, "confirmed_by_proposer", ("yes",), f)
    need(p, h, "risk", LEVELS, f)
    need(p, h, "schema_change", ("yes", "no"), f)
    if h.get("schema_change") == "yes" and h.get("risk") == "low":
        p.append(f"{f}: schema_change yes needs risk medium or high")
    proposer = h.get("proposer", "").lstrip("@").lower()
    expected = "no" if proposer and proposer == owner else ("yes" if h.get("risk") in ("medium", "high") else "no")
    if h.get("owner_decision_required") != expected:
        p.append(f"{f}: owner_decision_required is {h.get('owner_decision_required')!r}, expected {expected!r}")
    sec = sections(text)
    for heading, key in (("verdict", "verdict"), ("risk level", "risk"), ("schema change", "schema_change")):
        if first_word(sec.get(heading)) != h.get(key):
            p.append(f"{f}: section \"{heading}\" must start with {h.get(key)!r}, as in the header")

    ids = []
    rows = table(sec.get("acceptance criteria"))
    if len(rows) < 2:
        p.append(f"{f}: no acceptance criteria")
    for r in rows[1:]:
        if len(r) < 5 or not re.fullmatch(r"AC-\d+", r[0]) or not all(r[1:5]):
            p.append(f"{f}: criterion row {r[0]!r} needs an id AC-n, Given, When, Then and Live check")
            continue
        if plain(r[4]) not in ("live-check", "no"):
            p.append(f"{f}: {r[0]} Live check must be live-check or no")
        if r[0] in ids:
            p.append(f"{f}: {r[0]} appears twice")
        ids.append(r[0])

    rows = table(sec.get("new texts"))
    columns = [plain(c) for c in rows[0]] if rows else []
    if not rows:
        p.append(f"{f}: no New texts table")
    else:
        for lang in langs:
            if lang not in columns:
                p.append(f"{f}: New texts has no column for {lang}")
        if not (len(rows) == 2 and plain(rows[1][0]) == "none"):
            for r in rows[1:]:
                if len(r) < len(columns) or not all(r[:len(columns)]):
                    p.append(f"{f}: text {r[0]!r} is missing a language")

    answers = {}
    for r in table(sec.get("hard rules"))[1:]:
        m = re.match(r"(\d+)\.", r[0])
        if m:
            answers[int(m.group(1))] = plain(r[1]) if len(r) > 1 else ""
    for n in range(1, HARD_RULES + 1):
        if answers.get(n) not in ("complies", "not touched"):
            p.append(f"{f}: hard rule {n} is {answers.get(n)!r}, must be complies or not touched")
    return p, ids


def check_build(text):
    h = parse_header(text)
    if h is None:
        return ["build.md: no header"], {}
    p, f = [], "build.md"
    if FILL in strip_comments(text):
        p.append(f"{f}: [fill] left")
    need(p, h, "status", ("ready",), f)
    need(p, h, "risk_proposed", LEVELS, f)
    need(p, h, "risk_floor", LEVELS, f)
    return p, h


def findings(text):
    return table(sections(text).get("reviewer findings and answers"))[1:]


def open_findings(rows):
    return [r for r in rows if len(r) >= 7 and plain(r[2]) in ("must-fix", "should-fix") and plain(r[6]) != "closed"]


def check_review(text):
    h = parse_header(text)
    if h is None:
        return ["review.md: no header"], {}
    p, f = [], "review.md"
    if FILL in strip_comments(text):
        p.append(f"{f}: [fill] left")
    need(p, h, "status", ("ready",), f)
    need(p, h, "risk", LEVELS, f)
    still_open = open_findings(findings(text))
    if still_open:
        p.append(f"{f}: findings not closed: {', '.join(r[0] for r in still_open)}")
    if h.get("open_findings") != "0":
        p.append(f"{f}: open_findings is {h.get('open_findings')!r}, must be 0")
    return p, h


def last_round(text):
    """(round number, {commit, date, written_by, result}) of the last section in checks.md."""
    parts = re.split(r"(?m)^## Round (\d+)[ \t]*$", text or "")
    if len(parts) < 3:
        return None
    return int(parts[-2]), dict(re.findall(r"(?m)^(commit|date|written_by|result):[ \t]*(\S+)", parts[-1]))


def check_deploy(text):
    h = parse_header(text)
    if h is None:
        return ["deploy.md: no header"], {}
    p, f = [], "deploy.md"
    if FILL in strip_comments(text):
        p.append(f"{f}: [fill] left")
    need(p, h, "status", ("ready",), f)
    need(p, h, "approval", ("owner-approved", "owner-authored", "keep"), f)
    need(p, h, "deploy_run", ("success", "failure"), f)
    need(p, h, "checked_by", ("AI", "owner", "not-reached"), f)
    need(p, h, "outcome", ("live", "rolled-back"), f)
    rollback = h.get("rollback_pull_request", "")
    if not (rollback == "none" or re.fullmatch(r"#\d+", rollback)):
        p.append(f"{f}: rollback_pull_request must be none or #n")
    live_check = sections(text).get("live check", "")
    if h.get("outcome") == "live":
        if h.get("deploy_run") != "success":
            p.append(f"{f}: outcome live needs deploy_run success")
        if h.get("checked_by", "").lower() not in ("ai", "owner"):
            p.append(f"{f}: outcome live needs checked_by AI or owner")
        if rollback != "none":
            p.append(f"{f}: outcome live with a rollback pull request")
        if re.search(r"\bfail\b", live_check, re.I):
            p.append(f"{f}: outcome live, but the live check has a failed item")
    if h.get("outcome") == "rolled-back" and rollback == "none":
        p.append(f"{f}: outcome rolled-back needs rollback_pull_request")
    if NOT_REACHED in body_of(text) and h.get("checked_by") != "not-reached":
        p.append(f"{f}: [not reached] is only allowed when the live check was never reached")
    return p, h


def check_index_change(diff_text, fid, phases, outcomes):
    """Problems with the INDEX.md change of a stop or deploy record, and the added line's cells."""
    lines = diff_text.splitlines()
    added = [l[1:] for l in lines if l.startswith("+") and not l.startswith("+++") and l[1:].strip()]
    removed = [l for l in lines if l.startswith("-") and not l.startswith("---")]
    p, f = [], "process/INDEX.md"
    if removed:
        p.append(f"{f}: lines removed or changed; a feature only adds its own line")
    if len(added) != 1:
        return p + [f"{f}: {len(added)} lines added, expected exactly this feature's one line"], None
    cells = [c.strip().strip("`") for c in added[0].strip().strip("|").split("|")]
    if len(cells) != INDEX_COLUMNS:
        return p + [f"{f}: the line has {len(cells)} columns, expected {INDEX_COLUMNS}"], None
    if cells[0] != fid:
        p.append(f"{f}: the line is for {cells[0]!r}, not {fid}")
    if cells[3] not in phases:
        p.append(f"{f}: phase {cells[3]!r}, expected {' or '.join(phases)}")
    if cells[4] not in outcomes:
        p.append(f"{f}: outcome {cells[4]!r}, expected {' or '.join(outcomes)}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[5]):
        p.append(f"{f}: date {cells[5]!r} is not yyyy-mm-dd")
    return p, cells


# ---------------------------------------------------------------- owner decisions (from `gh pr view` JSON)

def login(item):
    return ((item or {}).get("author") or {}).get("login", "").lower()


def owner_reviews(pr, owner):
    return sorted((r for r in pr.get("reviews") or [] if login(r) == owner), key=lambda r: r.get("submittedAt") or "")


def owner_comments(pr, owner, words):
    return sorted((c for c in pr.get("comments") or [] if login(c) == owner and first_word(c.get("body")) in words),
                  key=lambda c: c.get("createdAt") or "")


def review_oid(review):
    return (review.get("commit") or {}).get("oid", "")


def proposal_approval(pr, owner, holds_current_proposal):
    """The owner approved a commit that already holds the current proposal.md, and did not say stop since."""
    approvals = [r for r in owner_reviews(pr, owner)
                 if r.get("state") == "APPROVED" and holds_current_proposal(review_oid(r))]
    if not approvals:
        return False, "no owner approval on a commit that holds the current proposal.md"
    when = approvals[-1].get("submittedAt") or ""
    if any((c.get("createdAt") or "") > when for c in owner_comments(pr, owner, ("stop",))):
        return False, "the owner commented stop after approving"
    return True, "the owner approved the current proposal"


def final_approval(pr, owner):
    """Phase 3: the owner's newest review is an approval on the latest commit."""
    if login(pr) == owner:
        return True, "the owner's own pull request: no approval needed"
    decisions = [r for r in owner_reviews(pr, owner) if r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED")]
    if not decisions or decisions[-1].get("state") != "APPROVED":
        return False, "the owner's newest review is not an approval"
    if review_oid(decisions[-1]) != pr.get("headRefOid"):
        return False, "the owner's approval is on an older commit, not the latest one"
    when = decisions[-1].get("submittedAt") or ""
    if any((c.get("createdAt") or "") > when for c in owner_comments(pr, owner, ("changes", "reject"))):
        return False, "the owner commented changes or reject after approving"
    return True, "the owner approved the latest commit"


def deploy_approval(pr, owner):
    """Phase 4: how the merged pull request counts as approved (owner-approved, owner-authored, keep or missing)."""
    if login(pr) != owner and final_approval(pr, owner)[0]:
        return "owner-approved"
    if login(pr) == owner and ((pr.get("mergedBy") or {}).get("login", "").lower() == owner):
        return "owner-authored"
    decisions = owner_comments(pr, owner, ("keep", "revert"))
    if decisions and first_word(decisions[-1].get("body")) == "keep":
        return "keep"
    return "missing"


# ---------------------------------------------------------------- git and GitHub

class Git:
    def __init__(self, root=ROOT):
        self.root = root

    def run(self, *args, ok=(0,)):
        try:
            r = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        except FileNotFoundError:
            raise CheckError("git is not installed")
        if r.returncode not in ok:
            raise CheckError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
        return r

    def out(self, *args):
        return self.run(*args).stdout

    def exists(self, ref):
        return self.run("rev-parse", "--verify", "--quiet", ref + "^{commit}", ok=(0, 1)).returncode == 0

    def sha(self, ref):
        return self.out("rev-parse", ref + "^{commit}").strip()

    def show(self, ref, path):
        r = self.run("show", f"{ref}:{path}", ok=(0, 128))
        return r.stdout.replace("\r\n", "\n") if r.returncode == 0 else None

    def changes(self, base, ref, *spec):
        out = self.out("diff", "--name-status", "--no-renames", f"{base}...{ref}", "--", *spec)
        return [tuple(line.split("\t", 1)) for line in out.splitlines() if "\t" in line]

    def diff(self, *args):
        return self.out("diff", *args).replace("\r\n", "\n")

    def changed_lines(self, base, ref, path):
        text = self.diff("-U0", f"{base}...{ref}", "--", path)
        return [l[1:] for l in text.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---"))]

    def files(self, ref, prefix):
        return self.out("ls-tree", "-r", "--name-only", ref, "--", prefix).splitlines()

    def same(self, a, b, path):
        return self.run("diff", "--quiet", a, b, "--", path, ok=(0, 1, 128)).returncode == 0

    def is_ancestor(self, a, b):
        return self.run("merge-base", "--is-ancestor", a, b, ok=(0, 1, 128)).returncode == 0

    def last_commit_outside(self, ref, folder):
        return self.out("log", "-1", "--format=%H", ref, "--", ".", f":(exclude){folder}**").strip()


PR_FIELDS = "number,title,author,state,isDraft,headRefOid,mergedAt,mergedBy,mergeCommit,reviews,comments"


class GitHub:
    def __init__(self, root=ROOT):
        self.root = root

    def json(self, *args):
        try:
            r = subprocess.run(["gh", *args], cwd=self.root, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        except FileNotFoundError:
            raise CheckError("the GitHub CLI gh is not installed")
        if r.returncode != 0:
            raise CheckError(f"gh {' '.join(args[:3])} failed: {r.stderr.strip()}")
        return json.loads(r.stdout or "null")

    def pr_for_branch(self, branch):
        rows = self.json("pr", "list", "--state", "all", "--head", branch, "--json", "number,state", "--limit", "10")
        if not rows:
            return None
        rows.sort(key=lambda r: (r["state"] != "OPEN", -r["number"]))
        return self.pr(rows[0]["number"])

    def pr(self, number):
        return self.json("pr", "view", str(number), "--json", PR_FIELDS)

    def check(self, sha, name="test"):
        data = self.json("api", f"repos/{{owner}}/{{repo}}/commits/{sha}/check-runs")
        runs = sorted((r for r in data.get("check_runs", []) if r.get("name") == name),
                      key=lambda r: r.get("started_at") or "")
        return (runs[-1].get("conclusion") or runs[-1].get("status")) if runs else None

    def pages_runs(self):
        return self.json("run", "list", "--workflow", "pages.yml", "--branch", "main", "--limit", "100",
                         "--json", "databaseId,headSha,status,conclusion,url")


# ---------------------------------------------------------------- gates

class Report:
    def __init__(self, title):
        self.title, self.items = title, []

    def check(self, ok, text):
        self.items.append((bool(ok), text))
        return bool(ok)

    def problems(self, problems, ok_text):
        for p in problems:
            self.check(False, p)
        if not problems:
            self.check(True, ok_text)
        return not problems

    @property
    def passed(self):
        return all(ok for ok, _ in self.items)

    def render(self):
        lines = [self.title]
        lines += [("  ok    " if ok else "  FAIL  ") + text for ok, text in self.items]
        failed = sum(1 for ok, _ in self.items if not ok)
        lines.append(f"Result: {'PASS' if not failed else 'FAIL'} ({failed} of {len(self.items)} checks failed)")
        return "\n".join(lines)


class Context:
    def __init__(self, fid, ref, git, gh, main=MAIN):
        self.fid, self.ref, self.git, self.gh, self.main = fid, ref, git, gh, main
        self.paths = paths_for(fid)
        self._cache = {}

    def _once(self, key, make):
        if key not in self._cache:
            self._cache[key] = make()
        return self._cache[key]

    @property
    def owner(self):
        owner = self._once("owner", lambda: owner_from_codeowners(self.git.show(self.main, ".github/CODEOWNERS")))
        if not owner:
            raise CheckError("no approver found in .github/CODEOWNERS on main")
        return owner

    @property
    def langs(self):
        return self._once("langs", lambda: langs_from_codec(self.git.show(self.main, "js/codec.js")))

    @property
    def codec_names(self):
        return self._once("codec", lambda: exported_names(self.git.show(self.main, "js/codec.js")))

    @property
    def pr(self):
        return self._once("pr", lambda: self.gh.pr_for_branch(f"feature/{self.fid}"))

    def changes(self, ref=None):
        return self.git.changes(self.main, ref or self.ref)

    def text(self, key, ref=None):
        return self.git.show(ref or self.ref, self.paths[key])


def csp_lines(git, ref):
    return {page: CSP_RE.findall(git.show(ref, page) or "") for page in ("index.html", "migrate.html")}


def gate_1(ctx, r):
    text = ctx.text("proposal")
    if not r.check(text is not None, f"{ctx.paths['proposal']} exists"):
        return None
    problems, ids = check_proposal(text, ctx.langs, ctx.owner)
    r.problems(problems, "proposal.md is complete: ready, go, confirmed, criteria, texts and hard rules filled")
    h = parse_header(text) or {}
    pr = ctx.pr
    if not r.check(pr is not None, f"feature pull request for feature/{ctx.fid} found"):
        return ids
    if h.get("owner_decision_required") == "yes" and login(pr) != ctx.owner:
        r.check(*(proposal_approval(pr, ctx.owner, lambda oid: ctx.git.same(oid, ctx.ref, ctx.paths["proposal"]))))
    else:
        r.check(True, "the owner's approval of the proposal is not required")
    return ids


def gate_2(ctx, r):
    ids = gate_1(ctx, r)
    text = ctx.text("build")
    if not r.check(text is not None, f"{ctx.paths['build']} exists"):
        return None
    problems, h = check_build(text)
    r.problems(problems, "build.md is complete and ready")

    changes = ctx.changes()
    paths = [p for _, p in changes]
    protected = [p for p in paths if is_protected(p)]
    r.check(not protected, "no protected path changed" + (f": {', '.join(protected)}" if protected else ""))
    outside = [p for p in outside_feature_allowlist(paths, ctx.fid) if p not in protected]
    r.check(not outside, "nothing outside the feature allowlist changed" + (f": {', '.join(outside)}" if outside else ""))
    r.check(csp_lines(ctx.git, ctx.main) == csp_lines(ctx.git, ctx.ref), "the Content-Security-Policy is unchanged")

    tests = {p: ctx.git.show(ctx.ref, p) or "" for p in ctx.git.files(ctx.ref, "tests/")}
    found = markers(tests, ctx.fid)
    missing = [i for i in ids or [] if i not in found]
    unknown = [i for i in found if ids is not None and i not in ids]
    r.check(not missing, "every criterion has a marked test" + (f"; missing: {', '.join(missing)}" if missing else ""))
    r.check(not unknown, "every test marker names a criterion in the proposal" + (f"; unknown: {', '.join(unknown)}" if unknown else ""))

    js = {p: ctx.git.changed_lines(ctx.main, ctx.ref, p) for p in paths if p.startswith("js/")}
    floor, reasons = risk_floor(changes, js, ctx.codec_names)
    why = f" ({'; '.join(reasons)})" if reasons else ""
    r.check(h.get("risk_floor") == floor, f"risk_floor in build.md is {h.get('risk_floor')!r}; the changed files give {floor}{why}")

    proposal = parse_header(ctx.text("proposal") or "") or {}
    raised = floor in LEVELS and proposal.get("risk") in LEVELS and LEVELS.index(floor) > LEVELS.index(proposal["risk"])
    pr = ctx.pr
    if raised and proposal.get("owner_decision_required") != "yes" and pr and login(pr) != ctx.owner:
        ok, why = proposal_approval(pr, ctx.owner, lambda oid: ctx.git.same(oid, ctx.ref, ctx.paths["proposal"]))
        r.check(ok, f"risk raised to {floor}: {why}")
    conclusion = ctx.gh.check(ctx.git.sha(ctx.ref))
    r.check(conclusion == "success", f"the test check on the latest commit is {conclusion or 'missing'}")
    return floor


def gate_3(ctx, r):
    floor = gate_2(ctx, r)
    text = ctx.text("review")
    if not r.check(text is not None, f"{ctx.paths['review']} exists"):
        return
    problems, h = check_review(text)
    r.problems(problems, "review.md is ready with every finding closed")
    proposal = parse_header(ctx.text("proposal") or "") or {}
    wanted = max((x for x in (proposal.get("risk"), floor) if x in LEVELS), key=LEVELS.index, default=None)
    if wanted and h.get("risk") in LEVELS:
        r.check(LEVELS.index(h["risk"]) >= LEVELS.index(wanted), f"review.md risk {h['risk']!r} is at least {wanted}")

    checked = ctx.git.last_commit_outside(ctx.ref, own_folders(ctx.fid, ("3-review",))[0])
    last = last_round(ctx.text("checks") or "")
    if r.check(last is not None, "checks.md has a round"):
        n, fields = last
        r.check(fields.get("commit") == checked, f"checks.md round {n} is for the checked commit {checked[:9]}")
        r.check(fields.get("result") == "pass", f"checks.md round {n} result is {fields.get('result', 'missing')}")
    pr = ctx.pr
    if pr:
        r.check(*(final_approval(pr, ctx.owner)))


def merged_and_deployed(ctx, merge_commit):
    """The pages.yml run that published merge_commit: its own, or a later successful one that contains it."""
    runs = ctx.gh.pages_runs()
    own = [x for x in runs if x.get("headSha") == merge_commit]
    if any(x.get("conclusion") == "success" for x in own):
        return True, "the deploy run for the merge commit succeeded"
    later = [x for x in runs if x.get("conclusion") == "success" and x.get("headSha")
             and ctx.git.is_ancestor(merge_commit, x["headSha"])]
    if later:
        return True, f"a later deploy run that contains the merge commit succeeded ({later[0].get('url', '')})"
    return False, "no successful deploy run published the merge commit"


def feature_code_files(git, merge_commit):
    out = git.out("diff", "--name-only", f"{merge_commit}^1", merge_commit, "--", ".", ":(exclude)process/")
    return sorted(out.split())


def gate_4(ctx, r):
    text = ctx.text("deploy")
    if not r.check(text is not None, f"{ctx.paths['deploy']} exists on {ctx.ref}"):
        return
    problems, h = check_deploy(text)
    r.problems(problems, "deploy.md is complete and consistent")
    pr = ctx.pr
    if not r.check(pr is not None and pr.get("state") == "MERGED", "the feature pull request is merged"):
        return
    merge = (pr.get("mergeCommit") or {}).get("oid", "")
    r.check(h.get("pull_request") == f"#{pr['number']}", f"pull_request is #{pr['number']}")
    r.check(len(h.get("merge_commit", "")) >= 7 and merge.startswith(h.get("merge_commit", "-")), f"merge_commit is {merge[:9]}")
    approval = deploy_approval(pr, ctx.owner)
    r.check(approval != "missing", f"the merge counts as approved ({approval})")
    r.check(h.get("approval") == approval, f"approval in deploy.md is {h.get('approval')!r}, GitHub shows {approval}")
    ok, why = merged_and_deployed(ctx, merge)
    if h.get("outcome") == "live":
        r.check(ok, why)
    if h.get("deploy_run") == "success":
        r.check(ok, "deploy_run success matches GitHub")

    rollback = h.get("rollback_pull_request", "none")
    if re.fullmatch(r"#\d+", rollback):
        rb = ctx.gh.pr(int(rollback[1:]))
        if r.check(rb.get("state") == "MERGED", f"rollback pull request {rollback} is merged"):
            rb_merge = (rb.get("mergeCommit") or {}).get("oid", "")
            r.check(feature_code_files(ctx.git, rb_merge) == feature_code_files(ctx.git, merge),
                    "the rollback changed exactly the feature's files outside process/")
            r.check(*(merged_and_deployed(ctx, rb_merge)))

    paths = [p for _, p in ctx.changes()]
    own = own_folders(ctx.fid, ("4-deploy",))[0]
    extra = [p for p in paths if not (p.startswith(own) or p == "process/INDEX.md")]
    r.check(not extra, "the deploy record changes only its own folder and INDEX.md" + (f": {', '.join(extra)}" if extra else ""))
    index_problems, cells = check_index_change(ctx.git.diff("-U0", f"{ctx.main}...{ctx.ref}", "--", "process/INDEX.md"),
                                               ctx.fid, ("4",), ("live", "rolled-back"))
    r.problems(index_problems, "INDEX.md gets this feature's one line")
    if cells:
        r.check(cells[4] == h.get("outcome"), f"the INDEX.md outcome matches deploy.md ({h.get('outcome')})")


def gate_stop(ctx, r):
    paths = [p for _, p in ctx.changes()]
    allowed = own_folders(ctx.fid, ("1-propose", "3-review"))
    extra = [p for p in paths if not (p.startswith(allowed) or p == "process/INDEX.md")]
    r.check(not extra, "the stop record holds only handoff files and INDEX.md" + (f": {', '.join(extra)}" if extra else ""))
    text = ctx.text("proposal")
    if not r.check(text is not None, f"{ctx.paths['proposal']} exists"):
        return
    problems, _ = check_proposal(text, ctx.langs, ctx.owner, stop=True)
    r.problems(problems, "proposal.md is ready with nothing left to fill")
    verdict = (parse_header(text) or {}).get("verdict")
    review = ctx.text("review")
    index_problems, cells = check_index_change(ctx.git.diff("-U0", f"{ctx.main}...{ctx.ref}", "--", "process/INDEX.md"),
                                               ctx.fid, ("1", "2", "3"), ("park", "no-go", "rejected"))
    r.problems(index_problems, "INDEX.md gets this feature's one line")
    if cells:
        if cells[4] == "rejected":
            r.check(review is not None and (parse_header(review) or {}).get("status") == "ready",
                    "a rejected feature's stop record holds its ready review.md")
        else:
            r.check(cells[4] == verdict, f"the INDEX.md outcome {cells[4]!r} matches the verdict {verdict!r}")
    if review is not None:
        r.check(FILL not in strip_comments(review), "review.md has nothing left to fill")
    branch = ctx.ref.split("/", 1)[1] if ctx.ref.startswith("origin/") else ctx.ref
    pr = ctx.gh.pr_for_branch(branch)
    r.check(pr is not None and "[stop record]" in pr.get("title", ""), f"the pull request from {branch} is titled as a stop record")


def gate_rollback(ctx, r):
    pr = ctx.pr
    if not r.check(pr is not None and pr.get("state") == "MERGED", "the feature pull request is merged"):
        return
    merge = (pr.get("mergeCommit") or {}).get("oid", "")
    expected = feature_code_files(ctx.git, merge)
    actual = sorted(p for _, p in ctx.changes())
    r.check(actual == expected, "the rollback changes exactly the feature's files outside process/"
            + ("" if actual == expected else f" (expected {expected}, found {actual})"))
    conclusion = ctx.gh.check(ctx.git.sha(ctx.ref))
    r.check(conclusion == "success", f"the test check on the rollback is {conclusion or 'missing'}")


GATES = {"1": gate_1, "2": gate_2, "3": gate_3, "4": gate_4, "stop": gate_stop, "rollback": gate_rollback}


def default_ref(git, which, fid):
    if which == "4":
        return f"origin/deploy/{fid}"
    if which == "rollback":
        return f"origin/revert/{fid}"
    if which == "stop" and git.exists(f"origin/stop/{fid}"):
        return f"origin/stop/{fid}"
    return f"origin/feature/{fid}"


def run_gate(which, ctx):
    r = Report(f"Gate {which} for {ctx.fid} ({ctx.ref} at {ctx.git.sha(ctx.ref)[:9]})")
    GATES[which](ctx, r)
    return r


# ---------------------------------------------------------------- phase 3 helpers

def reviewer_diff(git, ref, main=MAIN):
    return git.diff(f"{main}...{ref}", "--", ".", ":(exclude)process/*/output/**")


def review_round(ctx, today=None):
    """The checks.md section for this round; ctx.ref is the checked-out feature branch (HEAD)."""
    review = parse_header(ctx.text("review") or "") or {}
    n = review.get("review_round", "")
    if not n.isdigit():
        raise CheckError(f"{ctx.paths['review']} has no review_round; create it from the template first")
    checked = ctx.git.last_commit_outside(ctx.ref, own_folders(ctx.fid, ("3-review",))[0])
    paths = [p for _, p in ctx.changes()]
    protected = [p for p in paths if is_protected(p)]
    outside = [p for p in outside_feature_allowlist(paths, ctx.fid) if p not in protected]
    csp_main, csp_branch = csp_lines(ctx.git, ctx.main), csp_lines(ctx.git, ctx.ref)
    conclusion = ctx.gh.check(checked)
    _, ids = check_proposal(ctx.text("proposal") or "", ctx.langs, ctx.owner)
    found = markers({p: ctx.git.show(ctx.ref, p) or "" for p in ctx.git.files(ctx.ref, "tests/")}, ctx.fid)
    missing = [i for i in ids if i not in found]
    passed = not protected and not outside and csp_main == csp_branch and conclusion == "success" and not missing

    def block(lines):
        return "```text\n" + ("\n".join(lines) if lines else "(none)") + "\n```"

    csp = [f"{page} on main:   {' '.join(csp_main[page]) or '(none)'}\n{page} on branch: {' '.join(csp_branch[page]) or '(none)'}"
           for page in csp_main]
    marker_lines = [f"{ac}: {', '.join(where)}" for ac, where in sorted(found.items())] + [f"{ac}: NO TEST" for ac in missing]
    return "\n".join([
        f"## Round {n}", "",
        f"commit: {checked}",
        f"date: {today or datetime.date.today().isoformat()}",
        "written_by: tools/check_feature.py",
        f"result: {'pass' if passed else 'fail'}", "",
        "### Protected paths changed (must be empty)", block(protected), "",
        "### Files outside the feature allowlist (must be empty)", block(outside), "",
        "### Content-Security-Policy (must be identical)", block(csp) + ("" if csp_main == csp_branch else "\nCHANGED"), "",
        "### The test check on the checked commit", block([conclusion or "missing"]), "",
        "### Changed files and lines", block(ctx.git.diff("--stat", f"{ctx.main}...{ctx.ref}").rstrip().splitlines()), "",
        "### Criterion markers", block(marker_lines), "",
    ])


def write_review_round(ctx, root=ROOT):
    branch = ctx.git.out("rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch != f"feature/{ctx.fid}":
        raise CheckError(f"check out feature/{ctx.fid} first (now on {branch})")
    section = review_round(ctx)
    path = root / ctx.paths["checks"]
    existing = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else f"# Checks for {ctx.fid}\n\n"
    n = re.match(r"## Round (\d+)", section).group(1)
    if re.search(rf"(?m)^## Round {n}[ \t]*$", existing):
        raise CheckError(f"checks.md already has round {n}; earlier rounds are never edited (raise review_round first)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(existing.rstrip("\n") + "\n\n" + section, encoding="utf-8", newline="\n")
    return section


# ---------------------------------------------------------------- command line

def main(argv=None, git=None, gh=None):
    ap = argparse.ArgumentParser(description="Check a feature against the feature process gates.")
    sub = ap.add_subparsers(dest="command", required=True)
    g = sub.add_parser("gate", help="check a phase's gate")
    g.add_argument("which", choices=list(GATES))
    for p in (g, sub.add_parser("review", help="add this round to checks.md"), sub.add_parser("diff", help="print the reviewer's diff")):
        p.add_argument("feature_id")
        p.add_argument("--no-fetch", action="store_true", help="do not run git fetch first")
        p.add_argument("--ref", help="the ref to check (default: the feature's branch on origin)")
    args = ap.parse_args(argv)
    if not valid_id(args.feature_id):
        print(f"Not a feature id: {args.feature_id!r} (expected F-yyyymmdd-two-to-four-words)")
        return 2
    git, gh = git or Git(), gh or GitHub()
    try:
        if not args.no_fetch:
            git.run("fetch", "--quiet", "origin")
        if args.command == "gate":
            ref = args.ref or default_ref(git, args.which, args.feature_id)
            if not git.exists(ref):
                raise CheckError(f"{ref} does not exist")
            report = run_gate(args.which, Context(args.feature_id, ref, git, gh))
            print(report.render())
            return 0 if report.passed else 1
        if args.command == "review":
            print(write_review_round(Context(args.feature_id, args.ref or "HEAD", git, gh)))
            print(f"Added to {paths_for(args.feature_id)['checks']}")
            return 0
        sys.stdout.write(reviewer_diff(git, args.ref or f"origin/feature/{args.feature_id}"))
        return 0
    except CheckError as e:
        print(f"Could not check: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
