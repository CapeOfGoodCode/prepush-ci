Issue: #7

## Why

A check that runs on a machine missing its database, or on a branch that never saw the default branch's latest commits, proves less than the trailer claims (#1 section 4.5). A suite that skips its database tests "visibly" would make the trailer a lie. This slice makes the pre-push hook fail instead of skip, and refuse a branch that is behind the default branch.

## What Changes

- Before the check, the `pre-push` hook runs the preflight: every variable in `require_env` must be set and non-empty, and the `preflight` command must exit 0. A failing preflight aborts the push, names what is missing, and never skips the check.
- With `require_up_to_date` (default `origin/<default_branch>`), the hook fetches that ref and requires it to be an ancestor of `HEAD`; otherwise the push is refused with how to fix it. `require_up_to_date = false` turns the check off.
- A failing fetch refuses the push with a reason; it is never read as "up to date".

## Capabilities

### New Capabilities

- `preflight`: what the `pre-push` hook verifies before it runs the check.

### Modified Capabilities

- `pre-push-hook`: the check runs only after the preflight requirements pass.

## Impact

- New: pure logic in `src/prepush_ci/core/` (missing variables, splitting the up-to-date ref), the I/O in `pre_push_hook.py`.
- No runtime dependencies. `prepush-ci run` (#8) must run the same preflight; `doctor` (#14) reports it without running a push.
