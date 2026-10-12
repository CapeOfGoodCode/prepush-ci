# Tasks

## 1. The report and the cheap checks

- [x] 1.1 Add `prepush-ci doctor` with the six check lines in order, the `ok`/`fail`/`skip` verdicts, the closing count, the exit status, `fix:` lines, and the refusal outside a repository or in a bare one (verdicts and line text in `core/`); verify with specs for the order, the count, a failure that does not stop the later checks, and the two refusals
- [x] 1.2 Add the `config` check and the skip of `preflight` and `up-to-date` without it; verify with specs for each config place, a missing config, several problems and a malformed file
- [x] 1.3 Add the `PREPUSH_CI` check and `--mode`; verify with specs for each value, a misspelled one and every mode mismatch

## 2. The hooks

- [x] 2.1 Add `--hooks` (install's values and `none`) with install's detection (several managers, a named manager that is not set up) and the native checks (hooks path, executable script, recorded interpreter, linked worktree); verify with specs after `install`, before it, after another tool changed `core.hooksPath`, with a deleted script, a script that is not executable and a vanished interpreter
- [x] 2.2 Add the manager checks: the block in the manager's file, activation of pre-commit and lefthook by the hook script in the hooks directory, husky's `core.hooksPath` and its stubs; verify with specs for each manager installed, not activated, and with a block removed by hand

## 3. Preflight and the remote

- [x] 3.1 Add the `preflight` check: variables, the command run as the hook runs it, output shown only on failure; verify with specs for each outcome and the working directory
- [x] 3.2 Add the `up-to-date` check with `git ls-remote` (no fetch, `GIT_TERMINAL_PROMPT=0`); verify with specs for each failure, a disabled check, a branch with a slash and the proof that a local tracking ref does not move
- [x] 3.3 Prove that `doctor` changes nothing: a snapshot of the working tree and the git directory before and after, in a set-up and a broken repository
- [ ] 3.4 Run `sh scripts/ci` and verify it passes
