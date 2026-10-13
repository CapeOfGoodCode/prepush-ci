# Tasks

## 1. Reject a default branch that is not a branch name

- [x] 1.1 Make the config reject a `default_branch` that begins with `refs/` or `origin/`, naming `default_branch` and, for `refs/remotes/origin/`, `refs/heads/` and `origin/` followed by a name, the phrase `use "<name>"`; verify with a test for every scenario of the two config requirements (the three prefixes, `refs/tags/v1`, `origin/`, a name with a slash, the error together with other problems)
- [x] 1.2 Verify that `init --non-interactive` with such a flag, and the interactive answer, exit 1 and write nothing
- [x] 1.3 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 111-default-branch-name`) before the pull request is marked ready.
