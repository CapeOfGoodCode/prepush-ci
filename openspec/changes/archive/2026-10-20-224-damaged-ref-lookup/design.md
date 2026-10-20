# Design

## Context

`run-cache` says a result on `origin` is reused and a lookup that fails is a miss. `fetch_pass` asks `origin` for the ref (`ls-remote`), then fetches it into the same name and lets `has_pass` decide. git's fetch checks that what it received connects to every local ref and dies on one it cannot read, so with a damaged ref anywhere in the clone the fetch fails, no ref lands and the lookup is a miss without a word (#224). #220 and #221 closed the same trap for the up-to-date fetch of `preflight`, and left the lookup to this change, as its design says.

## Decisions

- **Ignore the damaged ref in the lookup; do not accept the miss.** Accepting it would make the cache cost the whole check in the one state `run-cache` says it must not (a damaged record is a miss *of that record*, not of every record), and a fresh clone reusing a published result is the point of #205. `GIT_REF_PARANOIA=0` is what #221 uses for the same trap, so one rule holds for both fetches.
- **The lookup's fetch starts no housekeeping.** The same reason as in #221: with git told to ignore broken refs, `gc --auto` treats them as absent and prunes history only they hold. The fetch runs with `--no-auto-maintenance` (git 2.29 or newer); an older git rejects the option, the fetch fails and the lookup is a miss, which loses nothing.
- **A fetch that cannot write its target is still a miss.** When the damaged ref has the name of the key, or `refs/prepush-ci` is a regular file, git cannot lock the ref and the fetch fails whatever the variable says. The lookup then is a miss and the check runs; the tool neither repairs nor deletes a file it does not know it wrote (the same reason as in #220). The run that follows records its pass under `Unwritable cache`.
- **No new message.** A failed fetch after a successful `ls-remote` stays silent, as `fetch_pass` documents; the lookup's decision is still made by `has_pass`, so a fetched ref that is not a result of the tree is a miss.

## Run the tools

git 2.39.5; `r.git` holds `refs/prepush-ci/results/k`, the clone `b` has none and an emptied `refs/prepush-ci/results/d`:

```
$ git fetch --quiet origin +refs/prepush-ci/results/k:refs/prepush-ci/results/k; echo $?
fatal: bad object refs/prepush-ci/results/d
error: .../r.git did not send all necessary objects            # rc 1
$ GIT_REF_PARANOIA=0 git fetch --quiet --no-auto-maintenance origin +refs/prepush-ci/results/k:refs/prepush-ci/results/k; echo $?
0                                      # refs/prepush-ci/results/k is now there
$ : > .git/refs/prepush-ci/results/k   # the damaged ref has the name of the key
$ GIT_REF_PARANOIA=0 git fetch --quiet --no-auto-maintenance origin +refs/prepush-ci/results/k:refs/prepush-ci/results/k; echo $?
error: cannot lock ref 'refs/prepush-ci/results/k': ... reference broken      # rc 1
$ rm -r .git/refs/prepush-ci; : > .git/refs/prepush-ci     # a file instead of the namespace
$ GIT_REF_PARANOIA=0 git fetch ...
error: cannot lock ref ...: non-directory in the way                          # rc 1
```
