## Context

The pre-push hook already knows the key of a result (`<tree>-<config>`, "The result is keyed by the tree and the inputs"), looks for it locally and then on `origin` ("A result on the remote is reused"), and `verify` already decides whether a commit carries the trailer and was not made by a server. `land` is a new command that reuses all three on a commit that is not checked out: the head of a pull request.

## Decisions

- **The branch to move is the branch `origin`'s `HEAD` points to, not a config value.** Rationale: the config is committed in the pull request, so a pull request could name the branch it lands on; `origin` decides what the default branch is.
- **The head is `refs/pull/<n>/head` on `origin`, read with git alone.** Rationale: no token and no API call, so it works in every session that can fetch; the price is that `land` does not know whether the pull request is open, approved or green. The person or the workflow that runs it decides that.
- **The key is computed as the hook computes it: the config committed in the head, and the `preflight` run in a temporary detached checkout of the head.** Rationale: the hook runs the preflight in a checkout of `HEAD`; a different rule would make `land` and the hook disagree about the same tree. The checkout is removed afterwards. The preflight's standard output goes to standard error, because the answer is one line.
- **The head must also verify (`verify`'s rule).** Rationale: `verify` on the tip of the branch keeps answering true after landing, so a deploy gate that calls it keeps working.
- **A head that is the tip or an ancestor of it is "already on" the branch, exit 0.** Rationale: landing twice, or after a merge by hand, is not a failure to retry.
- **A moved branch is checked twice: before the push, and again when the push is refused.** Rationale: the fast-forward push is the compare-and-swap, so a branch that moves in between is never overwritten; the second look only tells the user the right reason.
- **The push is the tool's own: `git push --no-verify origin <sha>:refs/heads/<branch>` with `core.hooksPath` at an empty directory, never with `--force`, `--force-with-lease` or `+`.** Rationale: same as publishing a result ref; the ruleset experiment of #199 (T5) shows that a bypass actor's push without `--force` still refuses a non-fast-forward.
- **A usage error is the parser's (exit 2), as for `run` and `report`; `verify` is the exception because a CI gate must see only 0 or 1.** Rationale: `land` is called by people and by a workflow that reads the line, not by a gate that treats 0 as a licence.
- **`land` runs code of the pull request, and says so.** The `preflight` committed in the head is code of the pull request, run with the lander's rights: a repository admin's session (way 1), the workflow that holds the bypass app's token (#295). A fork can open the pull request. `land` does not judge whether to trust it, as it does not judge approval; whoever runs it does, and #295 must run it only for pull requests it trusts. What `land` does guarantee is the order: every refusal that needs no code of the head comes first (a missing pull request or branch, a moved branch, already on the branch, no verified head, cache off, a missing required variable), so the `preflight` is the first and only command of the head that runs. Rationale: the key needs the preflight's output, so it cannot be skipped, but a head that cannot land anyway never gets to run it.
- **None of the commands that touch the clone runs a hook of the repository: the checkout, the fetch and the push.** Rationale: `git worktree add` runs `post-checkout`, and the hooks are the lander's, written for checkouts the lander makes. `--no-verify` skips `pre-push` and nothing else: git also runs `reference-transaction` when a fetch updates `refs/remotes/origin/<branch>` or a push updates it. Done by pointing `core.hooksPath` at an empty location for each of those commands.
- **`land` checks `require_env` as the hook does, before the preflight and the key.** Rationale: the hook refuses a push before it fetches or runs anything when a required variable is unset; a pass the hook would never have computed must not be landed. The variables are read from the config committed in the head, in the lander's environment.
- **The ancestry check always applies, whatever `require_up_to_date` says.** Rationale: the point of `land` is that the branch moves only to a tree checked on top of the tip; a config of the pull request must not relax it.
- **An `origin` whose `HEAD` names no branch it holds is refused.** Rationale: `git ls-remote --symref origin HEAD` prints nothing and exits 0 for a bare `origin` made under another `init.defaultBranch` once only `main` was pushed (git 2.39.5); guessing `main` would let the clone decide the default branch.
- **`cache = false` cannot land.** Rationale: no pass is recorded, so there is nothing to find; the line says so.

## Verified with the tools

git 2.39.5, a bare `origin` with `main`, the pull request head pushed to `refs/pull/7/head`:

```
$ git ls-remote --symref origin HEAD
ref: refs/heads/main	HEAD
$ git -c core.hooksPath=<empty> fetch origin main refs/pull/7/head      # FETCH_HEAD holds both; only refs/remotes/origin/main may be updated, by git itself
$ git -c core.hooksPath=<empty> push --no-verify origin <sha>:refs/heads/main        # a fast-forward
   d79b40f..d8b6574  d8b6574… -> main
$ git -c core.hooksPath=<empty> push --no-verify origin <other>:refs/heads/main      # not a fast-forward
 ! [rejected]  2a0ff29… -> main (non-fast-forward)
$ git -c core.hooksPath=<empty> push --no-verify origin <sha>:refs/heads/main        # origin's pre-receive hook declines
 ! [remote rejected] a256725… -> main (pre-receive hook declined)
$ git worktree add -q --detach ../wt <sha> && git worktree remove --force ../wt
```

The reason `land` quotes in "A refused push is reported" is the text in the last parentheses of the `!` line. A ruleset's refusal on GitHub (GH013) shows as `remote rejected`, as the owner's experiment (T2, T3) recorded. Whether GitHub shows the pull request as merged after such a push is GitHub's behaviour and is not specified here: #292 expects it, nobody but a bypass actor can try it, and a pull request that stays open after a landing is a `Bug` for the owner's first real landing (#296) to find.

## Risks

- The preflight output enters the key. `land` run in an environment that differs from the session's (another tool version) finds no pass. The landing workflow (#295) must set up the same tools; this change only says so in the line.
