# init Specification

## Purpose
What `prepush-ci init` asks, writes and prints to set a repository up in one command: the config file, the hooks through `install`, the Claude Code SessionStart hook and its registration, and the CI gate snippet; when it refuses and why a second run changes nothing.

## Requirements

### Requirement: Non-interactive setup
`prepush-ci init --non-interactive` SHALL ask nothing, read no standard input and run these steps in order: the config file, `install`, the SessionStart hook, the CI gate snippet. It SHALL exit 0 when every step succeeded. Outside a git repository it SHALL exit 1, write nothing and say there is no git repository.

#### Scenario: One command sets a repository up
- **WHEN** `init --non-interactive --check scripts/ci --hooks native` runs with standard input closed in a repository without config
- **THEN** it exits 0, `.prepush-ci.toml` exists, `core.hooksPath` is the native hooks directory and `.claude/hooks/session-start.sh` exists

#### Scenario: Not a repository
- **WHEN** `init --non-interactive --check scripts/ci` runs in a directory that is not inside a git repository
- **THEN** it exits 1, the message says there is no git repository and no file was created

### Requirement: Paths
`init` SHALL place `.prepush-ci.toml`, `.claude/hooks/session-start.sh` and `.claude/settings.json` at the root of the working tree and read `scripts/ci`, `bin/ci`, `Makefile`, `.github/workflows/` and `.gitlab-ci.yml` there, wherever it runs inside the tree. A relative path given to `--ci-gate-file` SHALL be relative to the current directory.

#### Scenario: Run from a subdirectory
- **WHEN** `init --non-interactive --check scripts/ci --ci-gate-file gate.yml` runs in the subdirectory `sub` of the working tree
- **THEN** `.prepush-ci.toml`, `.claude/hooks/session-start.sh` and `.claude/settings.json` exist at the root, `sub/gate.yml` exists and neither `sub/.prepush-ci.toml` nor `sub/.claude` does

### Requirement: The config is written from the flags
With no config in the repository, `init` SHALL write `.prepush-ci.toml` at the root of the working tree with the key `check` and, for each flag given, `preflight`, `require_env` (the flag may repeat), `require_up_to_date` (a ref, `true` or `false`) and `default_branch`, and no other key. The config SHALL load with exactly those values.

#### Scenario: Every flag
- **WHEN** `init --non-interactive --check "make ci" --preflight "make up" --require-env A --require-env B --default-branch trunk --require-up-to-date upstream/trunk` runs
- **THEN** the loaded config has check `make ci`, preflight `make up`, required variables `A` and `B`, default branch `trunk` and up-to-date ref `upstream/trunk`

#### Scenario: Only the check
- **WHEN** `init --non-interactive --check scripts/ci` runs
- **THEN** `.prepush-ci.toml` holds the key `check` and no other key

#### Scenario: A flag equal to the default is written
- **WHEN** `init --non-interactive --check scripts/ci --default-branch main` runs
- **THEN** `.prepush-ci.toml` holds the keys `check` and `default_branch`

#### Scenario: Up-to-date switched off
- **WHEN** `init --non-interactive --check scripts/ci --require-up-to-date false` runs
- **THEN** the loaded config has no up-to-date ref

#### Scenario: A check with quotes
- **WHEN** `init --non-interactive --check 'sh -c "make ci"'` runs
- **THEN** the loaded config's check is `sh -c "make ci"`

### Requirement: The check is required until there is a config
While neither `.prepush-ci.toml` nor a `[tool.prepush-ci]` table exists, `init --non-interactive` without `--check` SHALL exit 2 naming `--check` and write nothing. A value the config rejects (an empty check, say) SHALL exit 1 with the config's message and write nothing.

#### Scenario: No check given
- **WHEN** `init --non-interactive` runs in a repository without config
- **THEN** it exits 2, the message names `--check` and no file was created

#### Scenario: An empty check
- **WHEN** `init --non-interactive --check ""` runs
- **THEN** it exits 1, the message names `check` and no file was created

### Requirement: An existing config is kept
When `.prepush-ci.toml` or a `[tool.prepush-ci]` table exists, `init` SHALL NOT write or change a config file and `--check` SHALL be optional. A config that does not load (an unknown key, malformed TOML, an empty check) SHALL make `init` exit 1 with the config's message before it writes any file. A flag whose value differs from the loaded config SHALL do the same, naming each key that differs.

