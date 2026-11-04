# Daily Together — rules for working in this repo

Product source of truth: `docs/product-spec.md`. Read it before changing behaviour. If a change contradicts the spec, update the spec in the same change and say so.

## Hard rules (CI enforces what it can)
1. **Stateless, no backend.** No servers, databases, accounts, analytics, cookies or third-party requests. User state lives in localStorage and in the Magic State Link only.
2. **No end-user PII leaves the device.** The optional email goes only inside Self-Backup links; Partner Share links never contain it. It is kept in the browser's localStorage **only if the user ticks "Remember my email on this device"** (off by default; unticking deletes it). Nothing is ever sent anywhere.
3. **Domain agnostic.** Never hard-code a domain; build links from `location.origin + location.pathname`.
4. **State link is versioned.** The payload layout in `js/codec.js` is pinned by tests. Any change to it requires a new `SCHEMA_VERSION`, a decoder that still reads old versions, and new test vectors.
5. **Untrusted input.** Link data and content are untrusted. Build DOM with `textContent`/`createElement`; never `innerHTML`, `eval`, inline handlers or inline scripts (`tools/check_guardrails.py`). Keep the CSP in `index.html` as strict as it is.
6. **Accessibility (WCAG AAA, senior friendly).** 18px+ text, 48x48px minimum targets, 7:1 contrast, visible focus, no meaning by colour alone (icon plus label), ARIA live announcements for changes.
7. **Every UI string and every piece of content exists in every language** (`js/i18n.js` and `content/`, both tested and validated). That includes each week's `theme`, which is an object with one text per language. Finnish is the first-class language: prompts and themes are written in Finnish first, then translated.
8. **Plain static files, no build step.** Vanilla ES modules. No npm dependencies. Output must work on GitHub Pages and Cloudflare Pages unchanged.
9. **Content is validated.** `python manage.py validate` must pass; placeholders (`TODO`) never ship.

## Layout
- `index.html`, `css/`, `js/` — the app. Pure logic modules (`dates`, `codec`, `streaks`, `timeline`) have no DOM and are unit tested; `app.js` is the only DOM code.
- `content/` — weekly prompt JSON plus `manifest.json` (rebuilt by `manage.py`).
- `manage.py` — admin CLI. `migrate.html` + `js/migrate.js` — old-domain redirect (UC-4).
- `tests/` — `npm test` (Node) and `python -I -m unittest discover -s tests -p "test_*.py"`; both are run by `tools/run_checks.py`.
- `tools/check_guardrails.py` — static security/architecture checks, including the CSP. `tools/run_checks.py` — runs every check in one command.
- `.github/workflows/` — `ci.yml` (PRs and main), `pages.yml` (deploy on main after tests pass).

## Before you finish any change
Run `python tools/run_checks.py` (JS tests, Python tests, content validation, guardrails; CI and deploy run exactly this). It must pass. Never skip hooks or weaken a test to make it pass; fix the cause.

## Decisions already made (do not reopen without the owner)
On Time window = until end of the day after release; Day 1 = day of first launch; day boundaries = device-local midnight; MVP backup = copy to clipboard only; email is remembered on the device only if the user opts in; hosting = GitHub (Pages), keep portable to Cloudflare; stack = vanilla JS.
