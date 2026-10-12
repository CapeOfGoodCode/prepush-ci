# Tasks

## 1. Config

- [ ] 1.1 Parse config TOML into a typed config or a list of errors in `src/prepush_ci/core/`, with defaults (per `trailer` sub-key), unknown keys by full path, wrong types, trailer-token and trailer-value checks; verify with unit specs named after every `config` scenario at 100% branch coverage
- [ ] 1.2 Locate the config at the repository root (`.prepush-ci.toml`, else `[tool.prepush-ci]` in `pyproject.toml`) and report missing or malformed files (only the source in use is parsed); verify with integration specs in temporary git repositories, including a run from a subdirectory

## 2. commit-msg hook

- [ ] 2.1 Add `prepush-ci hook commit-msg <file>` handling `PREPUSH_CI` unset, empty, `off`, `full` and other values; verify with integration specs that install it as `.git/hooks/commit-msg` (running `sys.executable -m prepush_ci`) and run real `git commit`
- [ ] 2.2 Write the trailer with `git interpret-trailers --in-place --no-divider --where start --if-exists doNothing`, keep empty messages empty; verify the divider, amend, run-twice and empty-message specs
- [ ] 2.3 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 4-walking-skeleton`) before the pull request is marked ready.
