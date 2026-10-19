# Design

## Context

Step 2 of #196, the second of three slices cut from #198: the local result refs are on `main` (`run-cache`); this change shares them through the remote, #206 cleans them up, and `land` (#199) reads what both leave. Everything here is an addition to `run-cache`; no existing requirement changes.

## Decisions

- **A result ref leaves the machine only in a push to `origin`.** A result ref is a parentless commit of the checked tree, so pushing it uploads every file of that tree where any fresh clone can fetch it (shown below). Publishing from `run`, or on a push to a fork or private remote, would send content the user never pushed to `origin`, which can be public: a secret committed by mistake and amended away before the push would stay there. So only the hook publishes, and only when the push it checks goes to `origin`; the tree is then one the push sends to `origin` anyway. Two residues, accepted: if `origin` rejects the push itself after the ref went up (a protected branch, a non-fast-forward), or the push is a `git push --dry-run origin ...`, the tree has reached `origin` as a result ref and the branch has not moved (shown below). git tells a `pre-push` hook of neither, and a hook runs before anything is sent, so it cannot publish after the push. Publishing later instead (only once `origin` holds a commit of the tree) was rejected: it needs a scan of the local result refs against `origin`'s branches on every push, and the first push of a tree, the one a fresh clone wants to find, would share nothing until a second push. Reading the parent process for `--dry-run` was rejected too: it is not portable and the spec could not promise it. The user named `origin` and the tree is one they meant to send there; `cache = false` keeps `origin` out of it. Cost: a pass in a push elsewhere is not shared, and `run` does not publish; the lookup still goes to `origin` for every push, because reading sends nothing out but a tree name.
- **The remote is `origin`.** A result published to a fork would be invisible to a session that looks at `origin`; one fixed answer is what "agree" needs, and `REMOTE = "origin"` already serves `strip`, `init` and the default of `require_up_to_date`. A repository without `origin` shares nothing, silently (no remote is a choice, not a failure). No config key; a project that needs another remote asks for one later.
- **The hook learns the remote from argument 1, then from `PRE_COMMIT_REMOTE_NAME`; if neither is there it publishes nothing.** Git passes the remote name and url to a pre-push hook, but the managers differ: native and husky pass `"$@"`, pre-commit passes nothing and sets `PRE_COMMIT_REMOTE_NAME`, lefthook passes nothing (its `pre-push` line has no `{1}`, and the `install` spec pins that line). `origin` means the *name*: for `git push <url of origin>` git passes the url as both arguments (shown below), so a push by url publishes nothing, the safe side, since a url is not known to be `origin`. Defaulting an unknown remote to `origin` would upload the tree to `origin` on a push to a fork, the leak the first decision closes, so unknown means no publish. Cost: a lefthook install shares nothing, and no warning says so. Adding `{1}` to the lefthook line would modify `install` and leave existing installs as they are until `install` runs again; it is a separate change, not needed for the safety of this one. Lookup does not use the remote of the push, so it works under every manager.
- **The ref is pushed with `--no-verify`.** A push of `refs/prepush-ci/...` starts the `pre-push` hook, which ignores refs outside `refs/heads/` but still costs a process, and any other hook on the machine would see a push it was not written for. The push is the tool's own, so it skips hooks.
- **Publish after the record, and again when a local result is reused, in a push to `origin`.** A publish that failed once (offline, a remote that was down) would otherwise never be retried, because the next push finds the result locally and runs nothing. A repeat push of an unchanged ref costs one round trip (`Everything up-to-date`) and the push that follows goes to the same remote, `origin`.
- **Look up only after a local miss, and ask before fetching.** `git ls-remote origin <ref>` answers "no such ref" with exit 0 and no output, and "cannot reach" with exit 128; `git fetch` of a missing ref also exits 128, so the two could not be told apart from the fetch alone. A found ref is fetched into the same name, and the local check of the tree (`has_pass`) decides, so a ref of another tree on the remote is a miss by the rule that already exists.
- **`run` never uses the remote.** `run` is how to run a flaky check again and already ignores local results; it neither reads nor publishes, and `run_command.py` does not change.
- **A remote that fails is a warning, not a refusal, and the lookup has no time limit of its own.** The hook's push goes to a remote next, and git's transport timeouts apply to both; a limit of ours would be a number to defend and a test that sleeps. The user can interrupt.
- **Whoever can push to `origin` can plant a result.** That is the trust model of the trailer itself (`--no-verify` skips the hook as well); the tree check keeps a planted ref from vouching for another tree, nothing keeps it from vouching for a tree that never passed. The README does not call a shared result proof.
- **A cloud session behind a branch-only proxy shares nothing.** The intent records that Claude Code's proxy rejects pushes of anything but branches. There the publish is refused on every pass and the warning is printed each time; the lookup finds nothing. This change keeps the warning (a user must be able to see why nothing is shared) and does not store results as branches: branches cannot be deleted from such a session, which would leave #206 no way to clean up. If sharing from a cloud session matters, it needs its own decision; the warning is the evidence.

