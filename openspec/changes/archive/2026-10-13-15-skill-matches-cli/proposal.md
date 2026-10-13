Issue: #15

## Why

Agents set the tool up by following `skills/prepush-ci-setup/SKILL.md`, in a cloud session where nobody can ask. A skill that names a command, a flag or an action the CLI does not have, or that writes by hand what `init` already writes, fails there or leaves a repository half set up. The maintainer also asked that the skill handle repositories that already have pre-push setups and ask the user what should happen with pre-push locally (comment on #1). The skill exists from the bootstrap and was written before `init`, `strip` and `doctor`; it has to be brought in line with what was built and checked against it (#1, sections 4.1 and 6).

## What Changes

- New capability `skill`: what `SKILL.md` SHALL say and how it is checked against the CLI.
- A test reads every `prepush-ci` invocation in `SKILL.md` and fails on a command or option the CLI does not have; the skill's `init` invocation is run in a scratch repository.
- The skill looks at the existing hooks before it changes anything, stops to ask the user what pre-push should do locally, and maps each answer to a command.
- The skill lets `init` write the config, the hooks, the SessionStart script, its registration and the CI gate snippet, and extends what `init` wrote instead of writing those files again.
- `SKILL.md` is corrected where it differs from the CLI: the action name (`CapeOfGoodCode/prepush-ci@<ref>`, not `prepush-ci/gate@v1`), `uvx` in the SessionStart script (the skeleton installs the tool with `uv tool install`), and the activation step of a hook manager (the skeleton leaves it to the skill).

## Capabilities

### New Capabilities

- `skill`: the content the setup skill SHALL have and the checks that keep it true.

### Modified Capabilities

None. The skill reads what `init` (#12), `install` (#9, #10), `doctor` (#14), `strip` (#13) and `ci-gate` (#11) specify and changes none of them. The README usage section moved to #86.

## Impact

- Edited: `skills/prepush-ci-setup/SKILL.md`. New: a spec file in `tests/` for the checks. No change to `src/`.
- Open fixes that change `install` (#68 to #70) do not change any command or option the skill uses; if one changes what the skill promises, its change amends the skill.
