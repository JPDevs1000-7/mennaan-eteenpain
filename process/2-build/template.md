---
feature_id: F-yyyymmdd-short-name
status: draft                 # draft | ready | blocked (waiting on the owner or on a fix to the proposal; see the guide)
created: yyyy-mm-dd
risk_proposed: "[fill]"       # copied from the proposal: low | medium | high
risk_floor: "[fill]"          # from the files changed (guide, Step 4): low | medium | high
---

<!--
Copy this file to process/2-build/output/<feature_id>/build.md and fill it in
order, following process/2-build/guide.md. Replace every [fill]. HTML comments
like this one may stay; they are not shown on GitHub.
-->

## Context for the next session

[fill]
<!-- Two to five sentences: what this feature is, what was built, and where the process stands. If blocked, say why and what would unblock it. -->

## Task list

- [ ] [fill]

<!-- Small steps in order, each naming the files it touches and the criteria (AC-n) it serves. Tick each when done. Every criterion appears in at least one task. -->

## What changed

### For members
[fill]
<!-- What a member will see and be able to do, in plain words. -->

### For developers
[fill]
<!-- Files and modules changed, new modules, spec sections edited, schema version if changed. -->

### Checks
[fill]
<!-- Result of `python tools/run_checks.py` on the latest commit, and the date. -->

## Criterion-to-test map

| Criterion | Test file | Test name |
|---|---|---|
| AC-1 | [fill] | [fill] |

<!-- One row per criterion in the proposal, at least one test each. Each test carries the comment `<feature_id> AC-n` on the line above it. -->

## Differences from the proposal

[fill]
<!-- Anything built differently from the proposal and why, or "none". Only small differences members would not notice belong here; anything bigger blocks the phase (see the guide). -->
