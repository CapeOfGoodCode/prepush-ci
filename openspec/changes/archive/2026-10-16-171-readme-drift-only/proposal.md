Issue: #171

## Why

The `readme` spec pins README prose: what the agent step says, asks or names, the order of the usage steps, the form of its words. So every wording change to the README becomes an OpenSpec change with new tests; #169 deleted four README lines and still needed a proposal, a design, a delta spec and three tests (#170 has the evidence). #170 set the rule on `main`: the spec checks drift, not prose. This change takes the prose out of the spec so the rule holds. The checks that keep the README and the code from drifting apart stay.

## What Changes

- Removed from the `readme` spec, with their tests in `tests/integration/readme_spec.py`: "Each entry says what the command is for", "The agent step names the other way and the manual path", "The agent step says what the agent needs and delivers", "The agent step says what the agent asks", "The usage section walks from install to a push", "The usage section says what to do about a refused push" and "The README says nothing of an unreleased state".
- Narrowed to the drift check as a new requirement (OpenSpec cannot drop scenarios from a modified one): "The agent step hands the agent the skill command" becomes "The agent step's prompt runs a command the CLI has and links to no skill on GitHub". Its kept scenarios and tests keep their names.
- Unchanged: "The agent step names the Claude Code plugin" (as the issue says, with the manifest match and the `marketplace add` and `install` spans), "The README uses only what the CLI has", "The reference lists every command and flag", "The exit statuses are stated", "The README documents PREPUSH_CI and the config keys", "The documented defaults are the config's".
- The Purpose of the spec drops the usage walk (the new text is in `design.md`).
- The new requirement says what the kept checks assumed: the usage section has an agent step. It gets a scenario.
- `README.md` itself does not change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `readme`: eight requirements removed, one added (the narrowed check, with one new scenario).

## Impact

`openspec/specs/readme/spec.md` and `tests/integration/readme_spec.py`. No code of the tool and no README text changes.
