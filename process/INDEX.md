# Feature index

One line for every feature that has **finished** the process: it went live, was rolled back, or stopped.

## What this list is for

- **Duplicate checks.** Before a new proposal goes ahead, phase 1 searches this list (and `docs/product-spec.md`) for anything similar. Stopped ideas stay here on purpose, so an idea that was parked or turned down is found and named instead of being proposed again from scratch.
- **History at a glance.** Anyone can see what has been proposed, what happened to it and why, without reading every handoff file. The reasons and details are in each feature's own files in `process/<phase>/output/<feature id>/`.

Features **still in progress** are not listed here. They live only on their own `feature/<id>` branch and draft pull request until they finish, so check the open pull requests too: `gh pr list --state open --search "head:feature/"`.

## Rules for this file

- **One line per feature.** The session that finishes a feature adds its line: in a stop record (phases 1 to 3), or in phase 4's follow-up pull request. If a later outcome changes it (for example `rolled-back` and then, after a fix, `live`), that feature's own session updates the same line. It never adds a second one.
- **A feature touches only its own line.** It never edits another feature's line or the text above the table (`tools/check_feature.py` checks this).
- **Newest first:** add new lines at the top of the table.
- **Columns:**
  - **Feature id:** `F-<yyyymmdd>-<short-name>`, the same as the folder and branch names.
  - **Title:** the pull request's short title in plain words.
  - **Proposer:** a GitHub handle.
  - **Phase:** the last phase the feature reached (`1` to `4`).
  - **Outcome:** exactly one of `live`, `rolled-back`, `park` (a real need, but not now), `no-go` (not needed, already exists, or solvable without code) or `rejected` (built and reviewed, but the owner turned it down).
  - **Date:** when the outcome was reached, `yyyy-mm-dd`.
  - **Pull requests:** the feature pull request, plus the stop record or the follow-up, as `#n` links.

## Features

| Feature id | Title | Proposer | Phase | Outcome | Date | Pull requests |
|---|---|---|---|---|---|---|
