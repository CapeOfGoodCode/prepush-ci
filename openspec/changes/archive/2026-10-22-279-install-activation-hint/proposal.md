Issue: #279

## Why

With pre-commit, `install` always ends with `next: run `pre-commit install` to activate the hooks`, even when pre-commit's hooks are already active and `doctor` says so. A user or an agent then runs a command that is not needed, or doubts that the setup works. Found in the retest of `e84c2467e110`; the owner wants it fixed before 0.2.0 (#227).

## What Changes

- For pre-commit and lefthook, `install` prints the activation command only when the hooks of the manager are not active, by the same test `doctor` applies (the hook files `commit-msg` and `pre-push` in the hooks directory exist, are executable and contain the manager's name). When they are active it prints no activation line.
- Husky is unchanged: it never printed one.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install`: the requirement "The manager report" prints the activation command unless the hooks are active; the new requirement "Active hooks" says when they are, with the scenarios for the active and the half-active cases (split so that a requirement stays under 500 characters, which `openspec validate --strict` demands of the merged spec).

## Impact

- `manager_report` in `core/hook_managers.py` (it gets the facts about the hook files, which `doctor` already reads) and the `install` command that calls it; the README and `SKILL.md` if a sentence says `install` always prints the step. The `init` spec says `install` prints the step and the skill owns it, which stays true. No new config key or dependency.
