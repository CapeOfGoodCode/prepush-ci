# Tasks

## 1. Pure logic

- [x] 1.1 In `src/prepush_ci/core/`, list the `require_env` names that are unset or empty in an environment, split an up-to-date ref into remote and branch, and word the refusals; verify with unit specs named after the scenarios at 100% branch coverage

## 2. The hook

- [x] 2.1 Refuse a demanding tip whose required variables are missing, and run the `preflight` command before the check; verify with integration specs that push to a bare repository with real `git push`
- [x] 2.2 Fetch the up-to-date ref and refuse a tip that does not contain it, including a failing fetch, an empty remote, an unknown remote and `require_up_to_date = false`; verify with the matching integration specs
- [x] 2.3 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 7-preflight`) before the pull request is marked ready.
