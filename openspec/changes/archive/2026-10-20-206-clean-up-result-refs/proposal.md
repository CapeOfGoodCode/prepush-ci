Issue: #206

## Why

Result refs are kept forever (#198) and, since #205, on `origin` too. A busy repository collects one per tree it ever checked, each a commit that holds the whole tree, and nothing removes them (#196, step 2; #199 reads what is left).

## What Changes

- A result ref whose commit is older than 30 days is deleted. The age is the commit's committer date, which the tool sets to the time the pass is recorded.
- A recorded pass is dated when it is recorded, whatever `GIT_COMMITTER_DATE` says, so a cleanup never deletes the pass it follows.
- The cleanup runs whenever the tool records a pass, after the check ran, and never when a result is reused or the check fails. It reads the result refs once and deletes them in batches, however many there are.
- It deletes only where it can do so on both sides, the same line #205 draws for publishing: in the hook, for a push to `origin`, an expired ref is deleted from `origin` and then from the clone. In a repository without `origin`, `run` and the hook delete from the clone. A repository with `origin` deletes nothing in `run`, in a push to another remote or by url, or in a hook that is not told the remote.
- A `git push --dry-run origin` that records a pass cleans too: the hook cannot tell it from a real push (as for the publish in #205).
- A cleanup that fails is a warning on standard error that never changes the exit code or the decision about the push; a ref `origin` could not drop stays in the clone, so the next push to `origin` tries again.
- `cache = false` turns the cleanup off with the rest of the cache.
- Limit: only refs the clone holds are aged; a ref on `origin` that no clone holds stays there until a clone fetches it by reuse. See `design.md`.

## Capabilities

### Modified Capabilities

- `run-cache`: requirements are added for deleting expired result refs when a pass is recorded, and for deleting them from `origin` in a push to `origin`.

## Impact

- `pass_cache.py` gains `expire_passes` (one `git for-each-ref` to read, one `git update-ref --stdin` to delete) and a batched `git push --no-verify origin :<ref> …`; `pre_push_hook.py` and `run_command.py` call it after `record_pass`. `core/run_cache.py` gains the pure rule (which refs are expired at a given time). No config key, no runtime dependency.
- At most one read and one batch of deletions per recorded pass, plus one `git push` per hundred refs to drop from `origin`. A check that just ran costs minutes, so the cleanup is lost in it.
- The README's step 5 gains one sentence on how long a result is kept.
