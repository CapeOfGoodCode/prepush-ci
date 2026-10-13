## MODIFIED Requirements

### Requirement: Every command handles non-ASCII names the same way
`doctor`, `init`, `install`, `run` and the hooks SHALL work in a repository whose path, remotes, branches, hooks directory and templates have non-ASCII names, and with non-ASCII arguments and answers, and with a non-ASCII value in the config that a command hands on to git (the trailer), under both locales above; the hooks that pre-commit runs only as far as pre-commit itself runs under the locale.

#### Scenario: A remote with a non-ASCII name matches the config
- **WHEN** the remote `oré` has the branch `main`, the config says `require_up_to_date = "oré/main"` and `doctor` runs
- **THEN** the `up-to-date` line starts with `ok`

#### Scenario: Run with a remote that has a non-ASCII name is not refused
- **WHEN** the config says `require_up_to_date = "oré/main"`, the remote `oré` has `main` and `run` checks the tip
- **THEN** `run` does not refuse for a missing remote

#### Scenario: Doctor and init work in a repository whose path is non-ASCII
- **WHEN** the repository lives in a directory named `dé` and `doctor --hooks none` and `init --non-interactive --check true --hooks none --ci none` run in it
- **THEN** neither prints a traceback and `init` writes `.prepush-ci.toml` and exits 0

#### Scenario: Install writes the hooks in a non-ASCII path and says so once
- **WHEN** the repository lives in a directory named `dé` and `install --hooks native` runs twice
- **THEN** the first run exits 0 and writes the hook scripts, and the second prints `already installed` and changes no file

#### Scenario: Init sees the previous hook in a non-ASCII hooks directory
- **WHEN** `core.hooksPath` is a directory named `pré` that holds a `pre-push` hook and interactive `init` asks which hooks to set up
- **THEN** the question names that hook as one that is kept and runs first

#### Scenario: A non-ASCII argument reaches the config
- **WHEN** `init --non-interactive --check "echo é" --hooks none --ci none` runs
- **THEN** it exits 0 and `.prepush-ci.toml` holds `check = "echo é"` as UTF-8

#### Scenario: A non-ASCII answer reaches the config
- **WHEN** interactive `init` reads the check `echo é` from standard input
- **THEN** it exits 0 and `.prepush-ci.toml` holds `check = "echo é"` as UTF-8

#### Scenario: A check with a non-ASCII character runs
- **WHEN** the config says `check = "echo é"` and `run` checks the tip
- **THEN** `run` exits 0 and ends in no traceback, and the check's own output is passed through: it prints `é` in `utf8`, whatever the terminal shows in `ascii`

#### Scenario: A preflight with a non-ASCII character runs
- **WHEN** the config says `preflight = "echo é"`, and `run` checks the tip and `doctor --hooks none` runs
- **THEN** `run` ends in no traceback and the `preflight` line of `doctor` starts with `ok`

#### Scenario: A branch with a non-ASCII name is pushed
- **WHEN** a commit on the branch `fé` is pushed with the pre-push hook installed
- **THEN** the hook reads the ref, runs the check once and the push succeeds

#### Scenario: A commit template in a non-ASCII path is read
- **WHEN** `commit.template` names a file in a directory called `dé`, an editor saves the template untouched, and the commit-msg hook runs
- **THEN** the hook writes no trailer, as it does for any untouched template

#### Scenario: A non-ASCII trailer value is written
- **WHEN** the config says `trailer = { key = "Full-Check", value = "jä" }` and a commit runs with `PREPUSH_CI=full`
- **THEN** the hook exits 0, prints no traceback, and the commit message holds the line `Full-Check: jä` as UTF-8
