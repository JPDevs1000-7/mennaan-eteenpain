<!--
Stop record: a feature that stopped (outcome park, no-go or rejected) leaves this
record on main so later proposals find it (process/README.md, decisions 13, 16
and 17). A session fills it after replacing every <id>, <n>, <phase> and
<outcome>, and every [fill]. No code ever goes in a stop record.
-->

## Stop record `<id>`

- **Outcome:** `<outcome>` in phase `<phase>`. The reason is in the handoff files (the verdict in `proposal.md`, or the decision in `review.md`).
- **Feature pull request:** #<n> <!-- or "this pull request" when phase 1 turned the feature pull request itself into the stop record -->
- **Why it stopped, in plain words:** [fill]

This pull request holds only the feature's handoff files and its line in `process/INDEX.md`:

- `process/1-propose/output/<id>/proposal.md`
- `process/3-review/output/<id>/review.md` <!-- only if the feature was reviewed; otherwise delete this line -->
- one new line in `process/INDEX.md`

## For the owner

- [ ] `python tools/check_feature.py gate stop <id>` passes (it checks the files, the `INDEX.md` line and the title).
- [ ] The feature pull request is closed unmerged (if it is a different pull request from this one), so its code never reaches `main`.
- [ ] Then merge this pull request.
