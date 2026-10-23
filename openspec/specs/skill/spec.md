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
The `<default branch>` step of the skill SHALL give the commands `git remote set-head origin --auto` and then `git symbolic-ref refs/remotes/origin/HEAD`, SHALL tell the agent to remove the leading `refs/remotes/origin/` from the output of the second before passing it to `--default-branch`, and SHALL say that the first refreshes the local record from the remote. The result SHALL be a value `init` accepts, and the branch the remote has as its default.

#### Scenario: A repository with origin/HEAD
- **WHEN** the test runs the hint's commands in a repository whose remote's default branch is `trunk`, removes the leading `refs/remotes/origin/` and runs the `init` invocation of the skill with the result as the default branch
- **THEN** `init` exits 0 and the loaded config's default branch is `trunk`

#### Scenario: A branch name with a slash
- **WHEN** the same happens in a repository whose remote's default branch is `release/1`
- **THEN** `init` exits 0 and the loaded config's default branch is `release/1`

#### Scenario: A local branch named like the remote branch
- **WHEN** the same happens in a repository whose remote's default branch is `trunk` and which also has a local branch `origin/trunk`
- **THEN** `init` exits 0 and the loaded config's default branch is `trunk`

#### Scenario: A record older than a rename
- **WHEN** the same happens in a clone whose `origin/HEAD` names `origin/master` after the remote renamed its default branch to `main` and the clone ran `git fetch --prune origin`
- **THEN** `init` exits 0 and the loaded config's default branch is `main`

#### Scenario: The step says to remove the prefix
- **WHEN** a reader looks at the `<default branch>` step
- **THEN** it names `git remote set-head origin --auto` before `git symbolic-ref refs/remotes/origin/HEAD` and says to remove the leading `refs/remotes/origin/` from the output of the second

### Requirement: Without origin/HEAD the agent asks
The `<default branch>` step SHALL say that the commands fail when `origin` does not exist, cannot be reached, has no default branch, or the clone does not fetch it (a single-branch clone of another branch), and that the agent then asks the user for the name of the default branch and SHALL NOT guess it, nor read a record that was left from before. If the first command fails the agent SHALL NOT use the output of the second.

#### Scenario: A repository without origin/HEAD
- **WHEN** the test runs the hint's first command in a repository without a remote `origin` (so without `origin/HEAD`)
- **THEN** the command exits non-zero

#### Scenario: A remote that cannot be reached
- **WHEN** the test runs the hint's first command in a repository whose `origin/HEAD` names `origin/master` and whose remote `origin` is a path that is not a repository
- **THEN** the command exits non-zero

#### Scenario: A single-branch clone
- **WHEN** the test runs the hint's first command in a clone made with `--single-branch -b feature` of a remote whose default branch is `main`
- **THEN** the command exits non-zero

#### Scenario: The step says to ask
- **WHEN** a reader looks at the `<default branch>` step
- **THEN** it says the commands fail without a reachable `origin` with a default branch that the clone fetches, to ask the user for the default branch instead of guessing it, and not to use the second command's output when the first failed

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

### Requirement: The documentation section has every session show its result on the pull request
The section that the skill has the agent add to `CLAUDE.md` or `AGENTS.md` (the documentation step), which every later session reads, SHALL tell the agent: after a push of a commit with the trailer to a branch with a pull request, run `prepush-ci report --markdown --result passed --tree "$(git rev-parse 'HEAD^{tree}')"` and put its output into the one comment of that check on the pull request. The invocation SHALL pass "Every command in the skill exists".

#### Scenario: The instruction is in the section later sessions read
- **WHEN** a reader looks at the documentation step of the skill
- **THEN** the section it has the agent write holds the instruction to run that command after a push, written as an agent runs it

#### Scenario: Without a pull request
- **WHEN** a reader looks at that instruction
- **THEN** it says to post nothing when the branch has no pull request

#### Scenario: The invocation exists
- **WHEN** the check "Every command in the skill exists" reads the skill
- **THEN** it reports nothing for `report --markdown`

### Requirement: The comment is updated, found by its marker
The instruction SHALL tell the agent to find the comment of the pull request whose body holds the marker line `<!-- prepush-ci:`, followed by the check's name, update it, and create a comment only when none holds the marker. It SHALL tell the agent not to use `--edit-last`, which edits the last comment of the user whatever it says.

#### Scenario: Update, not add
- **WHEN** a reader looks at that instruction
- **THEN** it names the marker `<!-- prepush-ci:`, says to update the comment that holds it and to create one only when none does

#### Scenario: The wrong comment is not edited
- **WHEN** a reader looks at that instruction
- **THEN** it names `--edit-last` as not to be used and says why

