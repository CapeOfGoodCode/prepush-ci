## ADDED Requirements

### Requirement: The choice of hooks
`prepush-ci install` SHALL accept `--hooks` with one of `native`, `pre-commit`, `husky` or `lefthook`; any other value SHALL exit 2 and the message SHALL list the four. Without `--hooks` it SHALL look at the worktree root for `.pre-commit-config.yaml` (pre-commit), a directory `.husky` (husky), and `lefthook.yml`, `lefthook.yaml`, `.lefthook.yml` or `.lefthook.yaml` (lefthook): none found means native, one found means that manager.

#### Scenario: Detected pre-commit
- **WHEN** `.pre-commit-config.yaml` exists and `install` runs without `--hooks`
- **THEN** the file holds the block of the next requirements and `core.hooksPath` is unset

#### Scenario: Detected husky
- **WHEN** the directory `.husky` exists and `install` runs without `--hooks`
- **THEN** `.husky/commit-msg` and `.husky/pre-push` hold the block and `core.hooksPath` is unset

#### Scenario: Detected lefthook under a dotted name
- **WHEN** `.lefthook.yaml` exists and `install` runs without `--hooks`
- **THEN** that file holds the block and `lefthook.yml` was not created

#### Scenario: No manager
- **WHEN** none of those files exist and `install` runs without `--hooks`
- **THEN** `core.hooksPath` is the native hooks directory, as after any native install

#### Scenario: Native forced
- **WHEN** `.pre-commit-config.yaml` exists and `install --hooks native` runs
- **THEN** `core.hooksPath` is the native hooks directory and `.pre-commit-config.yaml` has the same contents as before

#### Scenario: Unknown value
- **WHEN** `install --hooks jenkins` runs
- **THEN** it exits 2 and the message contains `native`, `pre-commit`, `husky` and `lefthook`

### Requirement: Several managers are refused
When `--hooks` is absent and files of more than one manager are found, `install` SHALL exit 1, change nothing and name the managers found and the option `--hooks` in its message. With `--hooks` given, only that manager's files SHALL be read or changed.

#### Scenario: Two managers detected
- **WHEN** `.pre-commit-config.yaml` and `lefthook.yml` both exist and `install` runs without `--hooks`
- **THEN** it exits 1, the message contains `pre-commit`, `lefthook` and `--hooks`, and neither file changed

#### Scenario: The option settles it
- **WHEN** `.pre-commit-config.yaml` and `lefthook.yml` both exist and `install --hooks lefthook` runs
- **THEN** `lefthook.yml` holds the block and `.pre-commit-config.yaml` has the same contents as before

### Requirement: A named manager must be set up
`install --hooks <manager>` SHALL exit 1 and create nothing when the manager's files are missing: `.pre-commit-config.yaml` for pre-commit, the directory `.husky` for husky, one of the four lefthook file names for lefthook. The message SHALL name the missing file or directory.

#### Scenario: No pre-commit config
- **WHEN** `install --hooks pre-commit` runs in a repository without `.pre-commit-config.yaml`
- **THEN** it exits 1, the message names `.pre-commit-config.yaml` and no file was created

#### Scenario: No husky directory
- **WHEN** `install --hooks husky` runs in a repository without `.husky`
- **THEN** it exits 1, the message names `.husky` and the directory was not created

### Requirement: A manager leaves git alone
When the chosen hooks are those of a manager, `install` SHALL NOT change any git config and SHALL NOT write into the git directory.

#### Scenario: Git config and hooks directory unchanged
- **WHEN** `.pre-commit-config.yaml` exists and `install --hooks pre-commit` runs
- **THEN** `core.hooksPath` has the value it had before (unset), and `.git/hooks` and `.git/prepush-ci` hold no new file

### Requirement: One block, nothing else
Every change `install` makes to a file of a manager SHALL be one block per file that starts with the line `# prepush-ci: begin` and ends with the line `# prepush-ci: end`, except the keys `default_install_hook_types` and `default_stages` of pre-commit. Every line of the file outside the block SHALL stay as it was. When the file already holds the block, `install` SHALL replace its lines and no other.

#### Scenario: Existing content is kept
- **WHEN** `.husky/pre-push` holds the lines `npm test` and `# keep me`, and `install --hooks husky` runs
- **THEN** the lines after the block are `npm test` and `# keep me`, unchanged

#### Scenario: A hand edit of the block is undone
- **WHEN** `install` ran, a line inside the block of `lefthook.yml` was changed by hand and `install` runs again
- **THEN** the second run prints `updated`, the block has the lines of the first run and the lines outside it are unchanged

### Requirement: Entries are portable
The lines `install` writes for a manager SHALL start the tool as `prepush-ci`, found on `PATH`, and SHALL NOT contain the path of an interpreter, of the repository or of the home directory. The check command of `.prepush-ci.toml` SHALL NOT be written into any file of a manager.

