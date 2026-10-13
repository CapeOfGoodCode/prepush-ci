# Tasks

## 1. Correct the hint

- [ ] 1.1 Change the `<default branch>` bullet of `SKILL.md` to the command and the removal of `refs/remotes/origin/`, and add the case without `origin/HEAD`; verify with a test for every scenario of the two requirements (run the hint's command in a repository with `origin/HEAD` set to `origin/trunk`, to `origin/release/1` and to `origin/trunk` next to a local branch `origin/trunk`, and `init` with the result; run it in one without, see it fail, and run `init` with a named branch)
- [ ] 1.2 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 113-default-branch-hint`) before the pull request is marked ready.
