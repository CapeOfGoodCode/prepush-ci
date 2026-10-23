## ADDED Requirements

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