#### Scenario: No local path
- **WHEN** `install` ran for each of the three managers
- **THEN** the written block contains `prepush-ci hook` and contains neither the repository's absolute path nor the path of the interpreter that ran `install`

#### Scenario: The check is not duplicated
- **WHEN** `.prepush-ci.toml` sets `check = "scripts/ci"` and `install --hooks pre-commit` runs
- **THEN** the file contains no `scripts/ci` and no `args:` line in the block

### Requirement: pre-commit entries
For pre-commit, `install` SHALL add to the end of the `repos:` list a `- repo: local` entry with a hook for the `commit-msg` stage that runs `prepush-ci hook commit-msg` (pre-commit appends the message file) and a hook for the `pre-push` stage that runs `prepush-ci hook pre-push` with `pass_filenames: false` and `always_run: true`. Both hooks SHALL use `language: system`. `repos:` SHALL be a block list; otherwise `install` SHALL exit 1, naming `repos`, and change nothing.

#### Scenario: Trailer written through pre-commit
- **WHEN** `install` ran for a `.pre-commit-config.yaml` that lists another hook, `pre-commit install` ran, and `git commit -m "add x"` runs with `PREPUSH_CI=full`
- **THEN** the commit's message ends with the trailer `Prepush-CI: full` and the other hook ran

#### Scenario: Check run on push through pre-commit
- **WHEN** `install` and `pre-commit install` ran, the config's `check` writes a marker file, and `git push origin main` pushes a clean, checked-out commit that carries the trailer
- **THEN** the marker file exists and the push reaches the remote

#### Scenario: Failing check refuses the push through pre-commit
- **WHEN** `install` and `pre-commit install` ran, the config's `check` exits 1, and `git push origin main` pushes a clean, checked-out commit that carries the trailer
- **THEN** the push is refused and the remote has no new commit

#### Scenario: Entry goes after the existing repos
- **WHEN** `.pre-commit-config.yaml` lists two repos, followed by the key `exclude: '^vendor/'`, and `install` runs
- **THEN** the block follows the second repo and precedes `exclude`, with the indentation of the other `- repo:` lines, and both repos and `exclude` are unchanged

#### Scenario: Repos is not a block list
- **WHEN** `.pre-commit-config.yaml` contains `repos: []` and `install` runs
- **THEN** it exits 1, the message names `repos` and the file has the same contents as before

### Requirement: pre-commit installs both hook types
For pre-commit, `install` SHALL make `default_install_hook_types` contain `commit-msg` and `pre-push`. When the key is absent it SHALL add `default_install_hook_types: [pre-commit, commit-msg, pre-push]` before `repos:`. When it is a one-line flow list or a block list it SHALL append the missing ones and keep the others in order. When it has another form it SHALL exit 1, name the key and change nothing.

#### Scenario: Key absent
- **WHEN** `.pre-commit-config.yaml` has no `default_install_hook_types` and `install` runs
- **THEN** it holds `default_install_hook_types: [pre-commit, commit-msg, pre-push]` and `pre-commit install` installs the three hook types

#### Scenario: Flow list lacking one
- **WHEN** the file contains `default_install_hook_types: [pre-commit, pre-push]` and `install` runs
- **THEN** it contains `default_install_hook_types: [pre-commit, pre-push, commit-msg]`

#### Scenario: Block list lacking both
- **WHEN** the file lists `pre-commit` as the only item of a block-style `default_install_hook_types` and `install` runs
- **THEN** the list holds `pre-commit`, `commit-msg` and `pre-push`, in that order, each on its own line

#### Scenario: Unsupported form
- **WHEN** the file contains `default_install_hook_types: pre-push` and `install` runs
- **THEN** it exits 1, the message names `default_install_hook_types` and the file has the same contents as before

### Requirement: pre-commit hooks stay where they ran
When `install` adds `commit-msg` or `pre-push` to `default_install_hook_types` and the file has no `default_stages`, it SHALL add `default_stages` before `repos:`, set to the hook types the file had before `install` (`[pre-commit]` when the key was absent), so hooks without `stages:` keep running at the stages they ran at. It SHALL NOT add or change `default_stages` otherwise. The hooks of the block name their stage and are not affected.

#### Scenario: An existing hook runs once per commit and never on push
- **WHEN** the file lists a `local` hook `lint` without `stages` that appends a line to a log file, `install` and `pre-commit install` ran, and a commit and a push run
- **THEN** the log holds one line after the commit and still one after the push

#### Scenario: Types the team already used
- **WHEN** the file has `default_install_hook_types: [pre-commit, pre-push]`, no `default_stages`, and a `local` hook `lint` without `stages` that appends a line to a log file, and `install` and `pre-commit install` ran
- **THEN** the file contains `default_stages: [pre-commit, pre-push]`, and a commit and a push each add one line to the log

