Issue: #12

## Why

A developer or an agent in a fresh repository should reach a working setup with one command, not by reading the intent's section 4 and wiring config, hooks and a CI gate by hand. Every manual step is a place to get it wrong, and a half-installed setup either checks nothing or blocks pushes for no visible reason. `init` also has to ask the user what should happen with pre-push locally and to keep existing hooks (#1, section 4.3 and the maintainer's comment).

## What Changes

- New command `prepush-ci init`. Its steps, in order: write `.prepush-ci.toml`, run `install`, write the Claude Code SessionStart hook skeleton (it installs the tool with `uv tool install` and puts it on `PATH`) and register it, print (or write) the CI gate snippet.
- `--non-interactive` takes the flags the skill uses (`--check`, `--preflight`, `--require-env`, `--hooks`, `--default-branch`, `--require-up-to-date`) and asks nothing. Without it, `init` asks for each value with a detected default and asks explicitly what to do about hooks, naming the existing pre-push hook or hook manager it found.
- Running it twice with the same flags changes nothing and says so. An existing config, hook file or settings file is never overwritten.
- `init --hooks none` writes the config and installs no hooks, for a user who wants no local pre-push.

## Capabilities

### New Capabilities

- `init`: what `prepush-ci init` asks, writes and prints, and when it refuses.

### Modified Capabilities

None. `init` calls `install` (#9, #10) and reads the config (#4); it changes neither specification.

## Impact

- New: `init` subcommand in `src/prepush_ci/` and its pure logic in `core/` (config text, settings merge, detection). No runtime dependencies.
- The CI gate snippets are the files of `docs/ci/` (#11); the installed tool must carry them, since `docs/` is not in the wheel. How is for the build to decide; a test keeps both copies equal.
- `skills/prepush-ci-setup/SKILL.md` and the README will call `init` in #15; this change does not edit them.
