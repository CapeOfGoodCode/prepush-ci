# Tasks

## 1. Compare the executable on PATH

- [x] 1.1 Add to `core/doctor_hooks.py` the pure part: given the `--version` line of doctor, the path found on `PATH` (or none) and the outcome of running it (its first line, or why it gave none), return whether the hooks run the same version and the text of the line and of the fix; verify with unit specs for the same line, a different line, no executable, a non-zero exit, no output and a timeout
- [x] 1.2 In `doctor_command.py`, look up `prepush-ci` on `PATH` and run `<found> --version` with a limit of 10 seconds, only for the hooks of a manager whose other requirements hold, and feed the result to the manager checks of both hooks; run it once for both; verify with integration specs for every scenario of the change, each with a stub `prepush-ci` on `PATH`
- [x] 1.3 Verify that a manager's file without the block, or a pre-commit that is not activated, does not run the stub (the stub records its runs), and that native hooks and `--hooks none` do not look at `PATH`
- [x] 1.4 Let `doctor` run from source that is no installed distribution: the manager checks that would otherwise pass fail with a line saying that `prepush-ci` cannot read its own version (no traceback, no executable run); verify with integration specs on a copy of the code without package metadata and a unit spec

## 2. Existing specs

- [x] 2.1 Put a stub `prepush-ci` that prints doctor's own line on `PATH` in the helper of the integration specs that expect a manager's lines to start with `ok`, and run the specs of the `doctor` capability
- [x] 2.2 Run `sh scripts/ci` and verify it passes
