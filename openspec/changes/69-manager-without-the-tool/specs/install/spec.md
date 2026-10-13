## ADDED Requirements

### Requirement: A manager's commit-msg entry without the tool
When `prepush-ci` is not found on `PATH`, the `commit-msg` entry that `install` wrote for pre-commit, husky or lefthook SHALL print a warning on standard error that contains `not on PATH`, write no trailer and end with status 0, so the commit goes on. In husky, the lines after the block SHALL still run. When the tool is found, the entry SHALL run it as the other requirements say.

#### Scenario: pre-commit commit without the tool
- **WHEN** `install` and `pre-commit install` ran, `prepush-ci` is not on `PATH`, and `git commit -m "add x"` runs with `PREPUSH_CI=full`
- **THEN** the commit succeeds, its message has no trailer and the output contains `not on PATH`

#### Scenario: lefthook commit without the tool
- **WHEN** `install --hooks lefthook` ran, `prepush-ci` is not on `PATH`, and the `run:` line of the `commit-msg` command, with `{1}` replaced by a message file, runs through `sh` with `PREPUSH_CI=full`
- **THEN** it exits 0, standard error contains `not on PATH` and the message file is unchanged

#### Scenario: lefthook commit-msg finds the tool
- **WHEN** `install --hooks lefthook` ran, `prepush-ci` is on `PATH`, and the `run:` line of the `commit-msg` command, with `{1}` replaced by a message file, runs through `sh` with `PREPUSH_CI=full`
- **THEN** the message file ends with the trailer `Prepush-CI: full` and standard error does not contain `not on PATH`

#### Scenario: husky commit-msg without the tool
- **WHEN** `install --hooks husky` ran, `.husky/commit-msg` has a later line that writes a marker file, `prepush-ci` is not on `PATH`, and `sh .husky/commit-msg <file>` runs
- **THEN** it exits 0, standard error contains `not on PATH`, the message file is unchanged and the marker file exists

#### Scenario: The tool is found
- **WHEN** `install --hooks husky` ran, `prepush-ci` is on `PATH`, and `sh .husky/commit-msg <file>` runs with `PREPUSH_CI=full`
- **THEN** the message file ends with the trailer `Prepush-CI: full` and standard error does not contain `not on PATH`

### Requirement: A manager's pre-push entry without the tool
When `prepush-ci` is not found on `PATH`, the `pre-push` entry that `install` wrote for pre-commit, husky or lefthook SHALL refuse the push with a non-zero status and a message on standard error that contains `not on PATH` and `cannot be checked`. In husky, the lines after the block SHALL NOT run. A commit that carries the trailer may have come from someone who had the tool, so the push must not reach the remote unchecked.

#### Scenario: pre-commit push without the tool
- **WHEN** `install` and `pre-commit install` ran, `prepush-ci` is not on `PATH`, and `git push origin main` pushes a commit
- **THEN** the push is refused, the output contains `not on PATH` and `cannot be checked`, and the remote has no new commit

#### Scenario: lefthook push without the tool
- **WHEN** `install --hooks lefthook` ran, `prepush-ci` is not on `PATH`, and the `run:` line of the `pre-push` command runs through `sh` with a ref line on standard input
- **THEN** it exits non-zero and standard error contains `not on PATH` and `cannot be checked`

#### Scenario: husky pre-push without the tool
- **WHEN** `install --hooks husky` ran, `.husky/pre-push` has a later line that writes a marker file, `prepush-ci` is not on `PATH`, and `sh .husky/pre-push origin <url>` runs with a ref line on standard input
- **THEN** it exits non-zero, standard error contains `not on PATH` and `cannot be checked`, and the marker file does not exist

### Requirement: pre-commit shows the warning of its commit-msg hook
The `commit-msg` hook that `install` adds to `.pre-commit-config.yaml` SHALL set `verbose: true`, because pre-commit hides the output of a hook that passes, and the warning of the previous requirement would never be seen.

#### Scenario: The setting is written
- **WHEN** `install` runs for pre-commit
- **THEN** the `commit-msg` hook of the block holds `verbose: true` and the `pre-push` hook does not

### Requirement: A block of an earlier version gets the guard
When a manager's file holds a block from a version of `install` that did not handle a missing tool, `install` SHALL replace it as "Manager installs are idempotent" says, print `updated`, and leave the lines outside the block as they were.

#### Scenario: An old husky block is replaced
- **WHEN** `.husky/commit-msg` holds the block `prepush-ci hook commit-msg "$1" || exit $?` between the block markers, followed by the line `npm test`, and `install --hooks husky` runs
- **THEN** it prints `updated`, the block now contains `not on PATH` and `npm test` is still the line after it

### Requirement: Every manager entry names the tool's command
Each entry that `install` writes for pre-commit, husky or lefthook SHALL contain `prepush-ci hook <name>`, `<name>` being `commit-msg` or `pre-push`, so that `doctor` and a reader find the tool's command in it. What the entry does when the tool is not on `PATH` is set by "A manager's commit-msg entry without the tool" and "A manager's pre-push entry without the tool".

#### Scenario: The entries contain the command
- **WHEN** `install` runs for pre-commit, for husky and for lefthook
- **THEN** the `commit-msg` entry of each contains `prepush-ci hook commit-msg` and the `pre-push` entry of each contains `prepush-ci hook pre-push`

## MODIFIED Requirements

### Requirement: lefthook entries
For lefthook, `install` SHALL add under `commit-msg:` a command `prepush-ci` that runs `prepush-ci hook commit-msg {1}` and under `pre-push:` a command `prepush-ci` that runs `prepush-ci hook pre-push` with `use_stdin: true`.

#### Scenario: Standard input passed on
- **WHEN** `install` ran for lefthook
- **THEN** the `pre-push` command holds `use_stdin: true`

#### Scenario: The message file is passed on
- **WHEN** `install` ran for lefthook
- **THEN** the `commit-msg` command contains `prepush-ci hook commit-msg {1}`
