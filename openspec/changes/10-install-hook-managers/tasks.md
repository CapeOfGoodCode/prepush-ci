# Tasks

## 1. Choosing the hooks

- [x] 1.1 Add `--hooks` and manager detection at the worktree root; native stays the default, several managers and a named manager without files are refused, git config and the git directory stay untouched for a manager; verify with unit specs for the decision and integration specs for each scenario of "The choice of hooks", "Several managers are refused", "A named manager must be set up" and "A manager leaves git alone"

## 2. The managed block

- [x] 2.1 Add pure text functions in `core/` that insert or replace the block between the markers and leave every other line alone (final newline included); verify with unit specs
- [x] 2.2 pre-commit: add the `local` repo entry at the end of a block-style `repos:` and cover both hook types in `default_install_hook_types` (absent, flow list, block list, other form refused), keeping existing hooks at the pre-commit stage with `default_stages`; verify with unit specs and integration specs that run a real `pre-commit install`, `git commit` and `git push` through the manager (trailer written, check run, failing check refuses the push)
- [x] 2.3 husky: put the block first in `.husky/commit-msg` and `.husky/pre-push` (created when missing), with the pre-push block saving and re-supplying standard input; verify with integration specs on the written files and by running them with `sh` (a later line that reads standard input, a later `exit 0`, a failing check)
- [x] 2.4 lefthook: add the commands under existing or new `commit-msg:` and `pre-push:` keys with `use_stdin: true`, refuse a hook without a block-style `commands:`; verify with unit specs and integration specs that parse the result as YAML

## 3. Idempotence and the report

- [x] 3.1 Report `installed`, `updated` or `already installed` per manager, print the files and the activation command, refuse before writing anything; verify with specs that run `install` twice for each manager, restore a hand-edited block and refuse after a part would have been done
- [ ] 3.2 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 10-install-hook-managers`) before the pull request is marked ready.
