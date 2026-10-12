# Tasks

## 1. Pure logic

- [ ] 1.1 In `src/prepush_ci/core/`, add the decision: parsed trailer keys, the demanded keys and the committer e-mail as recorded (`%ce`) in, verified or not plus a one-line reason out; reuse the key matcher that #5 adds to `src/prepush_ci/core/` (this task is blocked by #5; do not write a second one); verify with unit specs named after the scenarios at 100% branch coverage

## 2. The command

- [ ] 2.1 Add `prepush-ci verify <sha>`: resolve the commit, read its trailers and the config committed in it, print the line with the full sha and exit 0 or 1, also for a missing, empty or extra argument; verify with integration specs against real temporary repositories
- [ ] 2.2 Fail with the fetch hint for an unknown or shallow-missing sha; verify with an integration spec on a real shallow clone
- [ ] 2.3 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 6-verify`) before the pull request is marked ready.
