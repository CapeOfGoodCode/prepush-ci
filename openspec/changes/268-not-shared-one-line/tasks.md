# Tasks

## 1. A warning of one line

- [ ] 1.1 Name the cause from git's output in `core/run_cache.py` and build the one-line message; verify with unit specs named after the scenarios of "The warning that a result was not shared is one line"
- [ ] 1.2 Print it from `publish_pass`, with git's lines after it when `PREPUSH_CI_DEBUG` is non-empty; verify with integration specs for the rejected ref, the failed push and the debug scenarios
- [ ] 1.3 Say in the README paragraph on result refs what the warning looks like and what `PREPUSH_CI_DEBUG` does; run the README's sentences against the head

## 2. Archive

- [ ] 2.1 Run `sh scripts/ci` and verify it passes
