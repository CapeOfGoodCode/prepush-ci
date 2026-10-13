## Decisions

- **Refresh with `git remote set-head origin --auto`, not `git ls-remote --symref origin HEAD`.** The skill keeps its `symbolic-ref` command and its prefix removal (#113); `set-head --auto` only makes the local record true. `ls-remote` prints `ref: refs/heads/<branch>\tHEAD`, a second parsing rule for the agent to get wrong. The cost is a write to `.git/refs/remotes/origin/HEAD`, which `git clone` itself does.
- **The agent asks when `set-head --auto` fails, even if the stale record still reads.** An unreachable remote must not fall back to a record that may be the very stale value of #127.
- **`init` checks local remote-tracking branches, not the network.** `init` stays fast and offline; `git fetch --prune` keeps `refs/remotes/origin/*` true. A network call in `init` would hang a setup on a plane for a typo check.
- **The check applies only when `origin` has remote-tracking branches, `origin` has the default fetch refspec and the up-to-date ref is `origin/<branch>`.** A repository without a remote, with an empty or never-fetched one, or whose gate is `upstream/<branch>` (a fork) has no evidence the branch is missing there. In a single-branch or shallow clone (`--single-branch -b feature`, `--depth 1`) the refspec names one branch, so `git fetch origin` never brings `main` in and the remote-tracking branches say nothing about what `origin` has: checking them would refuse a good branch with a remedy that does not work (the terminator's break on this change). A refusal on guesswork would block legitimate setups; the cost is that a typo in such a clone is not caught, and `ls-remote` was rejected for the same reason as above (a network call).
- **The interactive default is not changed.** The question still defaults to the branch `origin/HEAD` names; a stale default is refused when accepted, with the same message, and the user types the right name.

## Tools run

git 2.39.5, against a bare remote whose default branch was renamed `master` to `main` after a clone, then `git fetch --prune origin`:

- `git symbolic-ref refs/remotes/origin/HEAD` still prints `refs/remotes/origin/master`; `git for-each-ref refs/remotes/origin` lists `origin/HEAD` and `origin/main`, no `origin/master`.
- `git remote set-head origin --auto` prints `origin/HEAD set to main`, exits 0; the symbolic ref then prints `refs/remotes/origin/main`.
- With `origin/HEAD` deleted (`git remote set-head origin -d`), `symbolic-ref` exits 128; `set-head --auto` sets it again.
- Without a remote `origin`, or with `origin` pointing at a path that is not a repository: `set-head --auto` exits 128.
- Against an empty cloned remote: `error: Cannot determine remote HEAD`, exit 1, and `git for-each-ref refs/remotes` lists nothing.
- **The readme requirement follows the skill's trigger.** The README said the agent asks when `origin/HEAD` is unset; with `set-head --auto` that is no longer the trigger, and an unreachable `origin` makes the agent ask though `origin/HEAD` is set. The README and the skill name one trigger, so a reader is not told two.