#### Scenario: Flags that agree
- **WHEN** `.prepush-ci.toml` sets `check = "scripts/ci"` and `init --non-interactive --check scripts/ci --hooks native` runs
- **THEN** it exits 0 and `.prepush-ci.toml` has the same contents and modification time as before

#### Scenario: A flag that disagrees
- **WHEN** `.prepush-ci.toml` sets `check = "scripts/ci"` and `init --non-interactive --check "make ci"` runs
- **THEN** it exits 1, the message names `check` and no file changed or was created

#### Scenario: A config that does not load
- **WHEN** `.prepush-ci.toml` holds `chekc = "scripts/ci"` and `init --non-interactive --hooks native` runs
- **THEN** it exits 1, the message names `chekc` and no file was created or changed

#### Scenario: Config in pyproject.toml
- **WHEN** `pyproject.toml` has `[tool.prepush-ci]` with `check = "make ci"` and `init --non-interactive --hooks native` runs
- **THEN** it exits 0 and `.prepush-ci.toml` was not created

### Requirement: Hooks are installed through install
`init` SHALL run `install` with the value of `--hooks` and, without it, let `install` detect the hooks. With `--hooks none` it SHALL run no `install` and touch neither git config nor hook files. The output SHALL include what `install` printed. A refusal of `install` SHALL end `init` with exit 1 and that message, before the SessionStart hook and the CI gate.

#### Scenario: A manager is detected
- **WHEN** `.pre-commit-config.yaml` exists and `init --non-interactive --check scripts/ci` runs
- **THEN** that file holds the `prepush-ci` block and `core.hooksPath` is unset

#### Scenario: An existing pre-push hook keeps running
- **WHEN** `.git/hooks/pre-push` exits 1 and `init --non-interactive --check scripts/ci` ran, then a commit with the trailer is pushed
- **THEN** the push is refused by that hook

#### Scenario: No local hooks
- **WHEN** `init --non-interactive --check scripts/ci --hooks none` runs
- **THEN** it exits 0, `core.hooksPath` is unset and `.git/prepush-ci` does not exist

#### Scenario: Several managers
- **WHEN** `.pre-commit-config.yaml` and `lefthook.yml` both exist and `init --non-interactive --check scripts/ci` runs
- **THEN** it exits 1, the message contains `--hooks`, and no SessionStart hook was written

### Requirement: The SessionStart hook skeleton
Unless `--no-session-hook` is given, `init` SHALL write `.claude/hooks/session-start.sh`, executable, that exits 0 at once when `CLAUDE_CODE_REMOTE` is not `true`; otherwise makes `prepush-ci` startable (next requirement), runs `prepush-ci install` with `--hooks <name>` when a hooks value other than `none` was given or chosen, and appends `export PREPUSH_CI=full` to the file `CLAUDE_ENV_FILE` names unless it holds that line already. It SHALL NOT overwrite an existing file.

#### Scenario: Laptops are not touched
- **WHEN** `.claude/hooks/session-start.sh` runs with `CLAUDE_CODE_REMOTE` unset and a `uv` on `PATH` that records its calls
- **THEN** it exits 0, `uv` was not called and `CLAUDE_ENV_FILE` is unchanged

#### Scenario: Install is called with the chosen hooks
- **WHEN** `init ... --hooks husky` ran and the script runs with `CLAUDE_CODE_REMOTE=true` and a stub `uv` whose bin directory holds a `prepush-ci` that records its calls
- **THEN** that `prepush-ci` was called with `install --hooks husky`

#### Scenario: The export is not repeated
- **WHEN** the script runs twice with `CLAUDE_CODE_REMOTE=true`
- **THEN** `CLAUDE_ENV_FILE` holds `export PREPUSH_CI=full` once

#### Scenario: Trailer written in the session
- **WHEN** the script ran with `CLAUDE_CODE_REMOTE=true`, the lines of `CLAUDE_ENV_FILE` are sourced into a shell whose `PATH` has no `prepush-ci`, and `git commit -m "add x"` runs
- **THEN** the commit's message ends with the trailer `Prepush-CI: full`

