Issue: #238

## Why

`init` fails in a repository whose pre-commit config is valid (`repos: []`, which `pre-commit validate-config` accepts): `install` refuses it, after `init` already wrote `.prepush-ci.toml` (#238, found in the trial of #232). A project that starts its hooks with an empty list is the very place a hook manager is first set up.

## What Changes

- `install` accepts `repos: []` (with or without a trailing comment) for pre-commit and turns it into a block list that holds the block. Every other `repos` that is not a block list is still refused and left unchanged.
- A second `init` after a refusal of `install` finishes the setup: the config it wrote stays and is not asked for again. This is what the head does; the change pins it.

## Capabilities

### Modified Capabilities

- `install`: "pre-commit entries" accepts `repos: []`; its scenario "Repos is not a block list" moves to a non-empty flow list and a scenario is added for the empty one.
- `init`: a requirement is added for the second run.

## Impact

- `core/hook_managers.py` (`edit_pre_commit`), the two tests that name `repos: []` as refused, and a test for the second `init`. No config key, no new dependency, no README text.
