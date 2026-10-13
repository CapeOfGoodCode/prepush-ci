## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: The other requirements describe native hooks
The requirements of this specification about the hooks directory, the previous directory, forwarding, the recorded interpreter and `core.hooksPath` SHALL describe the native hooks only, except the two that refuse a manager while the native hooks hold `core.hooksPath`. For a manager, `install` SHALL NOT create the hooks directory or the files `python` and `previous`.

#### Scenario: No native files for a manager
- **WHEN** `install --hooks husky` ran in a repository whose `.git/hooks/pre-push` exists
- **THEN** the directory `prepush-ci/hooks` of the git directory does not exist and `.git/hooks/pre-push` is unchanged
