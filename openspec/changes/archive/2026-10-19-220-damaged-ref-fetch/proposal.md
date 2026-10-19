Issue: #220

## Why

A repository whose `refs/prepush-ci` is a regular file, or holds a result ref whose file is empty, cannot push or `run` a check at all: git cannot fetch while such a ref exists, the up-to-date step fails, and the push is refused with a reason that blames `require_up_to_date`. The cache is meant to cost time and nothing else.

## What Changes

- The up-to-date step fetches in a way that ignores a damaged ref, so a damaged ref under `refs/prepush-ci` (a regular file, an emptied result, a refused name) no longer fails it. The fetch starts no auto-maintenance. Nothing else about the step changes: a fetch that fails for any other reason still refuses the push.
- `run` and the pre-push hook behave as `run-cache` already says for such a repository: a damaged record is a miss and the check runs, an unwritable cache is a warning.

## Capabilities

### Modified Capabilities

- `preflight`: a requirement is added that a damaged or unreadable ref under `refs/prepush-ci` does not make the up-to-date fetch fail.

## Impact

- `preflight.py` runs its `git fetch` with the environment variable `GIT_REF_PARANOIA=0` and the option `--no-auto-maintenance` (git 2.29 or newer), so that git's housekeeping cannot prune history while broken refs are ignored. `git.py` may gain an environment argument. No config key, no new dependency; `run-cache` does not change.
