Issue: #8

## Why

The check takes minutes. A retried push, or a push right after a manual run that passed, must not pay for it again, or people reach for `--no-verify` and the trailer stops meaning anything. A person or an agent also needs to run the check by hand, under exactly the rules the hook applies, before committing to a push (#1 section 4.3).

## What Changes

- New command `prepush-ci run`: runs the preflight and then the check on `HEAD`, refusing a dirty worktree as the pre-push hook does, and exits with their result.
- A passing check is cached for the commit (SHA and tree hash) under `.git/prepush-ci/`. Failures are never cached.
- The pre-push hook skips the check, and says so, when a passing result is cached for the pushed tip. The preflight still runs.
- `cache = false` turns reading and writing of the cache off.
- A changed check command or other result-relevant config invalidates a cached pass.

## Capabilities

### New Capabilities

- `run-cache`: the `run` command and the result cache.

### Modified Capabilities

- `pre-push-hook`: a demanding tip may skip the check when the cache holds a pass for it.

## Impact

- New: the cache key and record logic in `src/prepush_ci/core/` (no I/O), the `run` command and the cache files in new modules, a route in `cli.py`.
- `pre_push_hook.py` and the new command share the refusals (clean worktree, hidden changes, preflight) and the way the check is run.
- No runtime dependencies. `doctor` (#14) and `init` (#12) may mention `run`; this change does not touch them.
