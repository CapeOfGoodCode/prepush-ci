# install Specification

## Purpose
What `prepush-ci install` writes into a repository so git runs the commit-msg and pre-push hooks, how the hooks that existed before keep running, and what the command reports.

## Requirements

### Requirement: Native hooks through core.hooksPath
For native hooks (see "The choice of hooks"), `prepush-ci install` SHALL write the scripts `commit-msg` and `pre-push` into the directory `prepush-ci/hooks` of the common git directory, make them executable and set the local `core.hooksPath` to its absolute path. `commit-msg` SHALL run `prepush-ci hook commit-msg` with the arguments git passes; `pre-push` SHALL run `prepush-ci hook pre-push` with the arguments and standard input git passes. No file of the worktree SHALL change.

#### Scenario: Trailer written after install
- **WHEN** `install` ran in a repository without any hook and `git commit -m "add x"` runs with `PREPUSH_CI=full`
- **THEN** the commit's message ends with the trailer `Prepush-CI: full`

#### Scenario: Check run on push after install
- **WHEN** `install` ran, the config's `check` writes a marker file, and `git push origin main` pushes a clean, checked-out commit that carries the trailer
- **THEN** the marker file exists and the push reaches the remote

#### Scenario: The worktree stays clean
- **WHEN** `install` runs in a repository with a clean worktree
- **THEN** `git status --porcelain` still prints nothing

### Requirement: The tool is found without PATH
The native scripts SHALL start the tool as `<python> -m prepush_ci`, where `<python>` is the interpreter that ran `install`, recorded in the file `python` of the hooks directory. They SHALL NOT look up `prepush-ci` on `PATH`. The files of a manager are not native scripts; they start `prepush-ci` from `PATH`.

#### Scenario: prepush-ci is not on PATH
- **WHEN** `install` ran from an interpreter whose scripts directory is not on `PATH`, and a commit runs with `PREPUSH_CI=full`
- **THEN** the commit's message ends with the trailer

### Requirement: A missing interpreter
When the recorded interpreter does not exist, the `pre-push` script SHALL refuse the push and its message SHALL name `prepush-ci install`. The `commit-msg` script SHALL print a warning naming `prepush-ci install` on standard error, write no trailer and exit 0.

#### Scenario: Push with a vanished interpreter
- **WHEN** the file `python` names a path that does not exist and `git push origin main` runs
- **THEN** the push is refused and the error contains `prepush-ci install`

#### Scenario: Commit with a vanished interpreter
- **WHEN** the file `python` names a path that does not exist and `git commit -m "add x"` runs with `PREPUSH_CI=full`
- **THEN** the commit succeeds without the trailer and the warning contains `prepush-ci install`

### Requirement: The previous hooks directory
The previous hooks directory SHALL be the directory git would use for hooks without `install`: the effective `core.hooksPath` of any scope, otherwise the directory `git rev-parse --git-path hooks` prints (under the common git directory, also in a linked worktree). It SHALL be recorded in the file `previous` of the hooks directory. `install` SHALL NOT modify it.

#### Scenario: Linked worktree
- **WHEN** `.git/hooks/pre-push` exits 1, `install` runs in a linked worktree of the repository, and a trailer commit is pushed from either worktree
- **THEN** the push is refused by that hook

#### Scenario: Existing core.hooksPath
- **WHEN** `core.hooksPath` is `custom-hooks`, which holds a `pre-push` hook that exits 1, and `install` ran
- **THEN** a push is refused by that hook, and `custom-hooks` holds the same files with the same contents as before

### Requirement: Existing hooks keep running
For `commit-msg` and `pre-push` the scripts SHALL, each time they run, first run the hook of the same name in the previous directory with the same arguments and standard input, only if it exists and is executable, as git does, and SHALL abort with its exit status when it fails, without running ours.

#### Scenario: Existing pre-push hook that passes
- **WHEN** `.git/hooks/pre-push` exists and exits 0, `install` ran, and a trailer commit is pushed
- **THEN** the existing hook ran and the check ran

