# readme Specification

## Purpose
What `README.md`, the PyPI long description, says a user acts on, and the checks that keep it true against the CLI and the config: every command and option exists, the reference leaves none out, the keys and defaults are the config's, and the usage section walks from the agent setup through install to a push.

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
The README SHALL have a command reference with an entry for each of `init`, `install`, `hook commit-msg`, `hook pre-push`, `run`, `verify`, `strip` and `doctor`, and the check SHALL fail when the CLI has a command the reference has no entry for, or an entry has no code span or block with its `prepush-ci <command>` synopsis. The synopsis of an entry SHALL name every flag the `--help` of that command lists, `-h` and `--help` apart.

#### Scenario: The shipped reference is complete
- **WHEN** the check reads the `README.md` of the repository and the `--help` of the CLI
- **THEN** every command of the CLI has an entry and every flag of each command appears in its synopsis

#### Scenario: A command left out
- **WHEN** the check reads a README text without any entry for `doctor`
- **THEN** it reports that `doctor` has no entry

#### Scenario: A flag left out
- **WHEN** the check reads a README text whose entry for `init` names every flag of `init` but `--no-session-hook`
- **THEN** it reports `--no-session-hook` as missing from `init`

### Requirement: Each entry says what the command is for
Each entry of the reference SHALL say in one sentence what the command does and when to run it, and SHALL show one example invocation. The entries of `hook commit-msg` and `hook pre-push` SHALL say that git calls them, not a person.

#### Scenario: An entry for the hooks
- **WHEN** a reader looks at the entries of `hook commit-msg` and `hook pre-push`
- **THEN** each says that git runs it, and none tells a person to run it

#### Scenario: An example per entry
- **WHEN** the check reads the entry of each command of the reference
- **THEN** each has a code span or block with an invocation of that command

### Requirement: The exit statuses are stated
The entries of `run`, `verify`, `doctor` and `strip` SHALL state their exit statuses: `run` and `strip` 0 when they did their work and 1 when they refused or failed; `verify` 0 when the commit is verified and 1 otherwise; `doctor` 0 when every check passed and 1 otherwise. The entry of `init` SHALL state that it exits 2 when `--check` is missing and no config exists.

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

### Requirement: The usage section starts with the agent setup
The usage section SHALL open with a step before the install step that sets a repository up through an agent with the skill. The step SHALL give, in a code block, the prompt to hand the agent; the prompt SHALL name the skill with an absolute link to `skills/prepush-ci-setup/SKILL.md` on the default branch of the repository and SHALL ask the agent to set prepush-ci up in the repository.

#### Scenario: The agent step comes first
- **WHEN** the headings of the usage section are read in order
- **THEN** the agent setup step is the first, before the install step

#### Scenario: The link names a file of the repository
- **WHEN** the check takes the link to the skill from the agent step and resolves its path against the repository
- **THEN** the link is absolute and the path names an existing file, `skills/prepush-ci-setup/SKILL.md`

#### Scenario: A prompt to hand over
- **WHEN** a reader looks at the code block of the agent step
- **THEN** it contains the link to the skill and asks the agent to set prepush-ci up in the repository

### Requirement: The agent step names the other way and the manual path
The agent step SHALL name the other way to give an agent the skill: copy the folder `skills/prepush-ci-setup/` into `.claude/skills/` of the repository. It SHALL say that the steps after it are the manual core and name what the skill does on top: it finds or writes the command that runs the full check, sets up the services and the preflight so that a missing service fails the check, extends the SessionStart script with dependencies and services, and proves the setup with `doctor`.

#### Scenario: The skill as a project skill
- **WHEN** a reader looks at the agent step
- **THEN** it names `skills/prepush-ci-setup/` and `.claude/skills/` as the way to install the skill in a repository

#### Scenario: The manual steps are the core
- **WHEN** a reader looks at the end of the agent step
- **THEN** it says the steps that follow are the manual core, and names the check command, the services and preflight, the SessionStart script and the `doctor` proof as what the skill does on top

### Requirement: The agent step says what the agent needs and delivers
The agent step SHALL say what the agent needs: a git repository with a remote it can push branches to, and a package index it can reach to install `prepush-ci`. It SHALL say that the agent works on a branch and opens a pull request instead of pushing to the default branch.

#### Scenario: What the agent needs
- **WHEN** a reader looks at the agent step
- **THEN** it names a remote the agent can push branches to and a package index it can reach

#### Scenario: What the agent delivers
- **WHEN** a reader looks at the agent step
- **THEN** it says the agent works on a branch and opens a pull request, and does not push to the default branch

### Requirement: The agent step says what the agent asks
The agent step SHALL say that the agent always stops to ask the user to confirm the full check command and what pre-push should do on their own machines, and asks more only where the repository leaves something open: the hook manager when there are two, the default branch when `origin` is missing, cannot be reached, has no default branch, or the clone does not fetch it (a single-branch clone of another branch), and a yes before it removes a hook.

#### Scenario: What the agent always asks
- **WHEN** a reader looks at the agent step
- **THEN** it says the agent always asks the user to confirm the check command and what pre-push should do locally

#### Scenario: What the agent asks only sometimes
- **WHEN** a reader looks at the agent step
- **THEN** it says the agent also asks which hook manager to use when there are two, for the default branch when `origin` is missing, cannot be reached, has no default branch, or the clone does not fetch it (a single-branch clone of another branch), and for a yes before it removes a hook, and not otherwise

### Requirement: The usage section walks from install to a push
The README SHALL have a usage section. After the agent setup step (previous requirement) its steps, in this order, are: install the package; set a repository up with `init`; opt in with `PREPUSH_CI=full`; what a commit does (writes the trailer) and what a push does (refuses a tip with the trailer unless the check passes on it); and the CI gate that skips on the trailer, with a pointer to `docs/ci/` or `init --ci`.

#### Scenario: The steps in order
- **WHEN** the headings and code blocks of the usage section are read in order
- **THEN** the agent setup step comes before the install step, which comes before the `init` step, which comes before the `PREPUSH_CI=full` step, which comes before the step on what a commit and a push do, which comes before the CI gate step

#### Scenario: A step left out
- **WHEN** the check reads a usage section without the step on what a commit and a push do
- **THEN** it reports that step as missing

#### Scenario: The gate step names its source
- **WHEN** a reader looks at the CI gate step
- **THEN** it names `docs/ci/` or `init --ci` and says the default branch always runs CI in full

### Requirement: The usage section says what to do about a refused push
After the CI gate step the usage section SHALL say what to do when the full check fails or the push is refused. It SHALL name `prepush-ci run` to run the check as the hook would, `prepush-ci doctor` to find a setup fault and `prepush-ci strip` for a push that must go without a check, with one sentence each.

#### Scenario: A refused push
- **WHEN** a reader looks at the step after the CI gate step
- **THEN** it names `prepush-ci run`, `prepush-ci doctor` and `prepush-ci strip` with one sentence each