#### Scenario: Stages already chosen
- **WHEN** the file contains `default_stages: [pre-commit, pre-push]` and `install` runs
- **THEN** that line is unchanged

#### Scenario: Hook types already covered
- **WHEN** the file has no `default_stages` and `default_install_hook_types: [pre-commit, commit-msg, pre-push]` and `install` runs
- **THEN** the file has no `default_stages`

### Requirement: husky entries
For husky, `install` SHALL put a block into `.husky/commit-msg` and `.husky/pre-push` before every line the file holds, after a first line that starts with `#!`, so the block runs whatever the lines after it do. The block in `.husky/commit-msg` SHALL run `prepush-ci hook commit-msg "$1"`. A missing hook file inside `.husky` SHALL be created executable, starting with `#!/usr/bin/env sh`.

#### Scenario: Hook files created
- **WHEN** `.husky` holds no hook files and `install` runs
- **THEN** `.husky/commit-msg` and `.husky/pre-push` exist, start with `#!/usr/bin/env sh` and hold the block

#### Scenario: Shebang stays first
- **WHEN** `.husky/pre-push` starts with `#!/bin/sh` followed by `npm test` and `install` runs
- **THEN** the first line is still `#!/bin/sh`, the block follows it and `npm test` follows the block

#### Scenario: The commit-msg file writes the trailer
- **WHEN** `install --hooks husky` ran and `sh .husky/commit-msg <file>` runs with `PREPUSH_CI=full` on a message file
- **THEN** the message file ends with the trailer `Prepush-CI: full`

### Requirement: The husky pre-push block cannot be skipped
The block in `.husky/pre-push` SHALL run `prepush-ci hook pre-push "$@"` with git's standard input and, when it fails, end the hook with its exit status before any line after it. It SHALL leave the same standard input for the lines after it, which SHALL run whether or not they read it.

#### Scenario: The pre-push file runs the check
- **WHEN** `install --hooks husky` ran, the config's `check` writes a marker file, and `sh .husky/pre-push origin <url>` runs with git's ref line for a checked-out commit with the trailer on standard input
- **THEN** the marker file exists

#### Scenario: A failing check stops the hook
- **WHEN** `install --hooks husky` ran, the config's `check` exits 1, `.husky/pre-push` has a later line that writes a marker file, and the hook runs with a ref line for a checked-out commit with the trailer
- **THEN** it exits non-zero and the later line did not run

#### Scenario: A later line that reads standard input
- **WHEN** `.husky/pre-push` has a later line that copies its standard input to a file, the config's `check` exits 1, and the hook runs with a ref line for a checked-out commit with the trailer
- **THEN** the check ran and the hook exits non-zero

#### Scenario: Later lines still get the refs
- **WHEN** `.husky/pre-push` has a later line that copies its standard input to a file, the check passes, and the hook runs with a ref line
- **THEN** the file holds that ref line

#### Scenario: A later line that ends the hook
- **WHEN** `.husky/pre-push` has the later line `exit 0`, the config's `check` exits 1, and the hook runs with a ref line for a checked-out commit with the trailer
- **THEN** the check ran and the hook exits non-zero

### Requirement: lefthook entries
For lefthook, `install` SHALL add under `commit-msg:` a command `prepush-ci` that runs `prepush-ci hook commit-msg {1}` and under `pre-push:` a command `prepush-ci` that runs `prepush-ci hook pre-push` with `use_stdin: true`.

#### Scenario: Standard input passed on
- **WHEN** `install` ran for lefthook
- **THEN** the `pre-push` command holds `use_stdin: true`

#### Scenario: The message file is passed on
- **WHEN** `install` ran for lefthook
- **THEN** the `commit-msg` command runs `prepush-ci hook commit-msg {1}`

### Requirement: Where the lefthook entries go
A hook key that the lefthook file lacks SHALL be added at the end of the file with its `commands:`. A key that exists SHALL get the block as the first entry of its block-style `commands:`, with the indentation of the entries after it. A key that exists without such a `commands:` SHALL make `install` exit 1, name the key and `commands`, and change nothing.

#### Scenario: Hook keys added
- **WHEN** `lefthook.yml` holds only a `pre-commit:` section and `install` runs
- **THEN** the file keeps that section unchanged and ends with a `commit-msg:` and a `pre-push:` section holding the block

#### Scenario: Existing commands are kept
- **WHEN** `lefthook.yml` has `pre-push:` with `commands:` holding the command `test`, and `install` runs
- **THEN** the command `test` is unchanged, the block is under the same `commands:` with the same indentation, and the file parses as YAML with both commands under `pre-push`

