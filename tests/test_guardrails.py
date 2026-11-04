import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import check_guardrails as g  # noqa: E402

GOOD_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; "
            "connect-src 'self'; base-uri 'none'")


def page(csp=GOOD_CSP, body=""):
    meta = f'<meta http-equiv="Content-Security-Policy" content="{csp}">' if csp is not None else ""
    return f"<!doctype html><html><head>{meta}</head><body>{body}</body></html>"


def js_problems(code):
    return g.scan_text("x.js", ".js", code)


class Rules(unittest.TestCase):
    def test_flags_each_dangerous_pattern(self):
        cases = {
            "el.innerHTML = x": ".js",
            "el.OUTERHTML = x": ".js",
            "eval('1')": ".js",
            "Function('return 1')()": ".js",
            "new Function('return 1')": ".js",
            "setTimeout('alert(1)', 5)": ".js",
            "fetch('https://evil.test/x')": ".js",
            "fetch('HTTPS://EVIL.TEST/x')": ".js",
            "document.cookie = 'a=b'": ".js",
            "new WebSocket('wss://x.test')": ".js",
            "import('https://x.test/m.js')": ".js",
            "import('//x.test/m.js')": ".js",
            "navigator.sendBeacon('/x')": ".js",
            "@import url(//fonts.example/css);": ".css",
            "a { background: url(//cdn.example/x.png) }": ".css",
        }
        for code, suffix in cases.items():
            self.assertTrue(g.scan_text("f" + suffix, suffix, code), f"not caught: {code}")

    def test_flags_html_patterns(self):
        for body in ('<button onclick="x()">', '<BUTTON ONCLICK="x()">', "<script>alert(1)</script>",
                     "<SCRIPT>alert(1)</SCRIPT>", '<img src="//cdn.example/x.png">', '<a href="HTTPS://evil.test">'):
            self.assertTrue(g.scan_text("p.html", ".html", page(body=body)), f"not caught: {body}")

    def test_allows_normal_code(self):
        ok = "const f = function () { return 1; };\nexport function g() {}\nel.textContent = 'x';\nfetch('content/a.json');"
        self.assertEqual(js_problems(ok), [])
        self.assertEqual(g.scan_text("p.html", ".html", page(body='<script type="module" src="js/app.js"></script>')), [])

    def test_comments_are_ignored_but_line_numbers_stay_correct(self):
        code = "/* a\n   multi-line comment mentioning innerHTML\n*/\n// eval(x)\nel.innerHTML = y;\n"
        problems = js_problems(code)
        self.assertEqual(len(problems), 1)
        self.assertIn("x.js:5:", problems[0])

    def test_string_containing_comment_start_cannot_hide_code(self):
        code = "const s = \"/*\";\nel.innerHTML = x;\nconst t = \"*/\";\n"
        self.assertTrue(any("innerHTML" in p for p in js_problems(code)))

    def test_html_comment_keeps_line_numbers(self):
        text = "<!--\n a\n b\n-->\n<script>x()</script>"
        problems = g.scan_text("p.html", ".html", page(body="") + text)
        self.assertTrue(any("inline <script>" in p for p in problems))


class Csp(unittest.TestCase):
    def csp_problems(self, csp):
        return g.check_csp("p.html", page(csp))

    def test_good_csp_passes(self):
        self.assertEqual(self.csp_problems(GOOD_CSP), [])

    def test_missing_meta_fails(self):
        self.assertTrue(g.check_csp("p.html", page(csp=None)))

    def test_weakened_policies_fail(self):
        for bad in (
            GOOD_CSP.replace("script-src 'self'", "script-src 'self' 'unsafe-inline'"),
            GOOD_CSP.replace("connect-src 'self'", "connect-src *"),
            GOOD_CSP.replace("default-src 'self'", "default-src *"),
            GOOD_CSP.replace("script-src 'self'", "script-src 'self' https://cdn.example"),
            GOOD_CSP.replace("img-src 'self'", "img-src 'self' data:"),
            "style-src 'self'",
        ):
            self.assertTrue(self.csp_problems(bad), f"not caught: {bad}")

    def test_migrate_page_style_policy_passes(self):
        self.assertEqual(self.csp_problems("default-src 'none'; script-src 'self'; style-src 'self'; base-uri 'none'"), [])


class Repository(unittest.TestCase):
    def test_shipped_files_pass(self):
        result = subprocess.run([sys.executable, "-I", str(ROOT / "tools" / "check_guardrails.py")],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
