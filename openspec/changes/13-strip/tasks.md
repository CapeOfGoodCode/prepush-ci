# Tasks

## 1. Pure logic

- [x] 1.1 In `src/prepush_ci/core/`, add the message rewrite: a commit message and the demanded keys in, the message without the matching trailer lines out (blank separator removed when the trailer block empties); reuse the key matcher that #5 adds (this task is blocked by #5); verify with unit specs named after the scenarios at 100% branch coverage

## 2. The command

- [x] 2.1 Add `prepush-ci strip [<base>]`: resolve the base, refuse unsafe states, rewrite the commits in history order keeping author, committer, tree and parents' shape, with no git hook run (write the commits with plumbing, not `commit --amend`), move the current branch, print the report; verify with integration specs against real temporary repositories
- [x] 2.2 Cover the refusals (dirty, in-progress operations including `git am` and bisect, no merge base, detached `HEAD`, bad base, bad config, extra argument) and show that each leaves `HEAD` and the worktree as they were; verify with integration specs
- [x] 2.3 Show with the real pre-push hook that a push after `strip` with `PREPUSH_CI` unset runs no check; verify with an integration spec
- [x] 2.4 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 13-strip`) before the pull request is marked ready.
