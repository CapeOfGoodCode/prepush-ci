Issue: #4

## Why

The walking skeleton of the first release (#1): the CLI must read its single source of truth, the config, and the `commit-msg` hook must write the trailer that demands the full check (#1 sections 2, 4.2 to 4.4). Every later slice builds on these two.

## What Changes

- The CLI finds and parses the config: `.prepush-ci.toml` at the repository root, else `[tool.prepush-ci]` in `pyproject.toml`. All keys of #1 section 4.4 are parsed with defaults; a missing config, unknown keys and wrong types fail with the key named.
- New command `prepush-ci hook commit-msg <file>`: with `PREPUSH_CI=full` it writes the configured trailer (default `Prepush-CI: full`) with `git interpret-trailers --in-place --no-divider --where start --if-exists doNothing`; with `PREPUSH_CI` unset or `off` it leaves the message alone; any other value is refused.

## Capabilities

### New Capabilities

- `config`: where the config is found, which keys it has, their defaults and how invalid config is reported.
- `commit-msg-hook`: what `prepush-ci hook commit-msg` does to a commit message for each value of `PREPUSH_CI`.

### Modified Capabilities

None.

## Impact

- New: config parsing in `src/prepush_ci/core/` (no I/O, `tomllib` from the standard library), the `hook commit-msg` subcommand in the CLI.
- No runtime dependencies. Installing the hook is out of scope (#9); the pre-push side is #5.
