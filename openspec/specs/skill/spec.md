# skill Specification

## Purpose
What the setup skill (`skills/prepush-ci-setup/SKILL.md`) says an agent to do, and the checks that keep it true against the CLI: every command and option exists, existing hooks are looked at first, the user is asked what pre-push does locally before `init` runs, and `init` writes its own files.

## Requirements

### Requirement: Every command in the skill exists
Every `prepush-ci` invocation in a code block or code span of `skills/prepush-ci-setup/SKILL.md` SHALL name a command of the CLI and SHALL use only options that command accepts. A command SHALL count as existing when `prepush-ci <command words> --help` exits 0, an option when that help lists it.

#### Scenario: The shipped skill passes
- **WHEN** the check reads the `SKILL.md` of the repository
- **THEN** it finds no unknown command and no unknown option

#### Scenario: An option the CLI lacks
- **WHEN** the check reads a text with ``prepush-ci strip --force``
- **THEN** it reports `--force` as unknown to `strip`

#### Scenario: A command the CLI lacks
- **WHEN** the check reads a text with ``prepush-ci sync``
- **THEN** it reports `sync` as unknown

#### Scenario: A nested command
- **WHEN** the check reads a text with ``prepush-ci hook pre-push``
- **THEN** it reports nothing

### Requirement: The verify command is checked by its shape
`verify` is not a subcommand of the parser: `prepush-ci verify --help` exits 1, because `--help` is not a sha. The check SHALL therefore count `verify` as existing when the top-level `prepush-ci --help` lists it, and SHALL accept it with exactly one argument and no option.

#### Scenario: Verify with a sha
- **WHEN** the check reads a text with ``prepush-ci verify "$SHA"`` and the top-level help lists `verify`
- **THEN** it reports nothing

#### Scenario: Verify with an option
- **WHEN** the check reads a text with ``prepush-ci verify --strict "$SHA"``
- **THEN** it reports `--strict` as unknown to `verify`

#### Scenario: Verify without a sha
- **WHEN** the check reads a text with ``prepush-ci verify``
- **THEN** it reports that `verify` takes exactly one sha

### Requirement: The init invocation runs
The `prepush-ci init --non-interactive` invocation in `SKILL.md` SHALL, with each `<placeholder>` replaced by a valid value, exit 0 in a new git repository and write `.prepush-ci.toml`.

#### Scenario: The invocation works
- **WHEN** the test fills the placeholders of that invocation (a check command, a default branch) and runs it in an empty git repository
- **THEN** it exits 0 and `.prepush-ci.toml` exists

### Requirement: The skill lets init write its files
The skill SHALL have the agent run `init` to write the config, install the hooks, write the SessionStart script, register it in `.claude/settings.json` and print the CI gate snippet. It SHALL tell the agent to add dependencies, services and the activation step of the repository's hook manager to the script `init` wrote, and SHALL NOT tell it to create that script, that settings entry or `.prepush-ci.toml` by hand.

#### Scenario: The script is extended
- **WHEN** a reader looks at the SessionStart step of the skill
- **THEN** it says `init` wrote `.claude/hooks/session-start.sh` and names what to add to it, and has no instruction to create the file or to register it in `.claude/settings.json`

#### Scenario: A manager's activation
- **WHEN** a reader looks at the SessionStart step of the skill
- **THEN** it names `pre-commit install` and `lefthook install` as steps to add to the script when the repository uses that manager

### Requirement: The session script does not use uvx
The skill SHALL NOT tell the agent to put `uvx` or `pipx run` into the SessionStart script or into a hook. The script `init` wrote installs the tool with `uv tool install`.

#### Scenario: No uvx in the script step
- **WHEN** a reader looks at the SessionStart step of the skill
- **THEN** the step contains neither `uvx` nor `pipx run`

### Requirement: Existing hooks are looked at first
Before it runs `init`, the skill SHALL have the agent list the hooks the repository already has: `core.hooksPath`, the files `commit-msg` and `pre-push` in the effective hooks directory, and the files of the hook managers (`.pre-commit-config.yaml`, `.husky/`, `lefthook.yml`), and tell the user what it found. When it finds more than one manager, the skill SHALL have the user choose and pass the choice as `--hooks`.

