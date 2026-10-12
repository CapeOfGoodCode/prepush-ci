Issue: #14

## Why

When a push is refused or the trailer goes missing, the user sees only the symptom: the interpreter vanished, the config is invalid, another tool took over the hooks, a preflight variable is unset. Without a command that names what is missing and what to run, they disable the hooks or stop trusting the trailer, and the trailer is only worth something while it implies a passed check (#1, section 4.3, `doctor`).

## What Changes

- New command `prepush-ci doctor`. It prints one line per check, in a fixed order: `config`, `commit-msg`, `pre-push`, `preflight`, `PREPUSH_CI` and `up-to-date`, each `ok`, `fail` or `skip`. Every failure is followed by a `fix:` line. It exits 0 only when every check is `ok`.
- The hooks checks look at what git would run: the hooks directory, the executable scripts and the recorded interpreter for native hooks; the block in the manager's file and the manager's own activation for pre-commit, husky and lefthook.
- `doctor --hooks <value>` picks the hooks to check as `install` does, so a repository with two managers can be diagnosed. `doctor --mode full|off|unset` also requires `PREPUSH_CI` to have that value, for a SessionStart hook or the skill that must know the variable is set.
- It never changes the repository: no file, no git config, no fetch.

## Capabilities

### New Capabilities

- `doctor`: what `prepush-ci doctor` checks, reports and exits with.

### Modified Capabilities

None. `doctor` reads what `config` (#4), `install` (#9, #10) and `preflight` (#7) specify and changes none of them.

## Impact

- New: `doctor` subcommand in `src/prepush_ci/` and its pure logic in `core/` (verdicts, report lines, block and hooks-path rules). No runtime dependencies.
- The checks reuse the loaders and the preflight messages that exist; the build decides how to share them.
- The README and `SKILL.md` will mention `doctor` in #15; this change does not edit them.
