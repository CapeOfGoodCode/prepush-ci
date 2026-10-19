# Design

## Context

`run-cache` says a damaged record is a miss and an unwritable cache is a warning, and the `preflight` capability says a failed fetch refuses the push. A repository whose own `refs/prepush-ci` is damaged triggers both: git's fetch checks that the objects it received connect to every local ref, and it dies on a ref it cannot read. The tool's own namespace thus decides whether a push may go on (#220).

## Decisions

- **The fetch ignores damaged refs; it does not skip, repair or reword.** Skipping the up-to-date step would let a push through unchecked, which `preflight` forbids ("never counts as up to date"). Deleting the broken file would repair the cache but change the "Unwritable cache" state under `run-cache`, which is a file at `refs/prepush-ci`, and the tool would delete something it does not know it wrote. A new message would still refuse a push the cache has no reason to refuse. Ignoring the ref is the only answer that keeps both existing specs true. The tool runs its fetch with `GIT_REF_PARANOIA=0`, which tells git to skip the check of refs it would otherwise die on (git 2.39.5; shown below).
- **Only the tool's fetch changes.** A user's own `git fetch` still fails in that repository; that is git, not the tool, and `doctor` and `verify` do not fetch. The `merge-base` after the fetch reads only the one tracking ref and needs no change (shown below).
- **Any damaged ref, not only the named states.** The variable does not know the namespace; a broken ref elsewhere no longer fails the fetch either. That is the same behavior for the same reason (the tool's check of "up to date" needs one ref).
- **The fetch starts no housekeeping.** `git fetch` runs `gc --auto` and the child inherits `GIT_REF_PARANOIA=0`; gc and prune then treat a broken ref as absent and prune history only that ref holds (reproduced in review). Today such a repository makes the fetch die and loses nothing, so the tool must not be the cause. The fetch runs with `--no-auto-maintenance`, which needs git 2.29 or newer; an older git rejects the option, the fetch fails and the push is refused, which loses nothing.
- **The lookup of #205 is the same trap.** Its `git fetch` of a result ref would fail the same way once a damaged ref exists, and would prune the same way. Whichever of the two changes lands second runs its fetch with both the variable and `--no-auto-maintenance`; this change does not specify it, because the requirement is not on `main` yet.

## Run the tools

git 2.39.5; a bare `remote.git` as `origin`, a clone `work` whose `main` is on `origin`:

```
$ : > .git/refs/prepush-ci             # a regular file
$ git fetch --quiet -- origin '+refs/heads/main:refs/remotes/origin/main'
fatal: bad object refs/prepush-ci
error: ../remote.git did not send all necessary objects            # rc 1
$ GIT_REF_PARANOIA=0 git fetch --quiet -- origin '+refs/heads/main:refs/remotes/origin/main'; echo $?
0                                      # refs/remotes/origin/main is updated
$ mkdir -p .git/refs/prepush-ci/results; : > .git/refs/prepush-ci/results/abc    # an emptied result
$ git fetch ...                        # fatal: bad object refs/prepush-ci/results/abc, rc 1
$ GIT_REF_PARANOIA=0 git fetch ...     # rc 0
$ git merge-base --is-ancestor refs/remotes/origin/main HEAD; echo $?
0                                      # without the variable too
```

Other attempts that did not help: `-c fetch.negotiationAlgorithm=noop`, `-c fetch.fsckObjects=false`, `GIT_REF_PARANOIA=1`, `GIT_NO_REPLACE_OBJECTS=1`. `git update-ref -d` on the emptied ref fails ("reference broken"), so a repair through git is not available either.
