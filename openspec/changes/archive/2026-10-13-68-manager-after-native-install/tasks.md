# Tasks

## 1. Refuse a manager while the native hooks hold core.hooksPath

- [x] 1.1 Make `install` for pre-commit or lefthook exit 1 before it writes a file when the local `core.hooksPath` is the native hooks directory, with a message that names `core.hooksPath` and `git config --local --unset core.hooksPath`; verify with integration specs for pre-commit and lefthook that cover the refusal (nothing changed), the rerun after the unset, husky unaffected and a `core.hooksPath` that is not ours
- [x] 1.2 Make the refusal name the previous hooks directory and say its hooks will no longer run when it holds a hook and git will not use it once the local value is gone; verify with integration specs for a `custom-hooks` previous directory and for the default `.git/hooks`
- [x] 1.3 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 68-manager-after-native-install`) before the pull request is marked ready.
