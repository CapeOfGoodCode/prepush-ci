# Tasks

## 1. Pure logic

- [x] 1.1 In `src/prepush_ci/core/`, parse git's pre-push ref lines and pre-commit's variables into pushed refs, drop deletions and refs that are not branches, and decide from parsed trailer keys (read with `git log` from the tip and the configs of tip and worktree) whether a tip demands the check; verify with unit specs named after the scenarios at 100% branch coverage

## 2. The hook

- [x] 2.1 Add `prepush-ci hook pre-push`: validate `PREPUSH_CI`, read the refs, ignore what is not a branch update, load the config only when a branch tip is examined; verify with integration specs that push to a bare repository with real `git push`
- [x] 2.2 Enforce a demanding tip: refuse with `off`, refuse when the tip is not `HEAD` or the worktree is dirty, otherwise run the check once per distinct sha and abort the push when it fails; verify with the matching integration specs
- [x] 2.3 Fail closed when the hook cannot decide (unknown sha, no worktree, unreadable status, unborn `HEAD`) and resolve `PRE_COMMIT_LOCAL_BRANCH`; verify with the matching integration specs, and with a real `pre-commit` run for the known limits
- [x] 2.4 Print the hint for a tip without the trailer in full mode; verify the hint and the silent cases
- [x] 2.5 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 5-pre-push-hook`) before the pull request is marked ready.