### Requirement: The skill proposes the hook that shows the result after every push
After the documentation step the skill SHALL have the agent explain, in a sentence, a Claude Code hook that creates or updates the comment of the check on the pull request after every successful `git push` of a commit with the trailer, and ask the user for a yes. Without the yes the agent SHALL change no file, and the rule of the documentation step stays the fallback for agents without hooks.

#### Scenario: The proposal is made and needs a yes
- **WHEN** a reader looks at the step of the skill that proposes the hook
- **THEN** it says what the hook does, asks the user for a yes before it changes `.claude/settings.json`, and says to change nothing without it

#### Scenario: The rule stays as the fallback
- **WHEN** a reader looks at the step and at the documentation step
- **THEN** the documentation step still holds the instruction to run `report --markdown` after a push, and the proposal says it stays for agents without hooks

### Requirement: The hook is added to the settings
With the user's yes the skill SHALL have the agent add to `.claude/settings.json` one group in `hooks.PostToolUse`: `matcher` `Bash`, a `hooks` list with `{"type": "command", "command": …, "timeout": 30}`, the command running `prepush-ci hook post-push` with the directory `uv tool dir --bin` prints in front of `PATH`. It SHALL keep every other setting and add nothing when a command there already runs `hook post-push`. The invocation SHALL pass "Every command in the skill exists".

#### Scenario: The setting is spelled out
- **WHEN** a reader looks at that step
- **THEN** it shows the group for `hooks.PostToolUse` with the matcher `Bash`, a `timeout` of 30 and a command that runs `prepush-ci hook post-push` with `uv tool dir --bin` in front of `PATH`

#### Scenario: Nothing else changes
- **WHEN** a reader looks at that step
- **THEN** it says to keep every other setting and to add nothing when the hook is there already

#### Scenario: The invocation exists
- **WHEN** the check "Every command in the skill exists" reads the skill
- **THEN** it reports nothing for `hook post-push`

### Requirement: The hook command is silent where the tool is not installed
The command of the hook SHALL run `prepush-ci hook post-push` only when `prepush-ci` is found on the `PATH` it builds, and otherwise SHALL do nothing and exit 0, with nothing on either stream. It SHALL NOT put an empty entry, which the shell reads as the current directory, in front of `PATH` when `uv` is absent, fails or prints no directory.

#### Scenario: The tool is not installed
- **WHEN** the command of the skill's group runs through `sh -c` with a `PATH` that holds no `prepush-ci`, and a payload of a `git push` on standard input
- **THEN** it exits 0 and prints nothing

#### Scenario: The tool is installed
- **WHEN** the command runs with `prepush-ci` in the directory `uv tool dir --bin` prints
- **THEN** it runs `prepush-ci hook post-push` with the payload and exits 0, whatever status that command had

#### Scenario: uv is not installed
- **WHEN** the command runs with a `PATH` that has neither `uv` nor `prepush-ci`, in a directory that holds an executable file `prepush-ci`
- **THEN** it exits 0, prints nothing and does not run that file

#### Scenario: uv prints no directory
- **WHEN** the command runs with a `uv` that exits 0 and prints nothing, and a `PATH` without `prepush-ci`, in a directory that holds an executable file `prepush-ci`
- **THEN** it exits 0, prints nothing and does not run that file

### Requirement: The skill has the check write its result files
After the user has confirmed the check and before `init` runs, the skill SHALL have the agent make the check write a JUnit XML file to `.prepush-ci/junit.xml` at the top of the worktree, and the coverage report of coverage.py as JSON to `.prepush-ci/coverage.json`, each only where the later requirements allow it.

#### Scenario: The step comes after the confirmation and before init
- **WHEN** the steps of the skill are read in order
- **THEN** the item that has the check write the files comes after the one that has the user confirm the check and before the step that runs `init`

#### Scenario: The paths are fixed
- **WHEN** a reader looks at that item
- **THEN** it names `.prepush-ci/junit.xml` and `.prepush-ci/coverage.json`, and says the files are written at the top of the worktree

#### Scenario: Coverage only as coverage.py writes it
- **WHEN** a reader looks at that item
- **THEN** it says the coverage file is the JSON of coverage.py and that a runner that cannot write it gets a JUnit file and no coverage file

### Requirement: The ignore line is added only where a file is written
The skill SHALL have the agent add `.prepush-ci/` to `.gitignore` when the file does not ignore it and at least one of the result files is written (after a yes, for a form that gets files). When no file is written it SHALL NOT touch `.gitignore`.

#### Scenario: The files are ignored
- **WHEN** a reader looks at that item
- **THEN** it says to add `.prepush-ci/` to `.gitignore` unless it is ignored already, because the pre-push hook refuses a worktree with untracked files that are not ignored

