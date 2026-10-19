Issue: #200

## Why

A red check run that only says "2 failed" sends a reviewer to the log, and a run that shows nothing until it ends hides that a check is under way. With each failure on its line in the pull request's diff and a run that shows as in progress from the start, the reviewer sees what broke and that a result is coming without leaving the pull request (#196, step 1; split from #197 so each slice is reviewable in one sitting).

## What Changes

- `prepush-ci report --start` marks the check run `in_progress` (a `pending` commit status without an app). The final `report` completes that run instead of creating a second one.
- Failing tests (JUnit XML that carries a file and a line), ruff errors (`--ruff`, JSON) and mypy errors (`--mypy`, default text output) become annotations on their lines, sent in batches of 50 and also when there are more than 50.
- A result that contradicts the files is refused: `passed` with a ruff or mypy error, a path outside the worktree.
- The summary of a red run lists the failures first.

## Capabilities

### Modified Capabilities

- `report`: the command takes `--start`, `--ruff` and `--mypy`; the check run can be started and then completed; failures become annotations; the summary lists them.

## Impact

- `src/prepush_ci/core/report.py` (parsers for the two formats and the JUnit locations, the batches, the summary), `src/prepush_ci/report_command.py` (`--start`, the lookup of the run in progress, the updates), `src/prepush_ci/github_api.py` (a lookup and an update of a check run, a pending status), `src/prepush_ci/cli.py` (three flags).
- The reference in `README.md` names the new flags.
- A GitHub App needs no new permission: `checks: write` already reads and updates its own check runs.