#### Scenario: Look before init
- **WHEN** the steps of the skill are read in order
- **THEN** the step that lists the existing hooks comes before the step with the `init` invocation and names each of the places above

#### Scenario: Two managers
- **WHEN** a reader looks at the step that lists the existing hooks
- **THEN** it says to ask the user which manager to use when there are several, and to pass it as `--hooks`

### Requirement: The skill asks what pre-push should do locally
Before it runs `init`, the skill SHALL stop and ask the user what should happen with pre-push on their own machines, and SHALL NOT continue without an answer. It SHALL offer these answers: keep the existing hooks and run ours after them; install the hooks only in cloud sessions; fold the existing pre-push steps into the full check and remove the old hook.

#### Scenario: The question comes first
- **WHEN** the steps of the skill are read in order
- **THEN** the step with the question comes before the step with the `init` invocation and lists all three answers

#### Scenario: No silent continue
- **WHEN** a reader looks at the question step
- **THEN** it says to wait for the answer before any command that installs hooks

### Requirement: The first answer keeps native hooks
The skill SHALL map the first answer to `init` with the `--hooks` value found. For native hooks it SHALL NOT edit, move or remove `commit-msg` or `pre-push` in the hooks directory.

#### Scenario: Keep, native hooks
- **WHEN** a reader looks at the first answer
- **THEN** it says to run `init` and to leave the existing hook files as they are

### Requirement: The first answer commits what init writes to a manager
For a hook manager the only change to the manager's files SHALL be what `init` writes, every other line staying as it is, and the skill SHALL have the agent commit those changes together with `.prepush-ci.toml`. For pre-commit what `init` writes is the block and the keys `default_install_hook_types` and `default_stages` that the `install` spec names.

#### Scenario: Keep, pre-commit
- **WHEN** a reader looks at the first answer
- **THEN** it says the only changes to `.pre-commit-config.yaml` are the block `init` writes and the keys `default_install_hook_types` and `default_stages`, and that these changes are committed

#### Scenario: Keep, husky or lefthook
- **WHEN** a reader looks at the first answer
- **THEN** it says the only change to the files under `.husky/` or to `lefthook.yml` is the block `init` writes, and that the block is committed

### Requirement: Cloud sessions only is offered for native hooks
The skill SHALL map the second answer to `init` with `--hooks none` and SHALL offer it only when the repository uses no hook manager. With a manager the skill SHALL leave the answer out and say why: the session's `install` would modify the tracked config and leave the worktree dirty so that every push refuses, while committing the block gives the hooks to every developer who runs the manager's install.

#### Scenario: Cloud sessions only, native hooks
- **WHEN** a reader looks at the second answer
- **THEN** it names `--hooks none` and says it applies when no hook manager is in use

#### Scenario: Cloud sessions only, with a manager
- **WHEN** a reader looks at the question step
- **THEN** it says that with a hook manager only the first and the third answer are offered, and gives the reason above

### Requirement: Removing an old hook needs a yes
The skill SHALL map the third answer to a change of an existing hook file only after the agent has shown the file, the user has named it and said yes, and its steps are part of the check command.

#### Scenario: Removing a hook needs a yes
- **WHEN** a reader looks at the third answer
- **THEN** it says to show the file, move its steps into the check command first, and remove the file only after the user confirms it by name

### Requirement: The gate action has the name the repository ships
`SKILL.md` SHALL NOT contain the text `prepush-ci/gate`, and every reference of the form `<owner>/prepush-ci@<ref>` in it SHALL have the owner `CapeOfGoodCode`. The skill SHALL point to the snippet `init` prints (`--ci`) or to `docs/ci/` for the gate.

#### Scenario: No wrong action name
- **WHEN** the check reads `SKILL.md`
- **THEN** the text `prepush-ci/gate` appears nowhere in it, prose included

#### Scenario: The owner of the action
- **WHEN** the check reads `SKILL.md`
- **THEN** every match of `<owner>/prepush-ci@` has the owner `CapeOfGoodCode`

#### Scenario: The gate step names its source
- **WHEN** a reader looks at the CI gate step
- **THEN** it names `docs/ci/` or `init --ci` as the source of the snippet

