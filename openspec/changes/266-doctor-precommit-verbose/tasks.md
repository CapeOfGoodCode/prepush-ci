# Tasks

## 1. The key is required

- [x] 1.1 Read the lines of the `prepush-ci-pre-push` hook in the pre-commit block in `core/doctor_hooks.py` and fail the `pre-push` check without `verbose: true`; verify with unit specs named after the scenarios of "The pre-push hook of a pre-commit block shows its messages"
- [x] 1.2 Add integration specs: a block from before #234 fails with the fix line, and `install` then makes it pass
- [x] 1.3 Name the requirement in the README reference of `doctor` if it lists what the hook checks, and run those sentences against the head

## 2. Archive

- [ ] 2.1 Run `sh scripts/ci` and verify it passes