## Run the tools

git 2.39.5. A bare `remote.git` as `origin`, a ref published from clone `a`, looked up from a fresh clone `b`:

```
$ git push --no-verify origin refs/prepush-ci/results/$T-cfg:refs/prepush-ci/results/$T-cfg
 * [new reference]   refs/prepush-ci/results/$T-cfg -> refs/prepush-ci/results/$T-cfg     # rc 0, hook not run
$ git push origin refs/prepush-ci/results/$T-cfg:refs/prepush-ci/results/$T-cfg
HOOK-RAN                                   # a native pre-push hook ran, even for a ref the remote has
Everything up-to-date                      # rc 0
$ git for-each-ref refs/prepush-ci         # in the fresh clone: nothing, a clone fetches heads only
$ git ls-remote origin refs/prepush-ci/results/zzz; echo rc=$?
rc=0                                       # absent: no output, exit 0
$ git ls-remote gone refs/prepush-ci/results/zzz; echo rc=$?     # url names no repository
fatal: '../nowhere.git' does not appear to be a git repository
rc=128
$ git fetch -q origin +refs/prepush-ci/results/$T-cfg:refs/prepush-ci/results/$T-cfg; echo rc=$?
rc=0                                       # the ref is now local
$ git fetch -q origin +refs/prepush-ci/results/$T-nope:refs/prepush-ci/results/$T-nope
fatal: couldn't find remote ref refs/prepush-ci/results/$T-nope     # rc 128, as for an unreachable remote
```

A `pre-receive` hook that exits 1 on `origin`, then a push of a new result ref:

```
remote: refused
 ! [remote rejected] refs/prepush-ci/results/$T-new -> ... (pre-receive hook declined)
error: failed to push some refs to '...'                            # rc 1
```

A repository without `origin`: `git push origin <ref>` exits 128 (`'origin' does not appear to be a git repository`), so the tool checks for the remote first and says nothing when it is absent.

A result ref published from a commit that was never pushed (`origin` holds no branch), read from a fresh clone of `origin`:

```
$ git push --no-verify origin refs/prepush-ci/results/$T-cfg:refs/prepush-ci/results/$T-cfg
$ git show refs/prepush-ci/results/$T-cfg:secret.txt     # in clone b, after fetching the ref
TOKEN=x
$ git for-each-ref                                       # on origin
commit	refs/prepush-ci/results/$T-cfg
```

What git passes a native pre-push hook, git 2.39.5 (from the round-2 review):

```
$ git push origin HEAD:refs/heads/m
pre-push args: [origin] [../remote.git]
$ git push /tmp/.../remote.git HEAD:refs/heads/n
pre-push args: [/tmp/.../remote.git] [/tmp/.../remote.git]
```

What git does with a hook on a dry run and on a declined push, git 2.39.5 (from the round-1 code review; a native `pre-push` hook that prints its arguments, `origin` a bare clone):

```
$ git push --dry-run origin main
pre-push ran: origin ../remote.git          # the hook runs, nothing tells it about --dry-run
To ../remote.git
   3c5a2fc..d1ec3c3  main -> main           # rc 0
$ git -C ../remote.git log --oneline main
3c5a2fc init                                 # the branch has not moved
$ git push origin main                       # origin's pre-receive hook exits 1
pre-push ran: origin ../remote.git
 ! [remote rejected] main -> main (pre-receive hook declined)   # rc 1
```
