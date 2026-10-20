Issue: #224

## Why

A clone whose git directory holds a damaged ref runs the check again on a tree that `origin` already holds a passing result for, and says nothing. The lookup of a result on `origin` fetches the result ref, git dies on the damaged ref, and the failed fetch is read as a miss. The cache is meant to cost time and nothing else; here it costs the whole check (#224). #221 fixed the same trap in the up-to-date fetch only.

## What Changes

- The lookup of a result on `origin` fetches in a way that ignores a damaged ref: a result ref whose file is emptied, or a ref whose name git refuses no longer turns a result `origin` holds into a miss. The fetch starts no auto-maintenance.
- A fetch that cannot write the ref it was asked for (the damaged ref has that very name, or `refs/prepush-ci` is a regular file) stays a miss and the check runs, as for any fetch that fails.

## Capabilities

### Modified Capabilities

- `run-cache`: a requirement is added that a damaged ref in the clone does not make the lookup of a result on `origin` a miss.

## Impact

- `pass_cache.fetch_pass` runs its `git fetch` with the environment variable `GIT_REF_PARANOIA=0` and the option `--no-auto-maintenance` (git 2.29 or newer), as `preflight.py` does since #221. `preflight` does not change. No config key, no new dependency.
