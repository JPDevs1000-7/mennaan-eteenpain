---
feature_id: F-yyyymmdd-short-name
status: draft                 # draft (a review round is open or findings wait for fixes) | ready (waiting for the owner's decision) | blocked (see the guide)
created: yyyy-mm-dd
review_round: 1               # raised by one at the start of every new review round
risk: "[fill]"                # the higher of the proposal's risk and the risk floor the reviewer works out from the diff: low | medium | high
open_findings: "[fill]"       # number of must-fix and should-fix findings not yet closed; 0 before status: ready
---

<!--
Copy this file to process/3-review/output/<feature_id>/review.md and fill it,
following process/3-review/guide.md. Replace every [fill]. HTML comments like
this one may stay; they are not shown on GitHub. checks.md, next to this file,
is written by `python tools/check_feature.py review <id>`, never composed by
the reviewer.
-->

## Context for the next session

[fill]
<!-- Two to five sentences: what this feature is, which review round this is, and where the process stands (findings waiting for fixes, waiting for the owner, blocked and why). -->

## Checks

[fill]
<!-- One line per round: round, checked commit (the latest one outside this folder), date, and pass or fail from checks.md. The details are in checks.md, one section per round. -->

## Reviewer findings and answers

| Id | Round | Severity | Where | Finding | Answer | State |
|---|---|---|---|---|---|---|
| R-1 | 1 | [fill] | [fill] | [fill] | | open |

<!--
One row per finding; write "none" in Finding if a round finds nothing.
Id: R-1, R-2... in order across all rounds, never reused. Owner change requests get O-1, O-2...
Severity: must-fix (breaks a hard rule, a criterion or existing behaviour), should-fix (a real problem that is not breaking), note (an observation, no action needed).
Where: file:line, or "proposal" or "general".
Answer: written by the Build session that resumes to fix it: "fixed in <commit>" or why it was not fixed. The reviewer never writes this column.
State: open, closed (the next reviewer checked the fix or accepted the answer), or note. Only the reviewer sets closed.
-->

## Summary for the approver

### What changes for members
[fill]
<!-- Plain words, no technical terms: what a member will see and be able to do. -->

### Risk
[fill]
<!-- The risk level and why: the proposal's level, the floor from the changed files, and which hard rules the change touches. -->

### What the reviewer checked
[fill]
<!-- A short list: the criteria and their tests, the hard rules touched, anything that needed extra care. Name anything that could not be checked. -->

## How to try it

[fill]
<!-- Steps the owner can follow on their own computer: check out the pull request, start the local server, open the page, and what to do to see each criterion. -->

## How to roll back

[fill]
<!-- What to revert, and what happens to members meanwhile: saved data, state links made with a new SCHEMA_VERSION, content already shown. Write "nothing special" only if a plain revert leaves no trace. -->

## Decision

[fill]
<!-- "Waiting for the owner's decision on the pull request." Nothing is written here after the owner decides, because a commit after the approval would cancel it; phase 4 records the approval in deploy.md. After changes requested, the requests go in the findings table as O-n rows; after reject, the reason goes here in the stop record. -->
