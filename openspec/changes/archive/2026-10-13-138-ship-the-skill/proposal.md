Issue: #138

## Why

Someone who finds prepush-ci on PyPI and wants an agent to set it up has to paste a GitHub URL into the prompt. That skill comes from `main`, not from the version they installed, so it can name commands or options their version lacks, and an agent that can reach the package index but not GitHub cannot read it at all. The wheel does not contain the skill today (#1, the skill that tells an agent to set the tool up).

## What Changes

- A new command `prepush-ci skill` prints the skill of the installed version to standard output. `prepush-ci skill --write` writes it to `.claude/skills/prepush-ci-setup/SKILL.md` of the repository, so the agent (or the user) has it as a project skill. Any agent can then be told: "Run `uvx prepush-ci skill` and follow it."
- The wheel carries `skills/prepush-ci-setup/SKILL.md` itself, as package data, so the command prints the file of the repository, never a copy that can drift. A spec builds the wheel the way the release does and checks the installed command prints the same bytes.
- The repository is a Claude Code plugin marketplace with one plugin, `prepush-ci`, whose only component is that same skill: `.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json` at the repository root, the plugin's source being the repository root, where `skills/` already is. A Claude Code user installs it with `/plugin marketplace add CapeOfGoodCode/prepush-ci` and `/plugin install prepush-ci@prepush-ci`.
- A spec keeps `SKILL.md` single: no second copy of it is tracked outside `.claude/`.

The README part (usage step 1 shows both ways instead of the URL) is #139, which waits for the `readme` spec of #86.

## Capabilities

### New Capabilities

- `skill-command`: `prepush-ci skill` and `--write`, and the wheel that carries the file they read.
- `plugin`: the marketplace and plugin manifests, and the skill staying a single file.

### Modified Capabilities

- `readme`: the command reference lists `skill` among its commands, because its check fails for a CLI command without an entry. The agent step of the usage section is #139, not this change.

The `skill` capability (what the skill says) is untouched, and its command check accepts `skill` and `--write` once they exist.

## Impact

- `src/prepush_ci/`: the `skill` command and its subparser; finding the file is the only I/O, writing it needs the repository root.
- `pyproject.toml`: `[tool.uv.build-backend.data]` (the build setting, not the version).
- New files at the repository root: `.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json`.
- Tests: integration specs for the command, one that builds and installs the wheel, one for the manifests. The wheel spec needs `uv` and the package index to build (the release does the same); CI has both.
- No runtime dependencies.