#### Scenario: A hook without commands
- **WHEN** `lefthook.yml` has `pre-push:` with `jobs:` and no `commands:`, and `install` runs
- **THEN** it exits 1, the message names `pre-push` and `commands`, and the file has the same contents as before

### Requirement: Manager installs are idempotent
Running `install` again for a manager SHALL write no file when nothing differs, print a line containing `already installed` and exit 0. When the block or the hook types differ it SHALL write the difference and print `updated`. A first run SHALL print `installed`. A refused run SHALL write no file of the manager, also when it would have changed another one first.

#### Scenario: Second run for each manager
- **WHEN** `install` runs twice in a row for pre-commit, husky and lefthook, each in its own repository
- **THEN** each second run exits 0, prints `already installed`, and every file has the same contents and modification time as after the first run

#### Scenario: First run
- **WHEN** `install` runs for the first time for a manager
- **THEN** the output contains `installed` and not `already installed`

#### Scenario: Refusal after a part is done
- **WHEN** `.husky/commit-msg` is missing, `.husky/pre-push` is a directory and `install --hooks husky` runs
- **THEN** it exits 1 and `.husky/commit-msg` was not created

### Requirement: The manager report
For a manager, `install` SHALL print each file it checked or wrote, relative to the worktree root. For pre-commit it SHALL print the command `pre-commit install` and for lefthook `lefthook install` as the step that activates the hooks; for husky it SHALL print no activation command.

#### Scenario: Report for pre-commit
- **WHEN** `install` runs for pre-commit
- **THEN** the output names `.pre-commit-config.yaml` and contains `pre-commit install`

#### Scenario: Report for husky
- **WHEN** `install` runs for husky
- **THEN** the output names `.husky/commit-msg` and `.husky/pre-push` and contains no activation command

### Requirement: The other requirements describe native hooks
The requirements of this specification about the hooks directory, the previous directory, forwarding, the recorded interpreter and `core.hooksPath` SHALL describe the native hooks only. For a manager, `install` SHALL NOT create the hooks directory or the files `python` and `previous`.

#### Scenario: No native files for a manager
- **WHEN** `install --hooks husky` ran in a repository whose `.git/hooks/pre-push` exists
- **THEN** the directory `prepush-ci/hooks` of the git directory does not exist and `.git/hooks/pre-push` is unchanged

## MODIFIED Requirements

### Requirement: The tool is found without PATH
The native scripts SHALL start the tool as `<python> -m prepush_ci`, where `<python>` is the interpreter that ran `install`, recorded in the file `python` of the hooks directory. They SHALL NOT look up `prepush-ci` on `PATH`. The files of a manager are not native scripts; they start `prepush-ci` from `PATH`.

#### Scenario: prepush-ci is not on PATH
- **WHEN** `install` ran from an interpreter whose scripts directory is not on `PATH`, and a commit runs with `PREPUSH_CI=full`
- **THEN** the commit's message ends with the trailer

### Requirement: Native hooks through core.hooksPath
When the chosen hooks are native (the requirement "The choice of hooks"), `prepush-ci install` SHALL write the scripts `commit-msg` and `pre-push` into the directory `prepush-ci/hooks` of the repository's common git directory, make them executable and set the repository's local `core.hooksPath` to that directory's absolute path. The `commit-msg` script SHALL run `prepush-ci hook commit-msg` with the arguments git passes; the `pre-push` script SHALL run `prepush-ci hook pre-push` with the arguments and standard input git passes. No file of the worktree SHALL change.

#### Scenario: Trailer written after install
- **WHEN** `install` ran in a repository without any hook and `git commit -m "add x"` runs with `PREPUSH_CI=full`
- **THEN** the commit's message ends with the trailer `Prepush-CI: full`

#### Scenario: Check run on push after install
- **WHEN** `install` ran, the config's `check` writes a marker file, and `git push origin main` pushes a clean, checked-out commit that carries the trailer
- **THEN** the marker file exists and the push reaches the remote

#### Scenario: The worktree stays clean
- **WHEN** `install` runs in a repository with a clean worktree
- **THEN** `git status --porcelain` still prints nothing

### Requirement: The report and its errors
`install` SHALL print, for native hooks, the hooks directory and, when the previous directory holds any hook it chains or forwards, the previous directory. Outside a git repository it SHALL exit 1 for every choice of hooks and its message SHALL say there is no git repository.

#### Scenario: Report
- **WHEN** `install` runs in a repository whose `.git/hooks/pre-push` exists
- **THEN** the output names the hooks directory and `.git/hooks`

#### Scenario: Not a repository
- **WHEN** `install` runs in a directory that is not inside a git repository
- **THEN** it exits 1 and the message says there is no git repository

#### Scenario: Not a repository with a manager named
- **WHEN** `install --hooks lefthook` runs in a directory that is not inside a git repository
- **THEN** it exits 1 and the message says there is no git repository
