<!--
Rollback: undoes a merged feature's code on main and keeps its process/ files
(process/4-deploy/guide.md, Rollback). A session opens it from branch
revert/<id> after replacing every <id>, <n> and <commit>, and every [fill].
-->

## Rollback `<id>`

- **Undoes:** feature pull request #<n>, merge commit `<commit>`.
- **Reason:** [fill]
- **What members will notice:** [fill]
<!-- From "How to roll back" in process/3-review/output/<id>/review.md, in plain words: for example, links made with a new state-link version stop opening. -->

This pull request undoes exactly the changes the feature made outside `process/`, and nothing else. Later changes by other features to the same files stay as they are, so a file is not necessarily back to how it was before the merge. The feature's handoff files stay on `main`. The deploy record pull request for `<id>` records the outcome `rolled-back` after this one is live.

## For the owner

- [ ] **Files changed** lists the same files as the feature's changes outside `process/` (`git diff --name-only <commit>^1 <commit> -- . ":(exclude)process/"`), and each change is the feature's change reversed.
- [ ] The `test` check is green.
- [ ] Then merge this pull request. A later phase 4 session checks that the rollback is live.