#### Scenario: No file, no ignore line
- **WHEN** a reader looks at that item for the cases where no file is written (a "no", several test commands, an entry point, a test command that is not a runner call, a test command that runs in another directory)
- **THEN** it says to leave `.gitignore` as it is

### Requirement: The files come from what the check already has
The skill SHALL have the agent write a JUnit file only through an option the runner has built in that removes or replaces no console output (`pytest --junitxml`), and the coverage file only when the check already measures coverage with coverage.py. It SHALL NOT allow a new dependency, a new plugin, or a start of coverage measurement, and SHALL NOT remove or replace console output in any environment (a line naming a written file is allowed) or replace a result file the check writes.

#### Scenario: No new dependency
- **WHEN** a reader looks at the item that has the check write the files
- **THEN** it says to use an option the runner has built in, and never to add a package or plugin to the project

#### Scenario: The console output loses nothing
- **WHEN** a reader looks at the item for a pytest check
- **THEN** it says the JUnit option adds the file and takes nothing from the console output

#### Scenario: Coverage is not started
- **WHEN** a reader looks at that item
- **THEN** it says to write `.prepush-ci/coverage.json` only when the check already measures coverage with coverage.py, and never to add measurement, because a coverage threshold in the project's configuration would then start to fail the check

#### Scenario: The coverage table stays
- **WHEN** a reader looks at that item for a check that names `--cov` and no `--cov-report`, on its command line or in the runner's configuration
- **THEN** it says to add `--cov-report=term` beside the JSON report, because the JSON report alone replaces the table of uncovered lines that pytest-cov prints by default

#### Scenario: A file the check already writes is left alone
- **WHEN** a reader looks at that item for a check whose command line or runner configuration already writes a JUnit file (`--junitxml`) or a coverage JSON file (`--cov-report=json`)
- **THEN** it says to add no option for that file, because the later option wins and the check would stop writing the project's file, and to tell the user that the check already writes its own file and the comment will show no counts for it

#### Scenario: A runner that chooses its reporters from the environment gets no JUnit file
- **WHEN** a reader looks at that item for a vitest, jest or `node --test` check
- **THEN** it says to write no JUnit file, because a reporter named for the file replaces the reporters that the runner chooses itself from the environment (an agent reporter under an agent, `github-actions` in GitHub Actions) and the console output of the check would change, and to tell the user that the comment will show no counts for that check

### Requirement: A check with more than one test command gets no result files
The skill SHALL have the agent write neither result file when the check, read in its command line or in the `scripts/ci` it wrote, runs tests with more than one command, because the commands would overwrite each other's files and the comment would show part of the tests as the whole. For each file left out, for this or any other reason, it SHALL have the agent tell the user why.

#### Scenario: Several test commands
- **WHEN** a reader looks at that item
- **THEN** it says that when the check runs tests with more than one command, neither file is written, and the agent tells the user that the comment will show no counts for that reason

#### Scenario: A file left out is explained
- **WHEN** a reader looks at that item
- **THEN** it says to tell the user which file is left out and why, and to leave `--junit` or `--coverage` out of the step 8 call for it

### Requirement: The options go only into a check the skill can show
The skill SHALL have the agent add the options only when the test command is in the check command line itself or in a `scripts/ci` that the skill wrote in this run (step 1, item 3). For any other entry point (a script, a Makefile or justfile target, a package script, or a tox or nox session of the project) it SHALL have the agent write neither file, change no file of the project (`.gitignore` included), and tell the user why.

#### Scenario: The command line is the check
- **WHEN** a reader looks at the item for a check that is a command line such as a runner call or a chain of commands
- **THEN** it says to add the options to the test command in that line

#### Scenario: The script the skill wrote
- **WHEN** a reader looks at the item for a `scripts/ci` that the skill wrote in this run
- **THEN** it says to add the options to the line of the script that runs the tests

#### Scenario: An entry point of the project
- **WHEN** a reader looks at the item for `make ci`, `npm run ci`, `just ci`, a `tox` or `nox` session, or a script that existed before this run
- **THEN** it says to write neither file, to change no file of the project, and to tell the user that the entry point is the project's and the comment will show no counts

### Requirement: The options go only after a direct call of the runner
The skill SHALL have the agent add the options only to a test command that is a direct call of `pytest` (also behind `uv run`). When the test command is itself an entry point (a Makefile target, a package script, a tox session, a script), it SHALL have the agent write neither file, change no file of the project, and tell the user why.

#### Scenario: A direct call gets the options
- **WHEN** a reader looks at the item for a test command such as `pytest` or `uv run pytest`
- **THEN** it says to add the options to that call

#### Scenario: A test command that is an entry point
- **WHEN** a reader looks at the item for a check such as `ruff check . && make test` or `npm run lint && npm test`, or a `scripts/ci` of the skill whose test line is `tox -e py`, `npm test` or `make test`
- **THEN** it says to write neither file, to change no file of the project, and to tell the user that the test command is not a call of the runner and the comment will show no counts

