# Tasks

## 1. Pin the first-line reading

- [x] 1.1 Add a spec that reads a `--mypy` file made with `--pretty` (a wrapped message, a source line, a caret line) and checks one annotation holding the first line of the message; verify it passes on the head without a code change
- [x] 1.2 Add one sentence to the reference of `report` in the README: run mypy without `--pretty` for `report`, since only the first line of a message is read; verify with a spec that reads the README
- [x] 1.3 Run `sh scripts/ci` and verify it passes