#### Scenario: No env file
- **WHEN** the script runs with `CLAUDE_CODE_REMOTE=true` and `CLAUDE_ENV_FILE` unset
- **THEN** it exits 0 and prints a warning on standard error

#### Scenario: An existing script is kept
- **WHEN** `.claude/hooks/session-start.sh` holds other lines and `init` runs
- **THEN** the file has the same contents as before and the output says `kept`

#### Scenario: Opt out
- **WHEN** `init --non-interactive --check scripts/ci --no-session-hook` runs
- **THEN** neither `.claude/hooks/session-start.sh` nor `.claude/settings.json` was created

### Requirement: The skeleton makes the tool startable
The skeleton SHALL run `uv tool install prepush-ci`, then put the directory `uv tool dir --bin` prints at the front of its own `PATH` and append `export PATH="<that directory>:$PATH"` to `CLAUDE_ENV_FILE` unless the file holds the line already. It SHALL NOT run `uvx`. It SHALL NOT run the activation step of a hook manager (`pre-commit install`, `lefthook install`, husky's `prepare`); `install` prints it and the setup skill owns it.

#### Scenario: A manager's hooks find the tool
- **WHEN** `init ... --hooks husky` ran in a repository with `.husky`, the script ran with `CLAUDE_CODE_REMOTE=true`, the lines of `CLAUDE_ENV_FILE` are sourced into a shell whose `PATH` has no `prepush-ci`, and `sh .husky/commit-msg <file>` runs with `PREPUSH_CI=full`
- **THEN** the message file ends with the trailer `Prepush-CI: full`

#### Scenario: The tool is installed persistently
- **WHEN** the script runs with `CLAUDE_CODE_REMOTE=true` and a recording `uv` on `PATH`
- **THEN** `uv` was called with `tool install prepush-ci` and with no `uvx`-style `tool run`

#### Scenario: The path export is not repeated
- **WHEN** the script runs twice with `CLAUDE_CODE_REMOTE=true`
- **THEN** `CLAUDE_ENV_FILE` holds one `export PATH=` line for the tool directory

### Requirement: The hook is registered in the settings
`init` SHALL register the script in `.claude/settings.json`, creating the file when it is missing, as one group in the list `hooks.SessionStart`: an object whose list `hooks` holds `{"type": "command", "command": …}` with a command that runs `.claude/hooks/session-start.sh` from the project directory. It SHALL keep every other setting. It SHALL add nothing when a command in a group's `hooks` already names `session-start.sh`.

#### Scenario: Settings created
- **WHEN** `init` runs without a `.claude` directory
- **THEN** `.claude/settings.json` parses as JSON and `hooks.SessionStart[0].hooks[0]` has `type` `command` and a `command` that runs `.claude/hooks/session-start.sh`

#### Scenario: Existing settings are kept
- **WHEN** `.claude/settings.json` sets `permissions` and a `PreToolUse` hook, and `init` runs
- **THEN** both are still in the parsed file, equal to before, and `hooks.SessionStart` holds a group whose `hooks` hold the new command

#### Scenario: Already registered
- **WHEN** `init` ran, then runs again
- **THEN** `hooks.SessionStart` holds one group with the command

### Requirement: Malformed settings are refused
A `.claude/settings.json` that is not valid JSON, or whose `hooks` or `hooks.SessionStart` is not an object or a list respectively, SHALL make `init` exit 1 naming the file, before it writes any file.

#### Scenario: Malformed settings
- **WHEN** `.claude/settings.json` is not valid JSON and `init` runs
- **THEN** it exits 1, the message names `.claude/settings.json` and no file was created or changed

#### Scenario: Unexpected shape
- **WHEN** `.claude/settings.json` holds `{"hooks": {"SessionStart": "x"}}` and `init` runs
- **THEN** it exits 1, the message names `.claude/settings.json` and the file has the same contents as before

### Requirement: The CI gate snippet
`init` SHALL print the CI gate snippet for one CI system: GitHub Actions when `.github/workflows/` holds a `.yml` or `.yaml` file, else GitLab CI when `.gitlab-ci.yml` exists, else the generic shell gate; `--ci github|gitlab|generic|none` overrides, `none` printing nothing. The snippet SHALL be the whole text of `docs/ci/github-actions.yml`, `docs/ci/gitlab-ci.yml` or `docs/ci/gate.sh`. `init` SHALL change no CI file.

#### Scenario: GitHub Actions detected
- **WHEN** `.github/workflows/ci.yml` exists and `init --non-interactive --check scripts/ci` runs
- **THEN** the output contains the full text of `docs/ci/github-actions.yml` and `.github/workflows/ci.yml` has the same contents as before

#### Scenario: GitLab CI detected
- **WHEN** `.gitlab-ci.yml` exists, no `.github/workflows/` file does, and `init` runs
- **THEN** the output contains the full text of `docs/ci/gitlab-ci.yml`

#### Scenario: Nothing detected
- **WHEN** neither exists and `init` runs
- **THEN** the output contains the full text of `docs/ci/gate.sh`

#### Scenario: Chosen by hand
- **WHEN** `.github/workflows/ci.yml` exists and `init --ci gitlab` runs
- **THEN** the output contains the full text of `docs/ci/gitlab-ci.yml`

#### Scenario: No snippet
- **WHEN** `init --ci none` runs
- **THEN** the output contains none of the three texts

### Requirement: The snippet can be written
With `--ci-gate-file <path>`, `init` SHALL write the snippet to that path, creating its directories, instead of printing it. It SHALL NOT overwrite a file with other contents: it SHALL exit 1 naming the path before it writes any file. A file that holds the snippet already SHALL be left as it is.

#### Scenario: Snippet written
- **WHEN** `init --non-interactive --check scripts/ci --ci github --ci-gate-file ci/gate.yml` runs
- **THEN** `ci/gate.yml` holds the text of `docs/ci/github-actions.yml` and the output does not repeat it

#### Scenario: Another file is in the way
- **WHEN** `ci/gate.yml` exists with other contents and `init --non-interactive --check scripts/ci --ci-gate-file ci/gate.yml` runs
- **THEN** it exits 1, the message names `ci/gate.yml` and no file changed or was created

### Requirement: Interactive setup
Without `--non-interactive`, `init` SHALL ask on standard output and read the answers from standard input, one line each, before it writes any file. For `check`, `preflight`, `require_env` (comma-separated), `default_branch` and `require_up_to_date` it SHALL show a default and take an empty answer as the default; no config question is asked when a config exists or the flag for it was given. It SHALL ask whether to write the SessionStart hook.

#### Scenario: Defaults detected
- **WHEN** `scripts/ci` exists, `origin/HEAD` points at `origin/trunk` and `init` runs with an empty line for every answer
- **THEN** the question for `check` shows `scripts/ci`, the question for `default_branch` shows `trunk`, and the loaded config has both

#### Scenario: A typed answer
- **WHEN** `init` runs with the answers `make ci` for the check and empty lines for the rest
- **THEN** the loaded config's check is `make ci`

#### Scenario: A flag answers the question
- **WHEN** `init --check scripts/ci` runs
- **THEN** no question for `check` is asked

#### Scenario: Declining the SessionStart hook
- **WHEN** `init` runs and the answer to the SessionStart question is `n`
- **THEN** `.claude/hooks/session-start.sh` was not created

### Requirement: Interactive defaults
The default of `check` SHALL be the first of `scripts/ci`, `bin/ci` and `make ci` (a `Makefile` with a `ci:` target) that exists; without one, an empty answer SHALL be refused naming `check`. The default of `preflight` and `require_env` SHALL be none, of `default_branch` the branch `origin/HEAD` names, else `main`, of `require_up_to_date` `origin/<default_branch>`. The answer `false` for `require_up_to_date` SHALL switch it off.

#### Scenario: Branch default without origin/HEAD
- **WHEN** `origin/HEAD` is unset and `init` runs
- **THEN** the question for `default_branch` shows `main`

#### Scenario: A Makefile target
- **WHEN** neither `scripts/ci` nor `bin/ci` exists, the `Makefile` has a `ci:` target and `init` runs
- **THEN** the question for `check` shows `make ci`

#### Scenario: No detected check
- **WHEN** no `scripts/ci`, `bin/ci` or `Makefile` with a `ci:` target exists and the answer for `check` is empty
- **THEN** it exits 1, the message names `check` and no file was created

#### Scenario: Switching the up-to-date check off
- **WHEN** the answer for `require_up_to_date` is `false`
- **THEN** the loaded config has no up-to-date ref

### Requirement: Interactive answers write only what differs
Interactively, `init` SHALL write `check` always and any other key only when its answer differs from what the config would take without the key; a key given by its flag is written as given.

#### Scenario: A default equal to the built-in one
- **WHEN** `origin/HEAD` names `origin/main` and `init` runs with `make ci` for the check and empty lines for the rest
- **THEN** `.prepush-ci.toml` holds the key `check` and no `default_branch` and no `require_up_to_date`

#### Scenario: An answer that differs
- **WHEN** `init` runs with `make ci` for the check, `trunk` for `default_branch` and an empty line for `require_up_to_date`
- **THEN** `.prepush-ci.toml` holds `check` and `default_branch` and no `require_up_to_date`

### Requirement: The hooks question
Interactively and without `--hooks`, `init` SHALL ask what to do about hooks, always, listing `native`, `pre-commit`, `husky`, `lefthook` and `none`, with the hooks `install` would use as the default, and SHALL name what it found: each hook manager's file and an existing `pre-push` hook in the directory `install` takes as the previous one.

#### Scenario: An existing pre-push hook is named
- **WHEN** `.git/hooks/pre-push` exists and `init` runs
- **THEN** the hooks question names `.git/hooks/pre-push`

#### Scenario: A manager is the default
- **WHEN** `lefthook.yml` exists and the answer to the hooks question is empty
- **THEN** the question names `lefthook.yml` and `lefthook.yml` holds the `prepush-ci` block

#### Scenario: The user picks none
- **WHEN** the answer to the hooks question is `none`
- **THEN** `core.hooksPath` is unset and `.git/prepush-ci` does not exist

#### Scenario: Nothing found
- **WHEN** no manager and no pre-push hook exist and the hooks question is asked
- **THEN** it lists the five choices with `native` as the default

### Requirement: Interactive refusals write nothing
An answer that the config or the hooks choice rejects SHALL make interactive `init` exit 1 before it writes any file, naming the valid values or the config's message. End of input before the last question SHALL do the same, with a message that names `--non-interactive`.

#### Scenario: Unknown hooks
- **WHEN** the answer to the hooks question is `jenkins`
- **THEN** it exits 1, the message contains `native`, `pre-commit`, `husky`, `lefthook` and `none` and no file was created

#### Scenario: Input ends early
- **WHEN** `init` runs with standard input closed
- **THEN** it exits 1, the message names `--non-interactive` and no file was created

### Requirement: Init is idempotent
Running `init` again with the same flags SHALL write no file, leave every file with the same contents and modification time, exit 0 and end its output with a line containing `already set up`. A run that wrote or changed a file SHALL end with a line containing `set up` but not `already set up`. Each step that owns a file SHALL report it as `written`, `updated` or `kept`.

#### Scenario: Second run
- **WHEN** `init --non-interactive --check scripts/ci --hooks native --ci github --ci-gate-file ci/gate.yml` runs twice in a row
- **THEN** the second run exits 0, its last line contains `already set up`, and every file has the same contents and modification time as after the first run

#### Scenario: First run
- **WHEN** `init --non-interactive --check scripts/ci` runs for the first time
- **THEN** the last line of the output contains `set up` and not `already set up`

#### Scenario: A manager file idempotent as well
- **WHEN** `.pre-commit-config.yaml` exists and `init --non-interactive --check scripts/ci` runs twice
- **THEN** the second run's last line contains `already set up` and `.pre-commit-config.yaml` is unchanged by it

### Requirement: A default branch must be a branch name
`init` SHALL refuse a default branch, given with `--default-branch` or typed as the answer, that the config rejects as not a branch name: it SHALL exit 1 with the config's message and write no file, also when the answer is read interactively.

#### Scenario: A full ref as the flag
- **WHEN** `init --non-interactive --check scripts/ci --default-branch refs/remotes/origin/trunk` runs
- **THEN** it exits 1, the message names `default_branch` and contains `use "trunk"`, and no file was created

#### Scenario: A remote-tracking name as the flag
- **WHEN** `init --non-interactive --check scripts/ci --default-branch origin/trunk` runs
- **THEN** it exits 1, the message names `default_branch` and contains `use "trunk"`, and no file was created

#### Scenario: A full ref as the answer
- **WHEN** `init --check scripts/ci` runs and the answer for `default_branch` is `refs/remotes/origin/trunk`
- **THEN** it exits 1, the message names `default_branch` and contains `use "trunk"`, and no file was created

#### Scenario: The branch name is accepted
- **WHEN** `init --non-interactive --check scripts/ci --default-branch main` runs
- **THEN** it exits 0 and the loaded config has default branch `main`

### Requirement: A default branch that origin lacks
`init` SHALL refuse a default branch, given with `--default-branch` or typed as the answer, when the remote-tracking branches of `origin` (any `refs/remotes/origin/*` other than `HEAD`) exist and none is the named one, unless the next requirement says it is not checked. It SHALL exit 1 with one message naming `default_branch`, the branch and the command `git fetch origin`, and write no file.

#### Scenario: A branch the remote renamed away
- **WHEN** a clone with the default fetch refspec has the remote-tracking branch `origin/main` only and `init --non-interactive --check scripts/ci --default-branch master` runs
- **THEN** it exits 1, the message names `default_branch`, `master` and `git fetch origin`, and no file was created

#### Scenario: A stale default accepted interactively
- **WHEN** a clone with the default fetch refspec has `origin/HEAD` naming `origin/master`, the remote-tracking branch `origin/main` only, and `init --check scripts/ci` runs with an empty line for `default_branch`
- **THEN** it exits 1, the message names `default_branch` and `master`, and no file was created

#### Scenario: A branch origin has
- **WHEN** a clone with the default fetch refspec has the remote-tracking branches `origin/main` and `origin/trunk` and `init --non-interactive --check scripts/ci --default-branch trunk` runs
- **THEN** it exits 0 and the loaded config has default branch `trunk`

### Requirement: When the default branch is not checked
`init` SHALL NOT check the default branch against `origin` when the repository holds no remote-tracking branch of `origin` (no remote, an empty remote, a remote never fetched), when no value of `remote.origin.fetch` is the default `+refs/heads/*:refs/remotes/origin/*` (a single-branch or shallow clone, a narrowed fetch: the remote-tracking branches then say nothing about what `origin` has), or when the up-to-date ref in effect is not `origin/<branch>`.

#### Scenario: No remote-tracking branches
- **WHEN** the repository has no remote, or a remote `origin` whose branches were never fetched, and `init --non-interactive --check scripts/ci --default-branch trunk` runs
- **THEN** it exits 0 and the loaded config has default branch `trunk`

#### Scenario: A single-branch clone
- **WHEN** a clone made with `--single-branch -b feature` holds the remote-tracking branch `origin/feature` only, with the fetch refspec `+refs/heads/feature:refs/remotes/origin/feature`, and `init --non-interactive --check scripts/ci --default-branch main` runs
- **THEN** it exits 0 and the loaded config has default branch `main`

#### Scenario: Another up-to-date ref
- **WHEN** a clone with the default fetch refspec has the remote-tracking branch `origin/main` only and `init --non-interactive --check scripts/ci --default-branch trunk --require-up-to-date upstream/trunk` runs
- **THEN** it exits 0 and the loaded config has default branch `trunk`

### Requirement: A refused install can be retried
When `install` refused and `init` exited 1 after it wrote `.prepush-ci.toml`, running `init` again, with no flag whose value differs from that config, SHALL leave the config as it is, run `install` again and then do the steps after it as a first run with the same flags would, once what `install` refused has been fixed.

#### Scenario: Second run after a refusal
- **WHEN** `init --non-interactive --check scripts/ci` exited 1 because `.pre-commit-config.yaml` held `repos: [{repo: local}]`, the file was changed to a block list, and `init --non-interactive` runs
- **THEN** it exits 0, `.prepush-ci.toml` has the same contents and modification time as after the first run, the file holds the `prepush-ci` block, `.claude/hooks/session-start.sh` exists, and `.claude/settings.json` registers the script in `hooks.SessionStart`
