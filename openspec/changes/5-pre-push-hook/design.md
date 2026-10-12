# Design

## Context

`commit-msg` (#4) writes the trailer; this change makes the push honour it. See `proposal.md` for the why, the delta spec for the behavior.

## Goals / Non-Goals

**Goals:** no commit that demands the full check reaches the remote through the hook without the check having passed on it; a failure always says why.

**Non-Goals:** preflight, `require_up_to_date` (#7), the result cache (#8), installing the hook (#9), bypasses (`--no-verify` is outside the trust model, #1 section 2).

## Decisions

- **The trailer key alone demands the check, case-insensitively, whatever the value.** `commit-msg` writes with `--if-exists doNothing`, which matches the key only; a message that already has `Prepush-CI: off` keeps it. Enforcing on the key alone means that line cannot slip through, and over-demanding costs a run while under-demanding breaks the invariant. `verify` (#6) uses this same rule, so a commit CI skips is a commit the hook checked.
- **`legacy_keys` demand the check too.** If CI skips on a legacy key (#6), the hook must have enforced it; otherwise such a commit reaches the remote unchecked.
- **Git decides what a trailer is, the way `git log` shows it.** The tip's trailers are read with `git log -1 --format=%(trailers:only,unfold)`, which is what CI sees. Plain `git interpret-trailers --parse` would stop at a `---` line, and `commit-msg` writes the trailer after one on purpose; it would need `--no-divider`. The core only matches already-parsed keys.
- **The config that decides the demand is both the tip's and the worktree's.** CI (`verify`, #6) reads the config committed in the commit, so the hook must honour that; the worktree config is what the user runs the check with. A tip demands the check if either says so (fail closed): a branch that renames the key cannot slip through when another branch is checked out. A tip with no config adds no keys (older commits stay pushable); an invalid config in the tip refuses. `verify` (#6) reads the tip's config only, which the union covers. When the tip is `HEAD` and the worktree is clean the two are equal, so the check that runs is the tip's.
- **Refs come from stdin; pre-commit's variables are the fallback.** pre-commit consumes git's stdin and exposes one ref as `PRE_COMMIT_TO_REF` (the pushed sha) and `PRE_COMMIT_REMOTE_BRANCH` (the remote ref). Stdin wins when it has lines; a missing remote branch counts as a branch (fail closed). When the root commit is pushed pre-commit sets no `PRE_COMMIT_TO_REF` but does set `PRE_COMMIT_LOCAL_BRANCH`, so the tip is what that ref resolves to; unresolvable, the push is refused.
- **Under pre-commit the hook is blind to some refs, and says so.** pre-commit gives the hook only the first ref with new commits and skips refs the remote already has. The hook cannot see the rest, so the spec records these as known limits rather than pretending otherwise; #9 (install) should prefer the native `pre-push` hook and offer pre-commit as the second choice.
- **The remote ref decides what is a branch** (`refs/heads/`). `git push origin HEAD:refs/heads/x` has `HEAD` as its local ref, so the local name says nothing.
- **A deletion is a pushed sha of all zeros.** Nothing is checked, nothing can be wrong.
- **Fail closed on the config.** The trailer key lives in the config, so without a valid config the hook cannot tell whether a tip demands the check; it refuses the push and names the problem as the `config` capability specifies. The config is read only when a branch tip is examined, so tag and delete pushes never need it.
- **`PREPUSH_CI` is validated like in `commit-msg`**: `full`, `off`, unset or empty; anything else is refused naming `full` and `off`, before any ref is read. `unset`, empty and `full` behave the same here: the trailer, not the variable, demands the check (#1 section 2).
- **Order of refusals for a demanding tip**: variable `off`, then not `HEAD`, then dirty worktree, then the check. The cheap, certain reasons come first and the check never runs on a state that is not the commit.
- **Untracked files make the worktree dirty; ignored files do not.** The check runs against the worktree, and an untracked file can change its outcome (a test that exists only locally).
- **Several refs: the check runs once per distinct sha.** Only the checked-out `HEAD` can be checked, so a second demanding tip with another sha is refused as "not HEAD"; two refs to the same sha need one run.
- **The check runs through the shell, from the repository root, with output on the terminal.** `check` is a command line (`make ci && ./extra`), not an argv; its exit status decides. The hook's own exit status is non-zero on any refusal.
- **Fail closed on the hook's own errors.** Whenever the hook cannot decide for a branch tip (unknown sha, unreadable message, no worktree, unreadable status, unborn `HEAD`), it exits non-zero naming what failed. A demanding tip never goes up because the hook was unsure; an unexpected exception also exits non-zero.
- **The hint is printed once per push**, to stderr, only with `PREPUSH_CI=full`: unset means the user did not opt in, and nagging them helps nobody.

## Risks / Trade-offs

- [A check that writes to the worktree leaves it dirty after the run] → not detected: the invariant is about the state the check started from.
- [Untracked build artifacts that are not ignored block the push] → intended, the message names them; the fix is `.gitignore`.
- [Key-only matching makes a hand-typed `Prepush-CI: off` demand a check] → harmless over-demand, and `verify` skipping it is consistent.
