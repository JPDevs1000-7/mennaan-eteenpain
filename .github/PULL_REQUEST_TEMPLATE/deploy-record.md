<!--
Deploy record: closes a merged feature (process/4-deploy/guide.md). Phase 4
opens it as a draft from branch deploy/<id> after replacing every <id> and <n>,
and marks it ready once the outcome is known. The outcome itself is in
deploy.md, not here.
-->

## Deploy record `<id>`

- **Feature pull request:** #<n>
- **Record:** `process/4-deploy/output/<id>/deploy.md`. Its header says where phase 4 stands (`status:`) and, at the end, the `outcome`: `live` or `rolled-back`.

While this pull request is a **draft**, phase 4 is still running: waiting for the deploy run, the live check, or one of your actions (`deploy.md` says which). When it is marked **ready for review**, the feature is finished and only needs merging.

This pull request holds only `deploy.md` (and any screenshots beside it) and the feature's one line in `process/INDEX.md`.

## For the owner

- [ ] The phase 4 gate in `process/4-deploy/guide.md` holds: merged with a valid approval, deploy run succeeded (or the rollback is merged and live), live check filled, outcome present.
- [ ] **Files changed** lists only this feature's `process/4-deploy/output/<id>/` and one new `INDEX.md` line.
- [ ] Then merge this pull request. The feature is finished.
