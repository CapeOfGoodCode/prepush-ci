# Tasks

## 1. Pure logic

- [x] 1.1 In `src/prepush_ci/core/`, build the cache key from a SHA, a tree hash and the result-relevant config values, name the record file for a key and tell an intact record from a damaged one; verify with unit specs named after the scenarios at 100% branch coverage

## 2. The cache and `run`

- [x] 2.1 Read and write records under the repository's git directory, a damaged or unwritable cache falling back to running the check; verify with integration specs against real repositories
- [x] 2.2 Add `prepush-ci run`: the hook's refusals, the preflight, the check, the exit code, and the record of a pass unless `cache = false`; verify with the matching integration specs
- [x] 2.3 Let the pre-push hook skip the check on a cached pass of the pushed tip, saying so, and record its own passes; verify with integration specs that push to a bare repository with real `git push`, including a push the remote rejects and a retry
- [x] 2.4 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 8-run-cache`) before the pull request is marked ready.
