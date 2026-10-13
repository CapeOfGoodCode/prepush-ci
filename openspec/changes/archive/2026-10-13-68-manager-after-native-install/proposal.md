Issue: #68

## Why

A user who ran `prepush-ci install` before `install` knew hook managers, in a repository that uses pre-commit or lefthook, runs it again (the README says to after an upgrade). `install` now detects the manager and says to run the manager's own activation step. That step refuses while `core.hooksPath` is set, and `core.hooksPath` is still the native hooks directory. The user ends with neither the manager's hooks nor a hint why (#1, section 4.3, `install`).

## What Changes

- `install` for pre-commit or lefthook refuses, before it writes anything, while the local `core.hooksPath` is the native hooks directory. The message says why the manager's activation would refuse, names the command that removes the setting, `git config --local --unset core.hooksPath`, says to run `install` again afterwards, and names the previous hooks directory when removing the setting would stop its hooks from running.
- husky is not refused: its own step (`npx husky`) replaces `core.hooksPath`, so nothing blocks it.
- A `core.hooksPath` that is not ours is not this requirement's business; `install` does as before.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install`: two added requirements about the native hooks directory still being `core.hooksPath` when a manager is chosen, and a modified one ("The other requirements describe native hooks") that names them as the exception.

## Impact

- `src/prepush_ci/install_command.py`: the check before `_install_manager`, using the comparison of `core.hooksPath` with the native directory that the native path already makes.
- `README.md` and the skill say to rerun `install` after an upgrade; their wording follows with #15.
