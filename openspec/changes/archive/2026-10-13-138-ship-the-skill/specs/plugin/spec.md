## ADDED Requirements

### Requirement: The repository is a plugin marketplace
The repository SHALL have `.claude-plugin/marketplace.json`, valid JSON with the marketplace `name` `prepush-ci`, an `owner` with a `name`, and exactly one plugin, named `prepush-ci`, whose `source` is `./`, the repository root.

#### Scenario: The marketplace names the plugin
- **WHEN** the test reads `.claude-plugin/marketplace.json`
- **THEN** its `name` is `prepush-ci`, `owner.name` is a non-empty string, and `plugins` has one entry with `name` `prepush-ci` and `source` `./`

### Requirement: The plugin is the setup skill
The repository root SHALL be a plugin: `.claude-plugin/plugin.json` is valid JSON with the `name` `prepush-ci` and a non-empty `description`, and the skill `skills/prepush-ci-setup/SKILL.md` is its only component. `plugin.json` SHALL NOT have a `version`: the version of the project lives only in `pyproject.toml`. The front matter of `SKILL.md` SHALL have the `name` `prepush-ci-setup`, the name of its directory, and a non-empty `description`.

#### Scenario: The manifest
- **WHEN** the test reads `.claude-plugin/plugin.json`
- **THEN** its `name` is `prepush-ci`, its `description` is non-empty and it has no `version`

#### Scenario: The skill is a component
- **WHEN** the test reads the front matter of `skills/prepush-ci-setup/SKILL.md`
- **THEN** its `name` is `prepush-ci-setup` and its `description` is non-empty

#### Scenario: No other components
- **WHEN** the test lists the directories of the repository root that Claude Code reads components from (`agents/`, `commands/`, `hooks/`, `.mcp.json`, `.lsp.json`)
- **THEN** none of them exists

### Requirement: The skill is a single file
The repository SHALL track exactly one file named `SKILL.md` outside `.claude/` and `openspec/`: `skills/prepush-ci-setup/SKILL.md`. The plugin and the wheel read that file and no copy of it.

#### Scenario: One SKILL.md
- **WHEN** the test lists the tracked files named `SKILL.md` outside `.claude/` and `openspec/`
- **THEN** the list is exactly `skills/prepush-ci-setup/SKILL.md`
