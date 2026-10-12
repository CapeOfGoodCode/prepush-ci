# Design

## Context

The pre-push hook (#5, #7) refuses a demanding tip that is not `HEAD`, a dirty worktree and `PREPUSH_CI=off`, runs the preflight, then the check. `run` is the same sequence started by hand, and the cache lets the hook skip its last step. See `proposal.md` for the why, the delta specs for the behavior.

## Goals / Non-Goals

**Goals:** one definition of "the check passed on this commit" shared by `run` and the hook; a retried push costs no second check; a cache that is stale, damaged or unwritable never lets a commit through that did not pass.

**Non-Goals:** `verify` and CI (the cache is local and never read by CI), `doctor` reporting on the cache (#14), pruning old records, caching across clones.

## Decisions

- **Only the check is cached; the preflight always runs.** The issue asks for a skipped check. The preflight is cheap by definition and its answers (services up, variables set, branch up to date) go stale between two pushes of one commit, so a hit would be the wrong place to trust a record.
- **`run` always runs the check, and a pass refreshes the record.** It is the explicit "do it now"; a `run` that answered from the cache could not be used to re-run a flaky check. Only the hook reads the cache.
- **`run` is not a hook.** It ignores `PREPUSH_CI` and the trailer: whoever types `run` has opted in, and `HEAD` need not demand anything. It exits 0 when everything passes and 1 otherwise, as the hook does.
- **The key is the commit SHA, its tree hash and a fingerprint of the config values that decide the result** (`check`, `preflight`, `require_env`, `require_up_to_date`). The tree normally carries the config, so the fingerprint matters only for an ignored config file; it costs one hash and closes that gap. `trailer`, `legacy_keys`, `default_branch` and `cache` do not change what a pass means, so they are not part of the key.
- **One small file per key under `prepush-ci/` in the repository's git directory** (`git rev-parse --git-path prepush-ci`), named by a hash of the key. Nothing to lock: two writers of one key write the same fact. No format is promised beyond "a record for this key is present and intact".
- **Fail toward running.** A record that is missing, empty, truncated or not for this key is a miss, so the check runs. A cache that cannot be written is a warning on stderr and never changes the exit code.
- **No pruning.** Records are a few bytes. `doctor` or a later slice can add cleanup if it ever matters.

## Risks / Trade-offs

- [The cache is local and trusted] → it only decides whether to repeat a check the same user already ran; anyone who can write `.git/` can also run `git push --no-verify`. The intent's trust model (#1 section 2) already accepts that.
- [Environment differences between the run that passed and the push] → the preflight runs every time and covers what the project declared; undeclared differences are the project's `require_env`, not the cache's.
- [A flaky check that failed after an earlier pass] → the earlier pass stays, since it is true of that commit. A later `run` that passes refreshes it; a failing one changes nothing.
