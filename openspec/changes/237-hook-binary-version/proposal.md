Issue: #237

## Why

The files of a hook manager start the tool as `prepush-ci`, found on `PATH`. Running `install` or `doctor` of a newer prepush-ci (through `uvx`, say) leaves an older `prepush-ci` on `PATH` as the one the hooks run, and `doctor` reports everything `ok`: the user believes the hook now runs the new version (#237, found in the trial of #232).

## What Changes

- For the hooks of a manager, the `commit-msg` and `pre-push` checks of `doctor` look up `prepush-ci` on `PATH` the way the hook does, ask it for its version, and compare it with doctor's own.
- Their lines name the executable and its version, whether they pass or not. A different version, no executable, or one that does not say its version fails the check with a fix.
- Native hooks, `--hooks none` and a manager whose block or activation is already missing are not affected: the native scripts pin the interpreter, and the failure that is already there stands.

## Capabilities

### Modified Capabilities

- `doctor`: a requirement is added for the executable that a manager's hooks find on `PATH`.

## Impact

- `doctor_command.py` (a `PATH` lookup and a `--version` subprocess, both outside `core/`), the pure comparison and the wording in `core/doctor_hooks.py`, unit and integration specs with a stub `prepush-ci` on `PATH`. No config key, no new dependency, no README text. `install` is unchanged: it still prints `next: run pre-commit install`, which the issue's title does not ask to change.
