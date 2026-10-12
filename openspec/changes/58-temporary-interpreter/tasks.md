# Tasks

## 1. Report a temporary interpreter

- [x] 1.1 Add a pure function that says whether a path lies inside a directory (whole components, lexical), with unit specs for inside, equal, sibling with a common name prefix and a relative or trailing-separator form
- [x] 1.2 Find uv's cache directory from the environment and platform and have `install` print the warning on standard error when the recorded interpreter is inside it, on every run; verify with integration specs that put the interpreter in a cache found through `UV_CACHE_DIR` (absolute and relative), through `XDG_CACHE_HOME` and through `HOME`, in an unrelated one, and that rerun `install`
- [ ] 1.3 Also compare the cache directory with its symbolic links resolved (a directory that does not exist is used as found); verify with unit specs and integration specs for a linked `UV_CACHE_DIR`, a linked `~/.cache`, a sibling of the link target and a missing directory
- [ ] 1.4 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 58-temporary-interpreter`) before the pull request is marked ready.