#### Scenario: Existing pre-push hook that fails
- **WHEN** `.git/hooks/pre-push` exists and exits 1, `install` ran, and a trailer commit is pushed
- **THEN** the push is refused, the check did not run and the remote has no new commit

#### Scenario: Existing commit-msg hook
- **WHEN** `.git/hooks/commit-msg` appends the line `Reviewed` to the message, `install` ran, and `git commit -m "add x"` runs with `PREPUSH_CI=full`
- **THEN** the commit's message contains `Reviewed` and ends with the trailer

#### Scenario: Existing hook gets the push input
- **WHEN** the existing `pre-push` hook copies its standard input to a file and a commit is pushed after `install`
- **THEN** the file holds git's ref line for the pushed branch and the remote name is its first argument

#### Scenario: Existing pre-push hook that is not executable
- **WHEN** `.git/hooks/pre-push` exists without the executable bit and exits 1, `install` ran, and a trailer commit is pushed
- **THEN** the check ran and the push reached the remote

#### Scenario: Samples are not hooks
- **WHEN** `.git/hooks/pre-push.sample` exists and `install` ran
- **THEN** the sample did not run on a push and `install` wrote no forwarding script for it

### Requirement: Other hooks are forwarded
For every regular file of the previous directory, executable or not, that is not named `*.sample` and is not `commit-msg` or `pre-push`, `install` SHALL write a script of the same name into the hooks directory that does what git would do with the previous directory each time it runs: it starts the previous hook with the same arguments and standard input and exits with its status, only if that hook exists and is executable; otherwise it exits 0.

#### Scenario: Existing pre-commit hook
- **WHEN** `.git/hooks/pre-commit` exists and exits 1, and `install` ran
- **THEN** `git commit` fails because of that hook

#### Scenario: Non-executable hook
- **WHEN** `.git/hooks/pre-commit` exists without the executable bit and exits 1, and `install` ran
- **THEN** `git commit` succeeds

#### Scenario: Hook deleted after install
- **WHEN** `install` ran with an executable `.git/hooks/pre-commit`, which is then deleted
- **THEN** `git commit` succeeds without a rerun of `install`

#### Scenario: Hook receives its arguments
- **WHEN** `.git/hooks/post-checkout` writes its arguments to a file and `install` ran, and `git checkout -b topic` runs
- **THEN** the file holds the three arguments git passes to `post-checkout`

### Requirement: Install is idempotent
Running `install` again SHALL write no file and change no config when nothing differs from what it would write, print a line containing `already installed` and exit 0. When something differs (another interpreter, a new hook in the previous directory) it SHALL write the difference and print a line containing `updated`. A first run SHALL print a line containing `installed`.

#### Scenario: Second run
- **WHEN** `install` runs twice in a row
- **THEN** the second run exits 0 and prints `already installed`, every file in the hooks directory has the same contents and modification time as after the first run, and `core.hooksPath` is unchanged

#### Scenario: New hook after install
- **WHEN** `install` ran, then `.git/hooks/post-merge` is added, and `install` runs again
- **THEN** the second run prints `updated` and the hooks directory has a `post-merge` script that runs it

#### Scenario: Another interpreter
- **WHEN** `install` ran from one interpreter and runs again from another
- **THEN** the second run prints `updated` and the file `python` names the second interpreter

### Requirement: A rerun keeps the previous directory
While the effective `core.hooksPath` is ours, a rerun SHALL keep the recorded previous directory, never recording the hooks directory itself. When it is something else (a hook manager set it after the first run), that value SHALL become the previous directory, so a rerun never drops it, and the run SHALL print `updated`.

#### Scenario: Existing hook survives a second run
- **WHEN** `.git/hooks/pre-push` exits 1 and `install` runs twice
- **THEN** a push of a trailer commit is refused by that hook

