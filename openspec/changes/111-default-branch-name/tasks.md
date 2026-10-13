# Tasks

## 1. Reject a default branch that is not a branch name

- [ ] 1.1 Make the config reject a `default_branch` that begins with `refs/` or `origin/`, naming `default_branch` and the name without the prefix; verify with integration specs for both prefixes, a name with a slash, and the error being reported together with other problems
- [ ] 1.2 Verify that `init --non-interactive` with such a flag, and the interactive answer, exit 1 and write nothing
- [ ] 1.3 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 111-default-branch-name`) before the pull request is marked ready.
