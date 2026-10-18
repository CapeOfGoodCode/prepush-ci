# readme Specification

## Purpose
What `README.md`, the PyPI long description, says a user acts on, and the checks that keep it true against the CLI and the config: every command and option exists, the reference leaves none out, the keys and defaults are the config's, and the agent step's prompt and plugin commands match the CLI and the manifests. The spec checks drift, not prose.

## Requirements

### Requirement: The README uses only what the CLI has
Every `prepush-ci` invocation in a code block or code span of `README.md` SHALL pass the check of the `skill` capability: it SHALL name a command of the CLI and use only options that command accepts.

#### Scenario: The shipped README passes
- **WHEN** the check reads the `README.md` of the repository
- **THEN** it finds no unknown command and no unknown option

#### Scenario: An option the CLI lacks
- **WHEN** the check reads a text with ``prepush-ci run --fast``
- **THEN** it reports `--fast` as unknown to `run`

#### Scenario: A command the CLI lacks
- **WHEN** the check reads a text with ``prepush-ci sync``
- **THEN** it reports `sync` as unknown

### Requirement: The reference lists every command and flag
The README SHALL have a command reference with an entry for each of `init`, `install`, `hook commit-msg`, `hook pre-push`, `run`, `verify`, `strip`, `doctor`, `skill` and `report`, and the check SHALL fail when the CLI has a command the reference has no entry for, or an entry has no code span or block with its `prepush-ci <command>` synopsis. The synopsis of an entry SHALL name every flag the `--help` of that command lists, `-h` and `--help` apart.

#### Scenario: The shipped reference is complete
- **WHEN** the check reads the `README.md` of the repository and the `--help` of the CLI
- **THEN** every command of the CLI has an entry and every flag of each command appears in its synopsis

#### Scenario: A command left out
- **WHEN** the check reads a README text without any entry for `doctor`
- **THEN** it reports that `doctor` has no entry

#### Scenario: A flag left out
- **WHEN** the check reads a README text whose entry for `init` names every flag of `init` but `--no-session-hook`
- **THEN** it reports `--no-session-hook` as missing from `init`

#### Scenario: The report command left out
- **WHEN** the check reads a README text without any entry for `report`
- **THEN** it reports that `report` has no entry

### Requirement: The exit statuses are stated
The entries of `run`, `verify`, `doctor`, `strip` and `report` SHALL state their exit statuses: `run` and `strip` 0 when they did their work and 1 when they refused or failed; `verify` 0 when the commit is verified and 1 otherwise; `doctor` 0 when every check passed and 1 otherwise; `report` 0 when the result was posted, 1 when it refused or failed and 2 when the parser rejects the command line. The entry of `init` SHALL state that it exits 2 when `--check` is missing and no config exists.

#### Scenario: Exit statuses of verify
- **WHEN** a reader looks at the entry of `verify`
- **THEN** it says exit 0 means the commit is verified and exit 1 means it is not

#### Scenario: Exit statuses of doctor
- **WHEN** a reader looks at the entry of `doctor`
- **THEN** it says exit 0 means every check passed and exit 1 that at least one did not

#### Scenario: init without a check
- **WHEN** a reader looks at the entry of `init`
- **THEN** it says `init` exits 2 when `--check` is missing and no config exists

#### Scenario: Exit statuses of run and strip
- **WHEN** a reader looks at the entries of `run` and `strip`
- **THEN** each says exit 0 means it did its work and exit 1 that it refused or failed

#### Scenario: Exit statuses of report
- **WHEN** a reader looks at the entry of `report`
- **THEN** it says exit 0 means the result was posted, exit 1 that it refused or failed and exit 2 that the parser rejected the command line

### Requirement: The README documents PREPUSH_CI and the config keys
The README SHALL document what `PREPUSH_CI` does when it is `full`, `off`, unset or empty, as the `commit-msg-hook` and `pre-push-hook` capabilities specify, and SHALL list every key of `.prepush-ci.toml` with its default in a table of rows `key | default`, including the sub-keys of `trailer`. The set of keys it lists SHALL equal the set the config accepts, read from the `known keys` list of the config's own `unknown key` message, for the top level and for `trailer`.

#### Scenario: The values of PREPUSH_CI
- **WHEN** a reader looks at the README
- **THEN** it says `PREPUSH_CI=full` makes commits get the trailer, an unset or empty variable writes no trailer while a pushed tip that already carries one is still checked, and `PREPUSH_CI=off` writes no trailer and makes the push of a tip that carries one refused

#### Scenario: Off is not a way past the check
- **WHEN** a reader looks at the sentence on `PREPUSH_CI=off`
- **THEN** it contains `refused` and `prepush-ci strip`

#### Scenario: The shipped keys match the config
- **WHEN** the check compares the keys the README documents with the `known keys` lists printed for an unknown top-level key and an unknown `trailer.` key
- **THEN** the two sets are equal

#### Scenario: A key left out
- **WHEN** the check reads a README text that documents every key but `cache`
- **THEN** it reports `cache` as missing

#### Scenario: A key the config does not have
- **WHEN** the check reads a README text that documents a key `timeout`
- **THEN** it reports `timeout` as unknown to the config

### Requirement: The documented defaults are the config's
Each default the README lists SHALL equal what the config loads when only `check` is set: `none` for `preflight`, `[]` for `require_env` and `legacy_keys`, `main` for `default_branch`, `origin/<default_branch>` for `require_up_to_date`, `Prepush-CI` and `full` for `trailer.key` and `trailer.value`, `true` for `cache`.

#### Scenario: The shipped defaults match the config
- **WHEN** the check compares the default the README gives for each key with what the config loads for a config that sets only `check`
- **THEN** each default is equal

#### Scenario: A wrong default
- **WHEN** the check reads a README text that gives `cache` the default `false`
- **THEN** it reports that the default of `cache` is `true`

### Requirement: The agent step names the Claude Code plugin
The agent step SHALL name the Claude Code plugin as the other way to give the agent the skill, with the commands `/plugin marketplace add CapeOfGoodCode/prepush-ci` and `/plugin install prepush-ci@prepush-ci`, in code spans.

#### Scenario: The plugin way
- **WHEN** a reader looks at the agent step
- **THEN** it has the code spans `/plugin marketplace add CapeOfGoodCode/prepush-ci` and `/plugin install prepush-ci@prepush-ci`

#### Scenario: The plugin commands match the manifests
- **WHEN** the check compares the `<plugin>@<marketplace>` of the install command with the plugin name and the marketplace name in `.claude-plugin/marketplace.json`
- **THEN** they are equal

### Requirement: The agent step's prompt runs a command the CLI has and links to no skill on GitHub
The usage section SHALL have a `###` step whose heading names the agent (the agent step), so that the checks can find it. The code block of the agent step SHALL contain the prompt to hand the agent, and the check SHALL find in it the invocation `prepush-ci skill` and no command or option the CLI lacks. The agent step SHALL NOT link to `skills/prepush-ci-setup/SKILL.md` on GitHub: a link to the default branch drifts from the released skill.

#### Scenario: The agent step exists
- **WHEN** the check looks for a `###` step of the usage section whose heading names the agent
- **THEN** it finds exactly one, and reports a problem, not an exception, when it finds none

#### Scenario: No link to the skill on GitHub
- **WHEN** the check takes the links of the agent step
- **THEN** none of them is a link to `skills/prepush-ci-setup/SKILL.md` on the default branch

#### Scenario: The prompt's command exists
- **WHEN** the check reads the code block of the agent step
- **THEN** it finds the invocation `prepush-ci skill` and reports no unknown command or option
