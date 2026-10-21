# Tasks

## 1. Show the hook's messages

- [ ] 1.1 Add `verbose: true` to the `pre-push` hook of the pre-commit block; verify with specs for the written block, for a block of an earlier version replaced with `updated` and the lines outside it unchanged, and for a push through `pre-commit` that shows the line the hook prints when the check is not run again
- [ ] 1.2 Run `sh scripts/ci` and verify it passes
