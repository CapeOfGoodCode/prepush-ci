# Tasks

## 1. Publish

- [x] 1.1 In the hook, push the result ref to `origin` after a pass and when a local result is reused, only when the remote is known to be `origin` (argument 1, else `PRE_COMMIT_REMOTE_NAME`; a url or no value is not `origin`), with `--no-verify` so the push of the ref does not start the hook again; `run` does not publish; a failed push is a warning naming `origin`; verify with specs for a hook pass to `origin`, a native hook that counts its runs, a reused local result that an earlier refused publish left behind, a push to another remote, a push by url, no remote known, the name from `PRE_COMMIT_REMOTE_NAME`, `run`, a failing check, `cache = false`, a repository without `origin` and a remote that refuses the ref, and for the check running once

## 2. Look up

- [x] 2.1 In the hook, when no local result matches, ask `origin` for the ref with `git ls-remote`, fetch it into the same name and let the local check of the tree decide whether it is a hit; print the skip line with `origin` in it; a remote that cannot be reached is a warning and a miss, a remote without the ref is a plain miss; verify with specs for a fresh clone, a ref of another tree on the remote, an unreachable remote, a remote without the ref, `cache = false` and a repository without `origin`

## 3. What the change says to readers

- [x] 3.1 Add to the README's step 5 that a pass in a push to `origin` is shared through `origin` (the tree goes up with the push; `run`, a push elsewhere, a push by url and lefthook share nothing), that a remote which refuses the ref costs a warning, and the `cache` row's reach; run each sentence against the head as `AGENTS.md` asks and put the commands and output into the PR

## 4. A dry run and a declined push (spec round 2)

- [x] 4.1 Verify with specs for `git push --dry-run origin main` and for a push that `origin`'s `pre-receive` hook declines: in both `origin` holds the result ref and its `main` has not moved; no code change is expected beyond what publishing already does
- [ ] 4.2 In the README's step 5, replace "the tree goes up only with that push" with the fact that the tree goes up with a push to `origin` even when it is a `--dry-run` or `origin` declines it, because git does not tell the hook, and that `cache = false` keeps `origin` out of it; run the sentence against the head as `AGENTS.md` asks