#### Scenario: A manager changed core.hooksPath
- **WHEN** `install` ran, then `core.hooksPath` is set to `managed-hooks`, which holds a `pre-push` hook that exits 1, and `install` runs again
- **THEN** the second run prints `updated`, `core.hooksPath` is ours again and a push of a trailer commit is refused by that hook

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
Every change `install` makes to a file of a manager SHALL be one block per file, and for lefthook one per hook section, each starting with the line `# prepush-ci: begin` and ending with the line `# prepush-ci: end`, except the keys `default_install_hook_types` and `default_stages` of pre-commit. Every line of the file outside the block SHALL stay as it was. When the file already holds the block, `install` SHALL replace its lines and no other.

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
The requirements of this specification about the hooks directory, the previous directory, forwarding, the recorded interpreter and `core.hooksPath` SHALL describe the native hooks only, except the two that refuse a manager while the native hooks hold `core.hooksPath`. For a manager, `install` SHALL NOT create the hooks directory or the files `python` and `previous`.

#### Scenario: No native files for a manager
- **WHEN** `install --hooks husky` ran in a repository whose `.git/hooks/pre-push` exists
- **THEN** the directory `prepush-ci/hooks` of the git directory does not exist and `.git/hooks/pre-push` is unchanged

### Requirement: A temporary interpreter is reported
When `install` writes native hooks and the interpreter it records lies inside uv's cache directory, it SHALL print a warning on standard error that the interpreter is temporary and the hooks stop working when uv cleans its cache, and that names the fix, `uv tool install prepush-ci` followed by `prepush-ci install`. The warning SHALL NOT change the exit status, the files written or the `installed`, `updated` or `already installed` line.

#### Scenario: Interpreter in the uv cache
- **WHEN** `UV_CACHE_DIR` names a directory that contains the interpreter running `install`, and `install` runs
- **THEN** it exits 0, standard error contains `temporary` and `uv tool install prepush-ci`, and the hooks directory holds the hooks as without the warning

#### Scenario: Interpreter outside the uv cache
- **WHEN** `UV_CACHE_DIR` names a directory that does not contain the interpreter running `install`, and `install` runs
- **THEN** standard error does not contain `temporary`

#### Scenario: The warning comes back on a rerun
- **WHEN** `install` ran with the interpreter inside `UV_CACHE_DIR` and runs again
- **THEN** the second run prints `already installed` and standard error contains `temporary` again

### Requirement: Where uv's cache directory is
uv's cache directory SHALL be found as uv does: `UV_CACHE_DIR` when set and not empty, a relative value taken relative to the working directory; otherwise, on Windows, `%LOCALAPPDATA%\uv\cache`; otherwise `$XDG_CACHE_HOME/uv` when `XDG_CACHE_HOME` is set and not empty, else `$HOME/.cache/uv`, on every other platform.

#### Scenario: The default under XDG_CACHE_HOME
- **WHEN** `UV_CACHE_DIR` is unset, `XDG_CACHE_HOME/uv` contains the interpreter running `install`, and `install` runs
- **THEN** standard error contains `temporary`

#### Scenario: The default under HOME
- **WHEN** `UV_CACHE_DIR` and `XDG_CACHE_HOME` are unset, `$HOME/.cache/uv` contains the interpreter running `install`, and `install` runs
- **THEN** standard error contains `temporary`

#### Scenario: An empty UV_CACHE_DIR is ignored
- **WHEN** `UV_CACHE_DIR` is empty, `XDG_CACHE_HOME/uv` contains the interpreter running `install`, and `install` runs
- **THEN** standard error contains `temporary`

#### Scenario: A relative UV_CACHE_DIR
- **WHEN** `UV_CACHE_DIR` is `cache`, the working directory holds `cache/` with the interpreter running `install` inside, and `install` runs there
- **THEN** standard error contains `temporary`

### Requirement: Inside the cache means whole path components
The interpreter SHALL count as inside the cache directory only when the path components of the directory, as found or with its symbolic links resolved, are a prefix of the interpreter's path components. The interpreter's path SHALL be compared as written and never resolved. A directory that merely shares a name prefix with the cache directory SHALL NOT count.

#### Scenario: A sibling directory with the same name prefix
- **WHEN** `UV_CACHE_DIR` is `<base>/uv` and the interpreter running `install` is `<base>/uv2/bin/python`
- **THEN** standard error does not contain `temporary`

#### Scenario: A virtualenv interpreter that links out of the cache
- **WHEN** the interpreter running `install` is a symbolic link inside `UV_CACHE_DIR` that points to a Python outside it
- **THEN** standard error contains `temporary`

