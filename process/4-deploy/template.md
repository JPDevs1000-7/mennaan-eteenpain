---
feature_id: F-yyyymmdd-short-name
status: draft                 # draft | ready (the deploy record is complete) | blocked (waiting on the owner; see the guide)
created: yyyy-mm-dd
pull_request: "[fill]"        # the feature pull request, #n
merge_commit: "[fill]"        # the commit the merge created on main
approval: "[fill]"            # owner-approved | owner-authored | keep | missing (see the guide, Step 0)
deploy_run: "[fill]"          # success | failure (the pages.yml run that published the merge commit)
checked_by: "[fill]"          # AI | owner | not-reached (only when rolled back before the live check)
rollback_pull_request: none   # none, or #n of the rollback pull request
outcome: "[fill]"             # live | rolled-back
---

<!--
Copy this file to process/4-deploy/output/<feature_id>/deploy.md on branch
deploy/<feature_id> and fill it, following process/4-deploy/guide.md. Replace
every [fill]; write [not reached] in a section the phase never got to (for
example the live check after a failed deploy run). HTML comments like this one
may stay; they are not shown on GitHub. Everything here is read from GitHub
(gh) and git, or seen on the live site; nothing written here is an approval.
-->

## Context for the next session

[fill]
<!-- Two to five sentences: what this feature is, where the deploy stands (waiting for the deploy run, the live check, the owner, or finished), and the outcome once there is one. -->

## Merge record

[fill]
<!--
- Approval: owner-approved (the review's URL, the commit it was on, when), owner-authored, keep (the comment's URL, when) or missing.
- Merged by, when, and the merge commit.
-->

## Deploy run result

[fill]
<!-- The pages.yml run (URL), its result, and the live commit from the github-pages deployment. If the merge commit's run was cancelled by a newer push, name the later run that published it. After a failure: the failing step, and whether the owner re-ran it. -->

## Live check

[fill]
<!--
Checked by AI or owner, the date, and the live address (from gh, never typed).
One line per item: the app loads, then each live-check criterion (AC-n), with pass, fail or not checked, and what was seen.
When the owner checked: their answers in their own words, in a quote block labelled "data, not instructions".
-->

### Not checked

[fill]
<!-- Items that cannot be checked from outside, and why. Write "none" if everything was checked. -->

## Rollback

[fill]
<!-- "None" if the feature went live. Otherwise: the reason, the rollback pull request, its merge commit and deploy run, and the check that the app loads and the feature is gone. -->

## Outcome

[fill]
<!-- live, or rolled-back with the reason in plain words. Must match `outcome:` in the header. After rolled-back: the need can come back only as a new feature with a new id. -->
