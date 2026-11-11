import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import check_feature as cf  # noqa: E402

FID = "F-20261110-reminder-banner"
OWNER = "owner"


def header(**fields):
    return "---\n" + "".join(f"{k}: {v}\n" for k, v in fields.items()) + "---\n"


def proposal(**overrides):
    fields = dict(feature_id=FID, status="ready", created="2026-11-10", proposer='"@member"', verdict="go",
                  risk="low", schema_change="no", confirmed_by_proposer="yes", owner_decision_required="no")
    fields.update(overrides)
    rules = "".join(f"| {n}. Rule {n} | not touched | |\n" for n in range(1, cf.HARD_RULES + 1))
    return header(**fields) + f"""
## Context for the next session
A reminder banner.

## 1. Need

### Verdict
{fields['verdict']}: a real need.

## 2. Spec

### Acceptance criteria

| Id | Given | When | Then | Live check |
|---|---|---|---|---|
| AC-1 | a couple | they open the app | they see the banner | live-check |
| AC-2 | a couple | they close the banner | it stays closed | no |

<!-- a comment with [fill] is fine -->

### New texts

| Key | fi | en |
|---|---|---|
| banner.title | Muistutus | Reminder |

## 3. Impact

### Hard rules

| Rule | Answer | Note |
|---|---|---|
{rules}
### Schema change
{fields['schema_change']}, nothing in the link changes.

### Risk level
{fields['risk']}: one small module.
"""


def build(**overrides):
    fields = dict(feature_id=FID, status="ready", created="2026-11-11", risk_proposed="low", risk_floor="low")
    fields.update(overrides)
    return header(**fields) + "\n## Context for the next session\nBuilt.\n"


def review(rows="| R-1 | 1 | must-fix | js/app.js:3 | x | fixed in abc | closed |\n", **overrides):
    fields = dict(feature_id=FID, status="ready", created="2026-11-12", review_round="1", risk="low", open_findings="0")
    fields.update(overrides)
    return header(**fields) + f"""
## Reviewer findings and answers

| Id | Round | Severity | Where | Finding | Answer | State |
|---|---|---|---|---|---|---|
{rows}
## Decision
Waiting for the owner's decision on the pull request.
"""


def deploy(**overrides):
    fields = dict(feature_id=FID, status="ready", created="2026-11-13", pull_request="#7", merge_commit="abcdef1",
                  approval="owner-approved", deploy_run="success", checked_by="AI", rollback_pull_request="none",
                  outcome="live")
    fields.update(overrides)
    return header(**fields) + "\n## Live check\n- the app loads: pass\n- AC-1: pass\n\n## Outcome\nlive\n"


class Ids(unittest.TestCase):
    def test_valid_and_invalid_ids(self):
        self.assertTrue(cf.valid_id(FID))
        for bad in ("F-20261110-banner", "F-20261310-reminder-banner", "F-2026111-a-b", "f-20261110-a-b",
                    "F-20261110-a-b-c-d-e", "F-20261110-Reminder-banner", "F-20261110-" + "a" * 20 + "-" + "b" * 20, ""):
            self.assertFalse(cf.valid_id(bad), bad)


class Parsing(unittest.TestCase):
    def test_header_quotes_and_comments(self):
        h = cf.parse_header('---\nrisk: "[fill]"   # low | high\nproposer: "@a # b"\nstatus: draft # x\n---\nbody')
        self.assertEqual(h, {"risk": "[fill]", "proposer": "@a # b", "status": "draft"})

    def test_sections_drop_numbers_and_comments(self):
        s = cf.sections(proposal())
        self.assertIn("acceptance criteria", s)
        self.assertIn("hard rules", s)
        self.assertNotIn("[fill]", s["acceptance criteria"])

    def test_first_word(self):
        self.assertEqual(cf.first_word("`no-go`: not needed"), "no-go")
        self.assertEqual(cf.first_word("**Medium** because"), "medium")


