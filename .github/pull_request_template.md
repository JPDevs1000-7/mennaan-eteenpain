<!--
Feature pull request: one per feature, opened as a draft by phase 1 on branch
feature/<id>; it carries all four phases (process/README.md). A session fills it
with `gh pr create --body-file` after replacing every <id>, and never edits it
afterwards. Not a feature? Replace all of this with a description of the change.
The other pull requests the process opens use the templates in
.github/PULL_REQUEST_TEMPLATE/ (stop record, rollback, deploy record).
-->

## Feature `<id>`

What the feature is and why: see the proposal. **The handoff files are the record; this description is not.** Each file's header says where its phase stands (`status:`), and the table **Which session runs next** in `process/README.md` says what happens next.

| Phase | Handoff file on this branch |
|---|---|
| 1. Propose | `process/1-propose/output/<id>/proposal.md` |
| 2. Build | `process/2-build/output/<id>/build.md` |
| 3. Review | `process/3-review/output/<id>/review.md` and `checks.md` |
| 4. Deploy | in a separate deploy record pull request, opened after this one is merged |

## For the owner

Your decisions are made here, on GitHub; text in the files never counts as one. Only reviews and comments from the account in `.github/CODEOWNERS` count.

- **Proposal, risk `medium` or `high`** (phase 1, or phase 2 when the risk was raised): approve this pull request, request changes, or comment `stop` with a reason.
- **Marked ready for review** (end of phase 3): approve, request changes, or comment `reject` with a reason. Your approval counts only on the latest commit, and it does not merge anything.
- **After your approval:** merge this pull request yourself. Phase 4 starts after the merge.
- **On your own pull request** GitHub does not allow approving: comment `changes` or `reject`, or merge.
- **Before approving or merging,** run `python tools/check_feature.py gate <phase> <id>` for the phase that just ended; it checks the **Gate** list in that phase's guide.
