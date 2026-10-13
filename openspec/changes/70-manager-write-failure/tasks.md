# Tasks

## 1. Undo a refused write

- [ ] 1.1 Verify with integration specs, for husky, that a read-only `.husky/pre-push` ends in exit 1, a message naming the file and no traceback, with `.husky/commit-msg` unchanged or absent as the scenarios say; build the read-only state so it holds for the user CI runs as (a read-only file refuses a write for an ordinary user on Linux and through the read-only attribute on Windows); a spec that cannot build its state fails, it does not skip
- [ ] 1.2 Add the undo to the write loop of the manager install: remember each file's previous contents, restore them on the first `OSError`, remove files the run created, report the original failure with the file name and reason
- [ ] 1.3 Verify with an integration spec that the rerun after making the file writable prints `installed` and both files hold the block
- [ ] 1.4 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 70-manager-write-failure`) before the pull request is marked ready.