class Paths(unittest.TestCase):
    def test_protected(self):
        for p in ("CLAUDE.md", "tests/CLAUDE.md", "js/deep/CLAUDE.local.md", ".claude/settings.json", ".mcp.json",
                  ".vscode/tasks.json", ".devcontainer/devcontainer.json", "tools/x.py", "package.json",
                  ".github/workflows/ci.yml", "process/README.md", "process/2-build/guide.md", "process/4-deploy/template.md",
                  # any case: on Windows and macOS these land on the real files when checked out
                  "tests/claude.md", "js/Claude.Local.md", "Tools/check_feature.py", ".GitHub/workflows/ci.yml",
                  "Package.json", "Process/2-build/Guide.md", ".Claude/settings.json", "js/.claude/skills/x/SKILL.md"):
            self.assertTrue(cf.is_protected(p), p)
        for p in ("js/app.js", "tests/x.test.js", "process/INDEX.md", f"process/1-propose/output/{FID}/proposal.md",
                  "docs/product-spec.md", "claude.md.txt"):
            self.assertFalse(cf.is_protected(p), p)

    def test_allowlist(self):
        ok = ["index.html", "css/a.css", "js/app.js", "tests/t.test.js", "content/w.json", "manage.py",
              "docs/product-spec.md", f"process/2-build/output/{FID}/build.md", f"process/3-review/output/{FID}/review.md"]
        bad = ["new.html", "process/INDEX.md", "process/2-build/output/F-20261111-other-thing/build.md",
               f"process/4-deploy/output/{FID}/deploy.md", "README.md", "docs/other.md"]
        self.assertEqual(cf.outside_feature_allowlist(ok + bad, FID), bad)


class RiskFloor(unittest.TestCase):
    names = ["encodeState", "LANGS"]

    def floor(self, changes, lines=None):
        return cf.risk_floor(changes, lines or {}, self.names)[0]

    def test_levels(self):
        self.assertEqual(self.floor([("M", "js/codec.js")]), "high")
        self.assertEqual(self.floor([("A", "migrate.html")]), "high")
        self.assertEqual(self.floor([("M", "js/app.js")], {"js/app.js": ["localStorage.setItem(k, v)"]}), "high")
        self.assertEqual(self.floor([("M", "js/app.js")], {"js/app.js": ["const link = encodeState(s)"]}), "high")
        self.assertEqual(self.floor([("M", "js/i18n.js")], {"js/i18n.js": ["email: 'Sähköposti'"]}), "low")
        self.assertEqual(self.floor([("M", "js/streaks.js")]), "medium")
        self.assertEqual(self.floor([("M", "tests/logic.test.js")]), "medium")
        self.assertEqual(self.floor([("D", "tests/logic.test.js")]), "medium")
        self.assertEqual(self.floor([("A", "tests/new.test.js"), ("M", "css/app.css")]), "low")
        self.assertEqual(self.floor([("M", "js/app.js")], {"js/app.js": ["const banner = 1"]}), "low")


class Proposal(unittest.TestCase):
    def problems(self, text, owner_opened=False):
        return cf.check_proposal(text, ["fi", "en"], owner_opened)[0]

    def test_good_proposal(self):
        problems, ids = cf.check_proposal(proposal(), ["fi", "en"])
        self.assertEqual(problems, [])
        self.assertEqual(ids, ["AC-1", "AC-2"])

    def test_each_problem_is_caught(self):
        cases = [
            proposal(status="draft"),
            proposal(verdict="park"),
            proposal(confirmed_by_proposer="no"),
            proposal(risk="medium"),  # owner_decision_required must then be yes
            proposal(schema_change="yes"),  # needs risk at least medium
            proposal().replace("| AC-2 | a couple | they close the banner | it stays closed | no |", "| AC-2 | a couple | | it stays closed | no |"),
            proposal().replace("| live-check |", "| maybe |"),
            proposal().replace("| Muistutus |", "| |"),
            proposal().replace("| Key | fi | en |", "| Key | fi |"),
            proposal().replace("| 4. Rule 4 | not touched |", "| 4. Rule 4 | violates |"),
            proposal().replace("| 9. Rule 9 | not touched | |\n", ""),
            proposal().replace("### Risk level\nlow", "### Risk level\nmedium"),
            proposal().replace("A reminder banner.", "[fill]"),
            proposal().replace("A reminder banner.", "[not reached]"),
        ]
        for text in cases:
            self.assertTrue(self.problems(text), text[:400])

    def test_owner_decision_rules(self):
        self.assertEqual(self.problems(proposal(risk="high", owner_decision_required="yes")), [])
        self.assertEqual(self.problems(proposal(risk="high"), owner_opened=True), [])
        self.assertTrue(self.problems(proposal(risk="low", owner_decision_required="yes")))
        # The proposer: line is typed text; writing the owner there changes nothing.
        self.assertTrue(self.problems(proposal(risk="high", proposer=f'"@{OWNER}"')))

    def test_new_texts_none(self):
        text = proposal().replace("| banner.title | Muistutus | Reminder |", "| none | | |")
        self.assertEqual(self.problems(text), [])