#### Scenario: No option is appended to an entry point
- **WHEN** a reader looks at that item
- **THEN** it never has the agent append `--junitxml`, `--reporter` or `--cov-report` to a Makefile target, a package script or a tox session

### Requirement: The options go only where the test command starts at the top of the worktree
The paths of the result files are relative, so the skill SHALL have the agent add the options only when the test command starts in the directory the check starts in, the top of the worktree. When a command changes the directory before the test command starts (a `cd` or `pushd` in the chain or the script, `uv run --directory`, `make -C`), it SHALL have the agent write neither file, change no file of the project (`.gitignore` included), and tell the user why.

#### Scenario: A cd before the test command
- **WHEN** a reader looks at the item for a check such as `cd backend && pytest -q`, or a `scripts/ci` of the skill whose test line follows a `cd`
- **THEN** it says to write neither file, to change no file of the project, and to tell the user that the test command runs in another directory and the comment will show no counts

#### Scenario: A cd that ended before the test command
- **WHEN** a reader looks at the item for a check such as `(cd web && npm run build) && pytest -q`
- **THEN** it says the rule is about the directory in which the test command starts, so the options go to `pytest` here

### Requirement: The check changes only in where it writes
The skill SHALL have the agent show the user the change (the command line with the added options, or the changed line of `scripts/ci`) and ask for a yes before it makes it, and change nothing without it. It SHALL NOT allow a change to what the check checks: the steps, the selection of tests and the thresholds.

#### Scenario: The user is asked
- **WHEN** a reader looks at the item that has the check write the files
- **THEN** it has the agent show the change and ask for a yes before it makes it, and says to leave the check as it is without the yes

#### Scenario: What the check checks does not change
- **WHEN** a reader looks at that item
- **THEN** it says the change adds the files and never changes the steps, the selection of tests or the thresholds of the check

### Requirement: Init stores the check with the options after a yes
The `--check` value that the step running `init` names SHALL be, after a yes, the confirmed command line with the options when the check is a command line, and `scripts/ci` unchanged when the options are in the script. Without a yes it SHALL be the confirmed check unchanged, and the files count as not written and `.gitignore` stays as it is.

#### Scenario: Init gets the changed command line after a yes
- **WHEN** a reader looks at the step that runs `init` for a check that is a command line
- **THEN** the `--check` value it names is the confirmed command with the added options

#### Scenario: Init gets the script after a yes
- **WHEN** a reader looks at the step that runs `init` for a `scripts/ci` that holds the options
- **THEN** the `--check` value it names is `scripts/ci`, unchanged

#### Scenario: A no leaves the check and the call as they are
- **WHEN** a reader looks at the item and at the step that runs `init` for the case that the user said no
- **THEN** the `--check` value is the confirmed check unchanged, the script has no options, and the step 8 call has neither `--junit` nor `--coverage`

### Requirement: The instruction of the documentation section passes the result files
The instruction that the documentation step has the agent add to `CLAUDE.md` or `AGENTS.md` SHALL add `--junit` with the path `"$(git rev-parse --show-toplevel)/.prepush-ci/junit.xml"` and `--coverage` with `"$(git rev-parse --show-toplevel)/.prepush-ci/coverage.json"` to its `prepush-ci report --markdown` call, each only if the check writes that file. The paths are anchored at the top of the worktree because the agent may run the call from a subdirectory, where the relative path does not exist.

#### Scenario: The result files are passed
- **WHEN** a reader looks at that instruction
- **THEN** it passes `--junit` and `--coverage` with those two files and says to pass each only if the check writes it

#### Scenario: The paths do not depend on the directory of the call
- **WHEN** a reader looks at that instruction
- **THEN** each path starts with `"$(git rev-parse --show-toplevel)/`, not with `.prepush-ci/` alone

### Requirement: The instruction leaves out the result files of a pass that did not run the check
The instruction SHALL tell the agent to leave out the result files when the push did not run the check in this run, that is, when the push said the check passed earlier, because the files on disk may belong to another tree.

#### Scenario: A file the push did not write is left out
- **WHEN** a reader looks at that instruction
- **THEN** it says to leave out the result files when the push said the check passed earlier, because the files on disk may belong to another tree

### Requirement: The instruction says the hook and the call share the comment
The instruction SHALL say that the post-push hook, where the repository has it, writes the short comment right after the push and that the agent's call then updates the same comment.

#### Scenario: The hook and the call share the comment
- **WHEN** a reader looks at that instruction
- **THEN** it says the post-push hook writes the short comment right after the push and the agent's call then updates that comment
