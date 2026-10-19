# Tasks

## 1. Date the pass and delete expired results

- [x] 1.1 In `pass_cache._commit_of`, set `GIT_COMMITTER_DATE` and `GIT_AUTHOR_DATE` to the time of recording so the environment cannot date the commit; verify with specs for both `GIT_COMMITTER_DATE` and `GIT_AUTHOR_DATE` 31 days back, the commit dated within a minute of the run, in `run` and in a push to `origin`
- [x] 1.2 In `core/run_cache.py`, add the pure rule (which of a list of `(ref, committer time)` pairs are older than 30 days at a given time); in `pass_cache.py`, read the result refs with one `git for-each-ref` and delete the expired ones with one `git update-ref --stdin`; call it after `record_pass` in `run` and in the hook, only for a repository without `origin`, only when a pass was recorded, and warn without changing the exit code when the deletion fails; verify with specs for an expired ref, a ref 29 days old, a ref dated in the future, a reused result, a failing check, a refusal, `cache = false`, a ref that cannot be read, a push to another remote without `origin`, 2000 expired refs, and a deletion that fails (a lock file next to the ref)

## 2. Delete them from origin

- [x] 2.1 In the hook, for a push to `origin` that recorded a pass, delete the expired refs the clone holds from `origin` with `git push --no-verify origin :<ref> …` in batches of 100, then delete from the clone the refs `origin` dropped; a batch that fails is a warning that names `origin`, and its refs stay; a repository with `origin` deletes nothing in `run`, in a push to another remote or by url, or when the remote is unknown; verify with specs for an expired ref on both sides, a recent ref, a ref only on `origin`, a ref `origin` never held, `git push --dry-run origin`, a push that `origin` declines, a `pre-push` hook that must run once, `run`, another remote, a push by url, an unknown remote, 250 expired refs, a remote that declines the delete, a remote that cannot be reached, and the next push once it accepts

## 3. What the change says to readers

- [ ] 3.1 Add to the README's step 5 that a result is kept for 30 days and when it is deleted (after a pass recorded in a push to `origin`, even a dry run, from `origin` and the clone; in a repository without `origin`, from the clone); run each sentence against the head as `AGENTS.md` asks and put the commands and output into the PR