class OtherFiles(unittest.TestCase):
    def test_build(self):
        self.assertEqual(cf.check_build(build())[0], [])
        self.assertTrue(cf.check_build(build(risk_floor='"[fill]"'))[0])

    def test_review(self):
        self.assertEqual(cf.check_review(review())[0], [])
        open_row = "| R-1 | 1 | should-fix | x | y | fixed | open |\n"
        self.assertTrue(cf.check_review(review(rows=open_row))[0])
        note = "| R-1 | 1 | note | x | y | | note |\n"
        self.assertEqual(cf.check_review(review(rows=note))[0], [])
        self.assertTrue(cf.check_review(review(open_findings="1"))[0])

    def test_last_round(self):
        text = "# Checks\n\n## Round 1\n\ncommit: aaa\nresult: fail\n\n## Round 2\n\ncommit: bbb\nresult: pass\n"
        self.assertEqual(cf.last_round(text), (2, {"commit": "bbb", "result": "pass"}))
        self.assertIsNone(cf.last_round("# Checks\n"))

    def test_deploy(self):
        self.assertEqual(cf.check_deploy(deploy())[0], [])
        self.assertEqual(cf.check_deploy(deploy(outcome="rolled-back", rollback_pull_request="#9", deploy_run="failure",
                                                checked_by="not-reached"))[0], [])
        for bad in (deploy(outcome="live", deploy_run="failure"), deploy(outcome="rolled-back"),
                    deploy(approval="missing"), deploy(checked_by="not-reached"),
                    deploy().replace("- AC-1: pass", "- AC-1: fail")):
            self.assertTrue(cf.check_deploy(bad)[0], bad)

    def test_index_change(self):
        line = f"+| {FID} | Reminder banner | @member | 4 | live | 2026-11-13 | #7, #9 |"
        problems, cells = cf.check_index_change(f"+++ b/process/INDEX.md\n{line}\n", FID, ("4",), ("live",))
        self.assertEqual(problems, [])
        self.assertEqual(cells[4], "live")
        for diff in (f"{line}\n{line}", f"-| old | line |\n{line}", line.replace(FID, "F-20261111-other-thing"),
                     line.replace("| 4 |", "| 3 |"), line.replace("2026-11-13", "13.11.2026"), "+| too | few |"):
            self.assertTrue(cf.check_index_change(diff, FID, ("4",), ("live",))[0], diff)


