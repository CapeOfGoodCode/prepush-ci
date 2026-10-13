# Tasks

## 1. Reject unusable names

- [x] 1.1 Add a pure check for a variable name (`[A-Za-z_][A-Za-z0-9_]*`) with unit specs for empty, `A=1`, `=A`, `A B`, `MY-VAR`, `1A`, and valid names (`DATABASE_URL`, `_X1`, `a`)
- [x] 1.2 Have config loading report each `require_env` entry that fails it, naming `require_env` and the entry, together with the other problems; verify with unit specs for one bad entry among good ones and for a bad entry next to an unknown key
- [x] 1.3 Verify with integration specs that `doctor` reports the config as invalid for `require_env = [""]`, and that `init --non-interactive --check true --require-env ""` and the interactive answer `A=1` exit 1 and write no file
- [ ] 1.4 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 78-require-env-names`) before the pull request is marked ready.
