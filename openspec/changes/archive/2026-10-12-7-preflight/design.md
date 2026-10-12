# Design

## Context

`pre-push` (#5) refuses a demanding tip that is not `HEAD`, a dirty worktree or `PREPUSH_CI=off`, then runs the check. This change inserts the preflight between those refusals and the check. See `proposal.md` for the why, the delta specs for the behavior.

## Goals / Non-Goals

**Goals:** the check never runs, and so no trailer is earned, in an environment the project declared insufficient or on a branch behind the default branch; every refusal says how to fix it.

**Non-Goals:** the result cache (#8), `run` and `doctor` (#8, #14), installing hooks (#9), what the `preflight` command does inside.

## Decisions

- **Order: variables, up to date, preflight command, check.** The cheapest and most certain refusal comes first, and a rebase that the up-to-date step asks for would invalidate any work a later step did. Each earlier refusal stops every later step, and the scenarios test the stops: variables before the fetch and the preflight, up to date before the preflight, preflight before the check.
- **A failing preflight never skips, and nothing turns it off.** No value of `PREPUSH_CI` and no config key lets a demanding tip reach the check without it. `require_up_to_date = false` is the one switch, and only for the up-to-date step.
- **A variable is missing when it is unset or empty.** An empty value usually means a templated secret that was never filled in. All missing names are reported at once; the `preflight` command does not run when one is missing.
- **The `preflight` command runs like `check`**: through the shell, from the repository root, output on the terminal, its exit status decides.
- **`require_up_to_date` names a remote-tracking ref, `<remote>/<branch>`, split at the first `/`** (so `origin/release/1` is remote `origin`, branch `release/1`). The hook runs `git fetch <remote> +refs/heads/<branch>:refs/remotes/<remote>/<branch>` and then `git merge-base --is-ancestor refs/remotes/<remote>/<branch> HEAD`. Fetching into the tracking ref the user's own `origin/main` reads keeps `git rebase origin/main` correct afterwards; an explicit refspec does not depend on the remote's configured refspec. A ref that is not `<remote>/<branch>` of a configured remote refuses the push (fail closed).
- **A fetch that fails is a refusal, with git's own message and two ways out.** Offline pushes are not special-cased. Every such refusal names `require_up_to_date = false` and pushing a tip without the trailer (which runs no check). Any other `merge-base` exit than 0 or 1 is also a refusal.
- **A ref the remote does not have is a refusal too, including the default branch of an empty remote.** Telling "not pushed yet" from a mistyped `origin/mian` is impossible without trusting the typo, so it fails closed. The first push of a new repository goes without the trailer, or with `require_up_to_date = false`.
- **The empty string stays a config error.** The issue says "false (or empty) disables"; the `config` capability rejects empty values everywhere, so `false` is the one spelling, and a blank value never disables a check silently.
- **Only demanding tips pay for it.** Tips without the trailer, tags and deletions run neither the fetch nor the preflight.

## Risks / Trade-offs

- [A shallow clone can report "not up to date" for a branch that is] → the refusal is fail-closed; the message names the ref and offers rebase or merge, and `git fetch --unshallow` remains the user's call.
- [Fetch to `refs/remotes/...` changes the user's tracking ref during a push] → harmless: it is what `git fetch` does.
- [A race remains between the fetch and the merge] → accepted by the intent (#1 section 4.5): it shrinks the gap, it does not close it.
