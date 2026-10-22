Issue: #266

## Why

With pre-commit, the pre-push hook of the prepush-ci block needs `verbose: true`, or pre-commit drops what a passing hook prints: "not run again" and "not shared through origin" (#234) are invisible. A repository set up before #234 has the old block, and `doctor --mode full` still says all checks passed, so nobody learns that the messages are missing. Found in the final trial of `f815b8d`; the owner wants it fixed before 0.2.0 (#227).

## What Changes

- With pre-commit, the `pre-push` check of `doctor` also requires `verbose: true` on the pre-push hook of the block, and fails with a fix line that names the `install` command that adds it.
- The `commit-msg` check, the other managers and the native hooks are not changed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `doctor`: one requirement is added for the `verbose: true` of the pre-push hook of a pre-commit block.

## Impact

- `_manager_problem` in `core/doctor_hooks.py` and the facts it reads (the file's content is already there); the README reference of `doctor` if it lists what the check requires. No new config key or dependency; `install` is not changed.