#### Scenario: The cache directory is a symbolic link
- **WHEN** `UV_CACHE_DIR` is a symbolic link to `<base>/real` and the interpreter running `install` is `<base>/real/archive-v0/x/bin/python`
- **THEN** standard error contains `temporary`

#### Scenario: The default cache lies behind a symbolic link
- **WHEN** `UV_CACHE_DIR` and `XDG_CACHE_HOME` are unset, `$HOME/.cache` is a symbolic link to `<base>/disk`, and the interpreter running `install` is inside `<base>/disk/uv`
- **THEN** standard error contains `temporary`

#### Scenario: A sibling of the link target
- **WHEN** `UV_CACHE_DIR` is a symbolic link to `<base>/real` and the interpreter running `install` is `<base>/real2/bin/python`
- **THEN** standard error does not contain `temporary`

#### Scenario: A cache directory that does not exist
- **WHEN** `UV_CACHE_DIR` names a directory that does not exist and the interpreter running `install` is outside it
- **THEN** standard error does not contain `temporary` and `install` exits as it would without the variable

### Requirement: A manager is refused while the native hooks hold core.hooksPath
When the chosen hooks are those of pre-commit or lefthook and the local `core.hooksPath`, made absolute, is the native hooks directory, `install` SHALL exit 1 and change nothing. Its message SHALL name `core.hooksPath` and the command `git config --local --unset core.hooksPath`, and say to run `install` again afterwards. The choice of husky, and a `core.hooksPath` that is not the native hooks directory, SHALL NOT cause this refusal.

#### Scenario: pre-commit after a native install
- **WHEN** `install --hooks native` ran, `.pre-commit-config.yaml` exists and `install` runs
- **THEN** it exits 1, the message contains `core.hooksPath` and `git config --local --unset core.hooksPath`, `.pre-commit-config.yaml` has the same contents as before and `core.hooksPath` is still the native hooks directory

#### Scenario: lefthook after a native install
- **WHEN** `install --hooks native` ran, `lefthook.yml` exists and `install` runs
- **THEN** it exits 1, the message contains `core.hooksPath` and `git config --local --unset core.hooksPath`, `lefthook.yml` has the same contents as before and `core.hooksPath` is still the native hooks directory

#### Scenario: A rerun after the setting is removed
- **WHEN** `install` was refused for pre-commit, `git config --local --unset core.hooksPath` ran and `install` runs again
- **THEN** it exits 0, prints `installed`, `.pre-commit-config.yaml` holds the block and `core.hooksPath` is unset

#### Scenario: husky is not refused
- **WHEN** `install --hooks native` ran, `.husky` exists and `install --hooks husky` runs
- **THEN** it exits 0 and `.husky/commit-msg` and `.husky/pre-push` hold the block

#### Scenario: A core.hooksPath that is not ours
- **WHEN** `core.hooksPath` is `custom-hooks`, `.pre-commit-config.yaml` exists and `install` runs
- **THEN** it exits 0, `.pre-commit-config.yaml` holds the block and `core.hooksPath` is still `custom-hooks`

### Requirement: The refusal names the hooks that would stop running
When `install` refuses a manager because the native hooks hold `core.hooksPath`, and the file `previous` of the native hooks directory names a directory that holds a regular file not named `*.sample` and that is not the directory git uses for hooks once the local `core.hooksPath` is gone, the message SHALL also name that directory and say that its hooks will no longer run. Otherwise the message SHALL NOT say so.

#### Scenario: A previous directory that stops being used
- **WHEN** `core.hooksPath` was `custom-hooks`, which holds a `pre-push` hook, `install --hooks native` ran, `.pre-commit-config.yaml` exists and `install` runs
- **THEN** it exits 1 and the message contains `custom-hooks` and `no longer run`

#### Scenario: A previous directory that stays in use
- **WHEN** `.git/hooks/pre-push` exists, `install --hooks native` ran, `.pre-commit-config.yaml` exists and `install` runs
- **THEN** it exits 1 and the message does not contain `no longer run`
