Issue: #197

## Why

When the full check runs before the push, pull request CI skips its jobs and the pull request shows only that they were skipped: a reviewer cannot see what was checked, on which tree, with which result. With the result posted as a real check run, the test jobs need not run on Actions at all, which saves minutes right away (#196, step 1).

## What Changes

- New command `prepush-ci report`. It posts the result of a run of the check, made in a session or on a machine, for a commit: as a check run through a GitHub App the team owns, or as a commit status when no app is configured.
- The caller states what it checked (`--tree`, `--result`); `report` refuses a tree that is not the commit's tree, so a result never shows on a state it did not check.
- The check run's summary names the commit, the tree, the `check` command, the preflight, the tool versions, the OS, the test counts (from JUnit XML) and the coverage (from `coverage.json`).
- The README's reference gains the entry for `report`, with its exit statuses.

Split off into their own slices, blocked by this one: line annotations and the `in_progress` state (#200), `prepush-ci app setup` and the README on app setup (#201). Ruff and mypy output is read there.

## Capabilities

### New Capabilities

- `report`: what `prepush-ci report` reads, refuses, posts and exits with.

### Modified Capabilities

- `readme`: the reference lists `report`, and its exit statuses are stated.

## Impact

- New: `report` subcommand in `src/prepush_ci/`, its pure logic (JUnit and coverage reading, summary and status text, repository from a remote URL) in `core/`. No runtime dependencies: HTTP through `urllib`, the app's token request signed by the `openssl` program.
- The check run is created with the app's own permission, `checks: write`; the commit status needs a token that may write statuses.