### Requirement: The gate never skips for forks
The CI gate step of the skill SHALL say that pull requests from forks never skip and that the default branch never skips.

#### Scenario: Forks and the default branch
- **WHEN** a reader looks at the CI gate step
- **THEN** it says pull requests from forks never skip and the default branch never skips

### Requirement: The proof step uses doctor with the mode
The proof step of the skill SHALL run `prepush-ci doctor --mode full` after the exported variables of the SessionStart script are sourced, and SHALL tell the agent to fix everything it reports.

#### Scenario: Doctor in the proof
- **WHEN** a reader looks at the proof step
- **THEN** it contains `doctor --mode full` after the instruction to source the variables

### Requirement: The default branch hint yields a branch name
The `<default branch>` step of the skill SHALL give the command `git symbolic-ref refs/remotes/origin/HEAD` and SHALL tell the agent to remove the leading `refs/remotes/origin/` from its output before passing it to `--default-branch`. The result SHALL be a value `init` accepts.

#### Scenario: A repository with origin/HEAD
- **WHEN** the test runs the hint's command in a repository whose `origin/HEAD` names `origin/trunk`, removes the leading `refs/remotes/origin/` and runs the `init` invocation of the skill with the result as the default branch
- **THEN** `init` exits 0 and the loaded config's default branch is `trunk`

#### Scenario: A branch name with a slash
- **WHEN** the same happens in a repository whose `origin/HEAD` names `origin/release/1`
- **THEN** `init` exits 0 and the loaded config's default branch is `release/1`

#### Scenario: A local branch named like the remote branch
- **WHEN** the same happens in a repository whose `origin/HEAD` names `origin/trunk` and which also has a local branch `origin/trunk`
- **THEN** `init` exits 0 and the loaded config's default branch is `trunk`

#### Scenario: The step says to remove the prefix
- **WHEN** a reader looks at the `<default branch>` step
- **THEN** it names the command and says to remove the leading `refs/remotes/origin/` from its output

### Requirement: Without origin/HEAD the agent asks
The `<default branch>` step SHALL say that the command fails when `origin/HEAD` is unset, and that the agent then asks the user for the name of the default branch and SHALL NOT guess it.

#### Scenario: A repository without origin/HEAD
- **WHEN** the test runs the hint's command in a repository without `origin/HEAD` and then runs the `init` invocation of the skill with `trunk` as the default branch
- **THEN** the command exits non-zero, `init` exits 0 and the loaded config's default branch is `trunk`

#### Scenario: The step says to ask
- **WHEN** a reader looks at the `<default branch>` step
- **THEN** it says the command fails when `origin/HEAD` is unset and to ask the user for the default branch instead of guessing it

### Requirement: The skill has the user confirm the check and works on a branch
Before it runs `init`, the skill SHALL have the agent ask the user to confirm the command that is the full check and the CI steps it covers, and SHALL NOT let it continue without that confirmation. The skill SHALL tell the agent to work on a branch and open a pull request with the result, and not to push to the default branch. The README states both (`readme` capability).

#### Scenario: The check is confirmed
- **WHEN** the steps of the skill are read in order
- **THEN** the step that has the user confirm the check command and the steps it covers comes before the step that runs `init`, and says not to continue without a confirmed check

#### Scenario: Work on a branch
- **WHEN** a reader looks at the opening of the skill
- **THEN** it says to work on a branch, open a pull request with the result and not to push to the default branch

### Requirement: The skill has the agent find the check and set up the services
The skill SHALL have the agent read the CI definitions of the repository and find, or write, one command that runs the steps pull request CI runs. It SHALL have the agent list the services and variables CI provides and put them in the preflight so that a missing service fails the full check, and SHALL NOT allow a suite that skips its tests for a missing service. The README states these (`readme` capability).

#### Scenario: One command for the check
- **WHEN** a reader looks at the first step of the skill
- **THEN** it has the agent read the CI definitions and find or write one command that runs the pull request steps

#### Scenario: A missing service fails the check
- **WHEN** a reader looks at the services and preflight step of the skill
- **THEN** it says a missing service fails the full check and the tests are never skipped for it