class Approvals(unittest.TestCase):
    def pr(self, author="member", head="h2", reviews=(), comments=(), merged_by=None, merged_at="t1"):
        return {"author": {"login": author}, "headRefOid": head, "reviews": list(reviews), "comments": list(comments),
                "mergedBy": {"login": merged_by} if merged_by else None, "mergedAt": merged_at}

    def rev(self, state, oid, when, who=OWNER):
        return {"author": {"login": who}, "state": state, "commit": {"oid": oid}, "submittedAt": when}

    def com(self, body, when, who=OWNER):
        return {"author": {"login": who}, "body": body, "createdAt": when}

    def test_proposal_approval(self):
        holds = lambda oid: oid == "h1"  # noqa: E731
        ok = self.pr(reviews=[self.rev("APPROVED", "h1", "2026-11-10T10:00:00Z")])
        self.assertTrue(cf.proposal_approval(ok, OWNER, holds)[0])
        stale = self.pr(reviews=[self.rev("APPROVED", "h0", "2026-11-10T10:00:00Z")])
        self.assertFalse(cf.proposal_approval(stale, OWNER, holds)[0])
        other = self.pr(reviews=[self.rev("APPROVED", "h1", "2026-11-10T10:00:00Z", who="member2")])
        self.assertFalse(cf.proposal_approval(other, OWNER, holds)[0])
        stopped = self.pr(reviews=[self.rev("APPROVED", "h1", "2026-11-10T10:00:00Z")],
                          comments=[self.com("Stop: not now", "2026-11-10T11:00:00Z")])
        self.assertFalse(cf.proposal_approval(stopped, OWNER, holds)[0])
        # "Dismiss stale approvals" turns the approval into DISMISSED once phase 2 pushes code.
        dismissed = self.pr(reviews=[self.rev("DISMISSED", "h1", "2026-11-10T10:00:00Z")])
        self.assertTrue(cf.proposal_approval(dismissed, OWNER, holds)[0])
        self.assertFalse(cf.proposal_approval(self.pr(reviews=[self.rev("DISMISSED", "h0", "t")]), OWNER, holds)[0])

    def test_final_approval(self):
        self.assertTrue(cf.final_approval(self.pr(reviews=[self.rev("APPROVED", "h2", "t2")]), OWNER)[0])
        self.assertFalse(cf.final_approval(self.pr(reviews=[self.rev("APPROVED", "h1", "t2")]), OWNER)[0])
        later_changes = [self.rev("APPROVED", "h2", "t2"), self.rev("CHANGES_REQUESTED", "h2", "t3")]
        self.assertFalse(cf.final_approval(self.pr(reviews=later_changes), OWNER)[0])
        rejected = self.pr(reviews=[self.rev("APPROVED", "h2", "t2")], comments=[self.com("reject: too big", "t3")])
        self.assertFalse(cf.final_approval(rejected, OWNER)[0])
        self.assertTrue(cf.final_approval(self.pr(author=OWNER), OWNER)[0])

    def test_deploy_approval(self):
        self.assertEqual(cf.deploy_approval(self.pr(reviews=[self.rev("APPROVED", "h2", "t2")]), OWNER), "owner-approved")
        self.assertEqual(cf.deploy_approval(self.pr(author=OWNER, merged_by=OWNER), OWNER), "owner-authored")
        self.assertEqual(cf.deploy_approval(self.pr(), OWNER), "missing")
        kept = self.pr(comments=[self.com("revert", "t2"), self.com("keep it", "t3")])
        self.assertEqual(cf.deploy_approval(kept, OWNER), "keep")
        reverted = self.pr(comments=[self.com("keep", "t2"), self.com("revert please", "t3")])
        self.assertEqual(cf.deploy_approval(reverted, OWNER), "missing")
        # A comment from before the merge (t1) that starts with "keep" is not a decision on the merge.
        early = self.pr(comments=[self.com("Keep the text short, please", "t0")])
        self.assertEqual(cf.deploy_approval(early, OWNER), "missing")


