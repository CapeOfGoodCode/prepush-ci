Issue: #292

## Why

A repository that wants its CI on the default branch switched off needs that branch to move only to a tree that passed the check on top of the current tip. Nothing guarantees it today: a merge can land a tree nobody checked on the tip it joins, so the branch re-runs everything after each merge. `land` is the one move that does: it pushes a pull request's head to the default branch as a fast-forward, and only when the head's tree has a pass for the configured check. The owner decided this on 2026-10-25 (#199, way 1); the landing workflow (#295) and the pull request comment as a second source of the result (#293) build on it.

## What Changes

- New command `prepush-ci land <pull request number>`. It fetches the head of the pull request (`refs/pull/<n>/head`) and the default branch of `origin`, and pushes the head to that branch by a fast-forward, without `--force` and without the repository's hooks, when all of these hold: the tip of the branch is an ancestor of the head; the head's tree has a pass for the key the pre-push hook would use on that commit (local result first, then `origin`); the head verifies by the rule of `verify`; the head's `require_env` variables are set; the preflight passes in a hook-free checkout of the head. Every refusal that needs no code of the head comes before the preflight runs.
- It never runs the check, never forces, and never reads the pull request's reviews, checks or state: approval is the business of the workflow or the person who runs it.
- It prints one line on standard output, `landed: …` (exit 0) or `not landed: …` (exit 1); warnings and the preflight's output go to standard error.
- The README gets an entry for `land`, with its exit statuses.

## Capabilities

### New Capabilities

- `land`: the command, its conditions and its answer.

### Modified Capabilities

- `readme`: the command reference lists `land`, and "The exit statuses are stated" covers it.

## Impact

`src/prepush_ci/`: a new `land_command.py` and pure logic in `core/land.py`; `cli.py` gets the subcommand; `README.md`. No new dependency. Out of scope: reading the result from a pull request comment (#293), the ruleset (#294), the workflow (#295).
