Issue: #10

## Why

Many repositories already run their hooks through pre-commit, husky or lefthook. For them the native install of #9 is the wrong tool: a manager that owns `core.hooksPath` or `.git/hooks` fights it, and the hooks would live in a place the team does not look at or commit. Without support, those users must wire the trailer and the pre-push check by hand, which is the first thing to go wrong (#1, section 4.3, `install`; the maintainer's comment on existing setups).

## What Changes

- `prepush-ci install` takes `--hooks native|pre-commit|husky|lefthook`. Without it, the manager is detected from files at the worktree root: none → native (as in #9), one → that manager, several → refused with the reason.
- For a manager, `install` edits the manager's own files, which the team commits: a `local` hook entry for `commit-msg` and `pre-push` in `.pre-commit-config.yaml` (and `default_install_hook_types` made to cover both, with `default_stages` set to the types the file had, so existing hooks do not start running at the new stages), a block at the top of `.husky/commit-msg` and `.husky/pre-push`, commands under `commit-msg:` and `pre-push:` in the lefthook config.
- Everything it adds sits in one block between `# prepush-ci: begin` and `# prepush-ci: end`; every other line is left alone, and a rerun replaces the block. A file whose shape it cannot edit safely is refused, not guessed at.
- The check command is never written into those files; they only call `prepush-ci hook …`, and the check stays in `.prepush-ci.toml`.
- Native hooks and `core.hooksPath` stay untouched when a manager is chosen. `install` does not run the manager; it prints the command that activates it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install`: the choice of hooks, the three managers, and the report; the native requirement and the report requirement are restated for their new conditions.

## Impact

- `src/prepush_ci/`: the `--hooks` option, manager detection, and per-manager editing of text files. The editing is pure text-in, text-out logic, so it lives in `core/` and is unit-tested; the command reads and writes the files.
- No runtime dependencies: the YAML files are edited as lines, not parsed.
- `init` (#12) will call `install --hooks …`; `doctor` (#14) will check what this writes.