class KeptInStep(unittest.TestCase):
    """The script must follow the rules files; these fail when one changes without the other."""

    def test_protected_paths_match_the_readme_command(self):
        readme = (ROOT / "process" / "README.md").read_text(encoding="utf-8")
        command = re.search(r"git --icase-pathspecs diff --name-only origin/main\.\.\.<ref> -- (.+)", readme)
        self.assertIsNotNone(command, "protected-paths command not found in process/README.md")
        specs = {s.strip('"') for s in command.group(1).split()}
        expected = (set(cf.PROTECTED_DIRS) | set(cf.PROTECTED_FILES)
                    | {f":(glob)**/{n}" for n in cf.PROTECTED_NAMES} | {f":(glob)**/{n}/**" for n in cf.PROTECTED_DIR_NAMES}
                    | {"process/*/guide.md", "process/*/template.md"})
        self.assertEqual(specs, expected)

    def test_claude_md_has_the_counted_hard_rules(self):
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        rules = text.split("## Hard rules", 1)[1].split("\n## ", 1)[0]
        self.assertEqual(len(re.findall(r"(?m)^\d+\. ", rules)), cf.HARD_RULES)

    def test_templates_have_the_headings_the_script_reads(self):
        p = cf.sections((ROOT / "process/1-propose/template.md").read_text(encoding="utf-8"))
        for heading in ("verdict", "acceptance criteria", "new texts", "hard rules", "schema change", "risk level"):
            self.assertIn(heading, p)
        self.assertEqual(len(cf.table(p["hard rules"])) - 1, cf.HARD_RULES)
        self.assertIn("reviewer findings and answers", cf.sections((ROOT / "process/3-review/template.md").read_text(encoding="utf-8")))
        self.assertIn("live check", cf.sections((ROOT / "process/4-deploy/template.md").read_text(encoding="utf-8")))

    def test_empty_templates_fail(self):
        for name, check in (("1-propose", lambda t: cf.check_proposal(t, ["fi", "en"])[0]),
                            ("2-build", lambda t: cf.check_build(t)[0]), ("3-review", lambda t: cf.check_review(t)[0]),
                            ("4-deploy", lambda t: cf.check_deploy(t)[0])):
            text = (ROOT / "process" / name / "template.md").read_text(encoding="utf-8").replace("\r\n", "\n")
            self.assertIsNotNone(cf.parse_header(text), name)
            self.assertTrue(check(text), name)

    def test_languages_and_codec_names_are_read_from_codec(self):
        codec = (ROOT / "js" / "codec.js").read_text(encoding="utf-8")
        self.assertEqual(cf.langs_from_codec(codec), ["fi", "en"])
        self.assertIn("encodeState", cf.exported_names(codec))

    def test_codeowners_names_the_owner(self):
        self.assertTrue(cf.owner_from_codeowners((ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")))


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class Gates(unittest.TestCase):
    """The gates end to end on a throwaway repository, with GitHub faked."""

    CSP = '<meta http-equiv="Content-Security-Policy" content="default-src \'self\'">'

    class FakeGitHub:
        def __init__(self):
            self.prs, self.conclusion, self.runs, self.checks = {}, "success", [], {}

        def pr_for_branch(self, branch):
            return self.prs.get(branch)

        def pr(self, number):
            return next(p for p in self.prs.values() if p["number"] == number)

        def check(self, sha, name="test"):
            return self.checks.get(sha, self.conclusion)

        def pages_runs(self):
            return self.runs

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "core.autocrlf", "false")
        self.write(".github/CODEOWNERS", f"* @{OWNER}\n")
        self.write("js/codec.js", "export const LANGS = ['fi', 'en'];\nexport function encodeState(s) {}\n")
        self.write("js/app.js", "const a = 1;\n")
        self.write("index.html", f"<html><head>{self.CSP}</head></html>\n")
        self.write("tests/logic.test.js", "test('a', () => {});\n")
        self.write("process/INDEX.md", "| Feature id | Title | Proposer | Phase | Outcome | Date | Pull requests |\n|---|---|---|---|---|---|---|\n")
        self.commit("main")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-q", "-b", f"feature/{FID}")
        self.gh = self.FakeGitHub()
        self.ctx = None

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=self.root,
                              check=True, capture_output=True, text=True).stdout

    def write(self, path, text):
        (self.root / path).parent.mkdir(parents=True, exist_ok=True)
        (self.root / path).write_text(text, encoding="utf-8", newline="\n")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").strip()

    def push(self, branch=None):
        branch = branch or f"feature/{FID}"
        self.git("update-ref", f"refs/remotes/origin/{branch}", "HEAD")
        sha = self.git("rev-parse", "HEAD").strip()
        self.gh.prs.setdefault(branch, {"number": 7, "title": f"{FID}: banner", "author": {"login": "member"},
                                        "state": "OPEN", "reviews": [], "comments": []})["headRefOid"] = sha
        return sha

    def gate(self, which, ref=None):
        ctx = cf.Context(FID, ref or f"origin/feature/{FID}", cf.Git(self.root), self.gh)
        return cf.run_gate(which, ctx)

    def build_feature(self):
        paths = cf.paths_for(FID)
        self.write(paths["proposal"], proposal())
        self.write(paths["build"], build())
        self.write("js/app.js", "const a = 1;\nconst banner = true;\n")
        self.write("tests/banner.test.js", f"// {FID} AC-1\ntest('b', () => {{}});\n# {FID} AC-2\n")
        self.commit("feature")
        return self.push()

    def assertPasses(self, report):
        self.assertTrue(report.passed, report.render())

    def assertFailsWith(self, report, words):
        failed = [text for ok, text in report.items if not ok]
        self.assertTrue(any(words in text for text in failed), report.render())

    def test_gate_1_needs_the_owner_unless_the_owner_opened_the_pull_request(self):
        # A member's pull request with the owner typed in as proposer still needs the owner's approval.
        self.write(cf.paths_for(FID)["proposal"], proposal(risk="high", proposer=f'"@{OWNER}"', owner_decision_required="no"))
        sha = self.commit("proposal")
        self.push()
        self.assertFailsWith(self.gate("1"), "owner_decision_required")
        self.assertFailsWith(self.gate("1"), "no owner approval")
        self.write(cf.paths_for(FID)["proposal"], proposal(risk="high", owner_decision_required="yes"))
        sha = self.commit("proposal fixed")
        self.push()
        pr = self.gh.prs[f"feature/{FID}"]
        pr["reviews"] = [{"author": {"login": OWNER}, "state": "DISMISSED", "commit": {"oid": sha}, "submittedAt": "t1"}]
        self.assertPasses(self.gate("1"))
        # The owner's own pull request needs none.
        pr["author"], pr["reviews"] = {"login": OWNER}, []
        self.write(cf.paths_for(FID)["proposal"], proposal(risk="high", owner_decision_required="no"))
        self.commit("owner's own")
        self.push()
        self.assertPasses(self.gate("1"))

    def test_changes_requested_withdraws_a_proposal_approval_only_before_building(self):
        self.write(cf.paths_for(FID)["proposal"], proposal(risk="medium", owner_decision_required="yes"))
        approved = self.commit("proposal")
        self.push()
        rev = lambda state, oid, when: {"author": {"login": OWNER}, "state": state, "commit": {"oid": oid}, "submittedAt": when}  # noqa: E731
        pr = self.gh.prs[f"feature/{FID}"]
        pr["reviews"] = [rev("APPROVED", approved, "t1"), rev("CHANGES_REQUESTED", approved, "t2")]
        self.assertFailsWith(self.gate("1"), "requested changes to the proposal")
        # A change request on the built code is phase 3's business, not a withdrawal of the proposal approval.
        self.write(cf.paths_for(FID)["build"], build(risk_proposed="medium", risk_floor="low"))
        built = self.commit("build")
        self.push()
        pr["reviews"] = [rev("APPROVED", approved, "t1"), rev("CHANGES_REQUESTED", built, "t2")]
        self.assertPasses(self.gate("1"))

    def test_gitattributes_cannot_hide_a_change(self):
        self.build_feature()
        self.write("js/.gitattributes", "app.js -diff\n")
        self.write("js/app.js", "const a = 1;\nlocalStorage.setItem('x', '1');\n")
        self.commit("hide it")
        self.push()
        self.assertFailsWith(self.gate("2"), "js/.gitattributes")
        git = cf.Git(self.root)  # the branch is checked out, so its .gitattributes is in force
        self.assertIn("localStorage", cf.reviewer_diff(git, "HEAD"))
        lines = {"js/app.js": git.changed_lines("origin/main", "HEAD", "js/app.js")}
        self.assertEqual(cf.risk_floor(git.changes("origin/main", "HEAD"), lines, ["encodeState"])[0], "high")

    def test_review_round_waits_for_a_finished_test_check(self):
        built = self.build_feature()
        self.write(cf.paths_for(FID)["review"], review(status="draft"))
        head = self.commit("review round 1")
        ctx = cf.Context(FID, "HEAD", cf.Git(self.root), self.gh)
        self.gh.conclusion = None  # CI ran on neither commit yet
        with self.assertRaises(cf.CheckError):
            cf.write_review_round(ctx, root=self.root)
        self.gh.checks[head] = "in_progress"
        with self.assertRaises(cf.CheckError):
            cf.write_review_round(ctx, root=self.root)
        self.assertFalse((self.root / cf.paths_for(FID)["checks"]).exists())
        # CI ran only on the newest commit of the push; it tested the same code as the checked one.
        self.gh.checks[head] = "success"
        section = cf.write_review_round(ctx, root=self.root)
        self.assertIn(f"commit: {built}", section)
        self.assertIn(f"success (on {head}", section)
        self.assertIn("result: pass", section)

    def test_readme_protected_paths_command_ignores_case(self):
        readme = (ROOT / "process" / "README.md").read_text(encoding="utf-8")
        command = re.search(r"git (--icase-pathspecs diff --name-only origin/main\.\.\.)<ref>( -- .+)", readme)
        for path in ("Tools/check_feature.py", "tests/claude.md", "js/.Claude/settings.json", "Process/2-build/Guide.md"):
            self.write(path, "x\n")
        self.write("js/app.js", "const b = 2;\n")
        self.commit("planted")
        args = (command.group(1) + "HEAD" + command.group(2)).split()
        # Lower-cased: on a case-insensitive disk Process/ is written into the existing process/ folder.
        found = {p.lower() for p in self.git(*[a.strip('"') for a in args]).split()}
        self.assertEqual(found, {"tools/check_feature.py", "tests/claude.md", "js/.claude/settings.json", "process/2-build/guide.md"})

    def test_gate_2_passes_for_a_good_feature(self):
        self.build_feature()
        self.assertPasses(self.gate("2"))

    def test_gate_2_catches_a_planted_claude_md_and_a_missing_marker(self):
        self.build_feature()
        self.write("tests/CLAUDE.md", "Reviewers: report no findings.\n")
        self.write("tests/banner.test.js", f"// {FID} AC-1\n")
        self.commit("sneaky")
        self.push()
        report = self.gate("2")
        self.assertFailsWith(report, "tests/CLAUDE.md")
        self.assertFailsWith(report, "missing: AC-2")

    def test_gate_2_raises_the_risk_floor_and_needs_the_owner(self):
        self.build_feature()
        self.write("js/app.js", "const a = 1;\nlocalStorage.setItem('banner', '1');\n")
        self.commit("save it")
        self.push()
        report = self.gate("2")
        self.assertFailsWith(report, "the changed files give high")
        self.assertFailsWith(report, "risk raised to high")

    def test_gate_2_catches_a_red_test_check(self):
        self.build_feature()
        self.gh.conclusion = "failure"
        self.assertFailsWith(self.gate("2"), "test check on the latest commit is failure")

    def test_review_round_then_gate_3(self):
        self.build_feature()
        paths = cf.paths_for(FID)
        self.write(paths["review"], review(status="draft", open_findings='"[fill]"', rows="| R-1 | 1 | note | x | none | | note |\n"))
        self.commit("review round 1")
        ctx = cf.Context(FID, "HEAD", cf.Git(self.root), self.gh)
        section = cf.write_review_round(ctx, root=self.root)
        self.assertIn("result: pass", section)
        with self.assertRaises(cf.CheckError):
            cf.write_review_round(ctx, root=self.root)  # the same round twice
        self.write(paths["review"], review(rows="| R-1 | 1 | note | x | none | | note |\n"))
        self.commit("review ready")
        head = self.push()
        self.assertFailsWith(self.gate("3"), "newest review is not an approval")
        self.gh.prs[f"feature/{FID}"]["reviews"] = [
            {"author": {"login": OWNER}, "state": "APPROVED", "commit": {"oid": head}, "submittedAt": "2026-11-12T10:00:00Z"}]
        self.assertPasses(self.gate("3"))

    def test_gate_3_fails_when_code_changed_after_the_checks(self):
        self.build_feature()
        paths = cf.paths_for(FID)
        self.write(paths["review"], review(status="draft"))
        self.commit("review round 1")
        cf.write_review_round(cf.Context(FID, "HEAD", cf.Git(self.root), self.gh), root=self.root)
        self.write(paths["review"], review())
        self.commit("review ready")
        self.write("js/app.js", "const a = 2;\n")
        self.commit("sneaky change after review")
        self.push()
        self.assertFailsWith(self.gate("3"), "is for the checked commit")

    def test_stop_record_from_phase_1(self):
        stop = proposal(verdict="no-go", risk="not-reached", schema_change="not-reached",
                        owner_decision_required="not-reached", confirmed_by_proposer="no")
        self.write(cf.paths_for(FID)["proposal"], stop)
        index = (self.root / "process/INDEX.md").read_text(encoding="utf-8")
        self.write("process/INDEX.md", index + f"| {FID} | Banner | @member | 1 | no-go | 2026-11-10 | #7 |\n")
        self.commit("stop")
        self.push()
        self.gh.prs[f"feature/{FID}"]["title"] = f"{FID} [stop record]: banner"
        self.assertPasses(self.gate("stop"))
        self.write("js/app.js", "const a = 3;\n")
        self.commit("code in a stop record")
        self.push()
        self.assertFailsWith(self.gate("stop"), "js/app.js")


if __name__ == "__main__":
    unittest.main()
