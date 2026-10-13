## ADDED Requirements

### Requirement: The agent step hands the agent the skill command
The usage section SHALL open with a step before the install step that sets a repository up through an agent with the skill. The step SHALL give, in a code block, the prompt to hand the agent; the prompt SHALL ask the agent to run `uvx prepush-ci skill`, follow what it prints, and set prepush-ci up in the repository. The step SHALL NOT link to `skills/prepush-ci-setup/SKILL.md` on GitHub.

#### Scenario: The agent step comes first
- **WHEN** the headings of the usage section are read in order
- **THEN** the agent setup step is the first, before the install step

#### Scenario: A prompt to hand over
- **WHEN** a reader looks at the code block of the agent step
- **THEN** it contains `uvx prepush-ci skill` and asks the agent to follow it and to set prepush-ci up in the repository

#### Scenario: No link to the skill on GitHub
- **WHEN** the check takes the links of the agent step
- **THEN** none of them is a link to `skills/prepush-ci-setup/SKILL.md` on the default branch

#### Scenario: The prompt's command exists
- **WHEN** the check reads the code block of the agent step
- **THEN** it finds the invocation `prepush-ci skill` and reports no unknown command or option

### Requirement: The agent step has a form that runs before the first release
Because the first release is not on PyPI yet, the agent step SHALL also give, in a code span, the form that runs from the repository, `uvx --from git+https://github.com/CapeOfGoodCode/prepush-ci prepush-ci skill`, with the words "until the first release is on PyPI" as the install step has them.

#### Scenario: Before the first release
- **WHEN** a reader looks at the agent step
- **THEN** it has the code span `uvx --from git+https://github.com/CapeOfGoodCode/prepush-ci prepush-ci skill` next to the words "until the first release is on PyPI", and the check finds `prepush-ci skill` in it with no unknown command or option

### Requirement: The agent step names the Claude Code plugin
The agent step SHALL name the Claude Code plugin as the other way to give the agent the skill, with the commands `/plugin marketplace add CapeOfGoodCode/prepush-ci` and `/plugin install prepush-ci@prepush-ci`, in code spans.

#### Scenario: The plugin way
- **WHEN** a reader looks at the agent step
- **THEN** it has the code spans `/plugin marketplace add CapeOfGoodCode/prepush-ci` and `/plugin install prepush-ci@prepush-ci`

#### Scenario: The plugin commands match the manifests
- **WHEN** the check compares the `<plugin>@<marketplace>` of the install command with the plugin name and the marketplace name in `.claude-plugin/marketplace.json`
- **THEN** they are equal

## MODIFIED Requirements

### Requirement: The usage section walks from install to a push
The README SHALL have a usage section. After the agent setup step its steps, in this order, are: install the package; set a repository up with `init`; opt in with `PREPUSH_CI=full`; what a commit does (writes the trailer) and what a push does (refuses a tip with the trailer unless the check passes on it); and the CI gate that skips on the trailer, with a pointer to `docs/ci/` or `init --ci`.

#### Scenario: The steps in order
- **WHEN** the headings and code blocks of the usage section are read in order
- **THEN** the agent setup step comes before the install step, which comes before the `init` step, which comes before the `PREPUSH_CI=full` step, which comes before the step on what a commit and a push do, which comes before the CI gate step

#### Scenario: A step left out
- **WHEN** the check reads a usage section without the step on what a commit and a push do
- **THEN** it reports that step as missing

#### Scenario: The gate step names its source
- **WHEN** a reader looks at the CI gate step
- **THEN** it names `docs/ci/` or `init --ci` and says the default branch always runs CI in full

### Requirement: The agent step names the other way and the manual path
The agent step SHALL name the way to keep the skill with a project: `prepush-ci skill --write`, which writes it to `.claude/skills/` of the repository. It SHALL say that the steps after it are the manual core and name what the skill does on top: it finds or writes the command that runs the full check, sets up the services and the preflight so that a missing service fails the check, extends the SessionStart script with dependencies and services, and proves the setup with `doctor`.

#### Scenario: The skill as a project skill
- **WHEN** a reader looks at the agent step
- **THEN** it names `prepush-ci skill --write` and `.claude/skills/` as the way to keep the skill in a repository

#### Scenario: The manual steps are the core
- **WHEN** a reader looks at the end of the agent step
- **THEN** it says the steps that follow are the manual core, and names the check command, the services and preflight, the SessionStart script and the `doctor` proof as what the skill does on top

## REMOVED Requirements

### Requirement: The usage section starts with the agent setup
**Reason**: Replaced by "The agent step hands the agent the skill command": the prompt no longer carries a link to the skill on GitHub, so its scenarios on the link and the prompt change, and the replacement has a new name instead of a scenario that says the opposite of its name.
**Migration**: None; the new requirement keeps the scenario "The agent step comes first".
