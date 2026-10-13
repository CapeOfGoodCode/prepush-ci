Issue: #86

## Why

The maintainer asked for a description of every command in the README (comment on #1 and the group chat, 2026-10-13). A reader who lands on the README, which is also the PyPI page, must learn what each command does, when to run it and what it prints or refuses, without reading specs. A README that names a command or a flag the CLI does not have makes setup fail in the field, and one that leaves a command out hides it, so the README is held against the real CLI the way `SKILL.md` is (#15).

Slice 13 of #1: README usage and command reference. Replaces the README bullet that #15 carried.

## What Changes

- New capability `readme`: what the usage section and the command reference of `README.md` SHALL say, and the checks that keep them true against the CLI.
- A test reads every `prepush-ci` invocation in `README.md` with the check of the `skill` capability, and fails on a command or option the CLI does not have; it also fails when a command or a flag of the CLI is missing from the reference, or a config key of the README is not one the config accepts (or the reverse).
- `README.md` gets a usage section that opens with the setup through an agent and the skill (the main use case, review of #122 by the maintainer, 2026-10-13), and a command reference; the "Status: under construction" note stays as it is (not a requirement: it changes with the release).

## Capabilities

### New Capabilities

- `readme`: the content of the usage section and the command reference, and the checks against the CLI.

### Modified Capabilities

- `skill`: four statements `SKILL.md` already makes become requirements, because the README now tells a reader the agent does them: the user confirms the check before `init` runs, the agent works on a branch and opens a pull request, it finds or writes the one command for the check, and a missing service fails the check. No change to `SKILL.md`.

The README describes what `init`, `install`, `run`, `verify`, `strip`, `doctor`, the hooks, `config` and `ci-gate` specify and changes none of them. The rest of the `skill` capability is untouched; only the code of its invocation check is shared (design).

## Impact

- Edited: `README.md`, `tests/integration/skill_spec.py` (its checker moves to one shared place). New: a spec file in `tests/` for the README. No change to `src/`.
- Out of scope: the animation (separate slice); the "Status" note changes only when a release has happened.
