Issue: #13

## Why

A machine that cannot run the full check (a laptop, a cloud session without the services) still has to push commits that were made with `PREPUSH_CI=full`. The pre-push hook (#5) runs the check for such a push, and the push fails when the machine cannot run it. `strip` removes the demand, so the push goes through and CI runs in full for those commits (#1 section 4.3).

## What Changes

- New command `prepush-ci strip [<base>]`: removes the configured trailer and every `legacy_keys` trailer from each commit in `<base>..HEAD`, rewriting the current branch. `<base>` defaults to the merge base with the default branch.
- Only the trailer lines go. Other trailers, message text, authors, committers, dates and trees stay; commits before the first one that changes keep their SHA.
- It runs no git hook, so the trailer is never written back, even with `PREPUSH_CI=full` set.
- It refuses a dirty worktree, an unfinished rebase, merge, cherry-pick, revert, `git am` or bisect, a detached `HEAD` and a `<base>` that is not an ancestor of `HEAD`, and changes nothing then.
- It prints how many commits it rewrote, the old and new tip, and that the next push needs `--force-with-lease`.

## Capabilities

### New Capabilities

- `strip`: which commits `prepush-ci strip` rewrites, how, and when it refuses.

### Modified Capabilities

None.

## Impact

- New: the pure message rewrite in `src/prepush_ci/core/`, the `strip` subcommand in the CLI.
- Depends on the pre-push hook (#5): the last scenario shows that a push after `strip` runs no check, which only the real hook can show.
- Not here: pushing, `verify` (#6), and removing the trailer at commit time (the commit-msg hook only adds it).
