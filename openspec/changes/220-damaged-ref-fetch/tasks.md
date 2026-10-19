# Tasks

## 1. Fetch past a damaged ref

- [x] 1.1 Run the up-to-date `git fetch` with `GIT_REF_PARANOIA=0` and `--no-auto-maintenance`; verify with specs for `refs/prepush-ci` as a regular file, for an emptied result ref and for a ref with a refused name, each with `run` and with the hook, and for a ref with a refused name that holds the only copy of a commit, failing on `main`, and with the ones of "The fetch must succeed" and "A refused fetch names a way out" still passing
- [ ] 1.2 Run `sh scripts/ci` and verify it passes
