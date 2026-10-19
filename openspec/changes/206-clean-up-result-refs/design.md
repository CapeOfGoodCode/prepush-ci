# Design

## Context

Step 2 of #196, the third slice cut from #198: result refs are local (`run-cache`) and shared through `origin` (#205); this change deletes the old ones. `land` (#199) reads what is left, so the rule decides how old a result `land` can still find. Everything here is an addition to `run-cache`; no existing requirement changes.

## Decisions

- **One rule: older than 30 days.** The other rule the issue names, "trees no longer reachable from any branch", needs a walk of every branch for every ref, says nothing about a tree a pull request is about to come back to, and cannot be answered for a ref on `origin` that the clone has no branch for. Age is one number in the ref's own commit. A result reused after 30 days costs one check when it has gone, which is what no cache costs. 30 days covers a pull request left over a holiday and keeps the refs of a busy repository in the hundreds.
- **The age is the commit's committer date, and the tool sets that date.** The commit behind a result ref is made when the pass is recorded (`commit-tree`, fixed identity), and the tool now also fixes its dates to the time of recording: `commit-tree` takes `GIT_COMMITTER_DATE` from the environment, so a pass recorded under an old date would be expired by the very cleanup that follows it. The date is the day of the pass, and `git for-each-ref --format='%(refname) %(committerdate:unix)'` reads all of them in one process. A pass recorded again replaces the ref with a new commit, so a result that keeps being recorded never expires. A date in the future (a clock that was wrong) is not expired, and "older than 30 days" is strict.
- **No config key.** `cache` is the only switch of the cache; a project that needs another age asks for a key later.
- **The cleanup runs when a pass is recorded.** That is after a check ran, minutes of work that dwarf one `for-each-ref`; a hook that skips the check, the common case, does nothing extra, and a repository with thousands of refs pays for them only when it has just paid for a check. A repository that only ever reuses results does not clean up until it records one. Running the cleanup on every hook was rejected for the cost on the fast path; a scheduler for lack of anything that runs on its own.
- **Delete only where both sides can follow: the line #205 draws for publishing.** A result published to `origin` and then deleted from the clone alone would leave the tree on `origin` with no name in any clone that could drop it. So an expired ref is deleted from the clone only together with `origin` (the hook, a push to `origin`), or in a repository that has no `origin` and so shares nothing. `run`, a push to another remote or by url, and a hook that cannot tell the remote delete nothing when the repository has an `origin`; the next push to `origin` that records a pass deletes what has expired by then. Cost: a lefthook install (it publishes nothing and never learns the remote) keeps its expired refs; they are local and cheap. The same line keeps the tool from contacting `origin` in `run`.
- **`origin` first, the clone after.** If the clone dropped its ref first and `origin` then refused, nothing would name the leftover again. The clone drops only the refs `origin` dropped, so a failure leaves the ref where the next push to `origin` finds it and tries again. A delete of a ref `origin` does not hold succeeds (exit 0; the remote prints a warning the tool discards), so no `ls-remote` is needed to find which `origin` has. The push is `git push --no-verify origin :<ref> :<ref> …`, a hundred refs at a time so the command line stays short on Windows; a batch that fails leaves its refs in the clone and warns once.
- **A dry run cleans too.** A `pre-push` hook cannot tell `git push --dry-run origin` or a push that `origin` then declines (#205 draws the same consequence for the publish), so `git push --dry-run origin main` that records a pass deletes expired refs from `origin` and from the clone. Telling them apart is not possible; the deletion is of results older than 30 days, which the cache would drop at the next such pass anyway, so a dry run costs nothing it would not cost later. The README sentence says it.
- **Only refs the clone holds are aged.** A ref on `origin` has a date only in the commit it points at, and reading the commits of thousands of refs means fetching them, trees included. Cost, accepted and stated in the proposal: a ref published by a clone that is gone (a short-lived sandbox) stays on `origin` until some clone fetches it by reuse, and then it is a held ref that expires with the next recorded pass in a push to `origin`. If that proves too many refs in practice, a later change adds a command that reads only the commits.
- **A cleanup that fails is a warning.** It follows a pass that is already recorded, so nothing in the push or the run depends on it. The warning for `origin` names it and says that old results could not be removed from it. A ref whose commit cannot be read stays untouched: the cache already treats it as a miss, and removing what the tool cannot read is how it would one day remove what it should not.
- **The cloud-session proxy.** A session behind a proxy that accepts only branches refuses the delete of a result ref, as it refuses the publish (#205). The warning is the evidence and the clone keeps the ref, which is consistent: that session shares nothing either.
- **Objects stay until `git gc`.** Deleting a ref makes its commit unreachable; git removes it when it next collects garbage. The tool does not run `git gc`.

## Run the tools

git 2.39.5. A bare `remote.git` as `origin`, clone `c`, one ref made on 2026-09-01 and one made today:

```
$ git for-each-ref --format='%(refname) %(committerdate:unix)' refs/prepush-ci/results/
refs/prepush-ci/results/new-x 1792442007
refs/prepush-ci/results/old-x 1788220800                   # one process for all refs
$ git push --no-verify origin :refs/prepush-ci/results/old-x :refs/prepush-ci/results/gone-x
remote: warning: deleting a non-existent ref
 - [deleted]         refs/prepush-ci/results/old-x
 - [deleted]         refs/prepush-ci/results/gone-x        # rc 0, even for a ref origin never held
$ printf 'delete refs/prepush-ci/results/old-x\n' | git update-ref --stdin   # rc 0, any number of lines
```
