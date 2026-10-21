Issue: #234

## Why

A user of pre-commit never sees what the pre-push hook said. pre-commit prints a passing hook's output only with `verbose: true`; the pre-push hook that `install` writes lacks it, so "not run again", "origin holds a result" and "the result was not shared through origin" are swallowed and the push shows only `Passed`. The main feature of 0.2.0, the reuse of a result, is invisible to them (#234, found in the trial of #232).

## What Changes

- The `pre-push` hook of the block `install` writes for pre-commit sets `verbose: true`, as the `commit-msg` hook already does.
- A block written by an earlier version, without it, is brought up to date by the next `install`, which already replaces a block that differs.

## Capabilities

### Modified Capabilities

- `install`: the requirement "pre-commit shows the warning of its commit-msg hook" is replaced by one that covers both hooks.

## Impact

- `core/hook_managers.py`: the `pre-push` entry of `pre_commit_block` gains one line. No config key, no new dependency. `init` writes the block through `install` and gets it too.
