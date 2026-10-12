Issue: #5

## Why

The trailer is only a demand (#1 section 2). Until the `pre-push` hook enforces it, a commit with the trailer can reach the remote unchecked and CI would skip it. This slice makes the invariant true: **trailer on the remote implies the full check passed on exactly that commit**.

## What Changes

- New command `prepush-ci hook pre-push`: reads the pushed refs (git's stdin protocol, or pre-commit's `PRE_COMMIT_*` variables, whose blind spots are recorded as known limits), ignores tags, deletions and non-branch refs, and for each pushed branch tip decides whether the tip demands the check.
- A tip demands the check when it carries a trailer, as `git log` shows it, whose key is the configured key or a `legacy_keys` key (case-insensitive, any value), by the config committed in the tip or the worktree config. Only the tip counts.
- A demanding tip is pushed only if it is the checked-out `HEAD`, the worktree is clean and the configured `check` passes. Otherwise the push is refused with a reason.
- Any error that stops the hook from deciding refuses the push.
- `PREPUSH_CI=off` refuses to push a demanding tip; no value lets one through unchecked.
- With `PREPUSH_CI=full` and a tip without the trailer, the hook prints a hint (CI will run; `git commit --amend --no-edit` adds the trailer) and lets the push go.

## Capabilities

### New Capabilities

- `pre-push-hook`: what `prepush-ci hook pre-push` does for each pushed ref.

### Modified Capabilities

None.

## Impact

- New: pure ref-line parsing and the demand decision in `src/prepush_ci/core/`, the `hook pre-push` subcommand in the CLI.
- No runtime dependencies. Preflight, `require_up_to_date` and the result cache are out of scope (#7, #8); installing the hook is #9. `verify` (#6) must apply the same trailer rule defined here.
