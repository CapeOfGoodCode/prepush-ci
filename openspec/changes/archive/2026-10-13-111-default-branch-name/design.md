# Design

## Context

`default_branch` is a string that the config only checks for emptiness. `require_up_to_date` defaults to `origin/<default_branch>` and the hook fetches that ref, so a value that is not a branch name breaks every trailer push. See `proposal.md` for the why, the delta specs for the behavior.

## Goals / Non-Goals

**Goals:** a config whose `default_branch` cannot work does not load, and the message says what to write; `init` cannot report success for it.

**Non-Goals:** the wording of `SKILL.md` (#15 owns it; a follow-up slice fixes the hint), checking that the branch exists, normalising the value for the user.

## Decisions

- **Reject in the config, not only in `init`.** `init` already exits 1 with the config's message for a value the config rejects, so one rule covers `init`, the hooks and `doctor`, and catches a config that an earlier `init` wrote. A check in `init` alone would leave such a config loading and every push refused.
- **Reject; do not strip.** Stripping `refs/remotes/origin/` would make `init` write a value the user did not pass, and the config would still load a wrong one written by hand. A refusal that names the fix is cheap and visible.
- **The prefixes are `refs/` and `origin/`.** Run on git 2.39.5 in a scratch repository after `git remote set-head origin -a`: `git symbolic-ref refs/remotes/origin/HEAD` prints `refs/remotes/origin/main`, and `git symbolic-ref --short refs/remotes/origin/HEAD` prints `origin/main`; `prepush-ci init --non-interactive --check true --hooks none --no-session-hook --default-branch refs/remotes/origin/main` exits 0 and writes `default_branch = "refs/remotes/origin/main"`. These are the two forms an agent gets from the skill's hint, and neither names a branch. `origin` is the remote the tool always uses (`require_up_to_date` defaults to `origin/<default_branch>`), so a branch that begins `origin/` is a remote ref spelled as a branch. A name like `release/1` stays valid.
- **The message gives the branch to write, in a fixed phrase.** After `refs/remotes/origin/`, `refs/heads/` or `origin/` the rest is a branch name, so the message says `use "<rest>"`: `refs/remotes/origin/trunk` and `origin/trunk` give `trunk`, `refs/heads/release/1` gives `release/1`. The prefixes are tried in that order so `refs/remotes/origin/x` is not read as a branch `remotes/origin/x`. Any other `refs/…` value (`refs/tags/v1`, `refs/remotes/upstream/x`) names no branch of `origin`, so the message only says a branch name is expected and offers none. The fixed phrase is what a test asserts: the rejected value contains the branch name too, so a bare mention would prove nothing.

## Risks / Trade-offs

- [A repository with a real branch whose name begins `origin/` or `refs/` is refused] → such a branch cannot be the default branch of a repository whose remote is `origin`, since git would see `origin/x` as the remote's `x`; accepted.
- [The skill still shows the failing hint until #15 merges and its follow-up lands] → the refusal now tells the agent what to write, so the failure is loud and not silent.
