# Tasks

## 1. Look up past a damaged ref

- [x] 1.1 Run the lookup's `git fetch` with `GIT_REF_PARANOIA=0` and `--no-auto-maintenance`; verify with specs for an emptied result ref of another key and a ref with a refused name, each reusing the result of `origin`, for a damaged ref of the key's own name and `refs/prepush-ci` as a regular file, each a miss, and for a ref with a refused name that holds the only copy of a commit, failing on `main`, and with the ones of "A result on the remote is reused" and "A remote that fails costs time and nothing else" still passing
- [x] 1.2 Run `sh scripts/ci` and verify it passes
