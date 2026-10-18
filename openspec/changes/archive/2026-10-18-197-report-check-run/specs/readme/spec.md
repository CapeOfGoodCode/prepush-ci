## MODIFIED Requirements

### Requirement: The reference lists every command and flag
The README SHALL have a command reference with an entry for each of `init`, `install`, `hook commit-msg`, `hook pre-push`, `run`, `verify`, `strip`, `doctor`, `skill` and `report`, and the check SHALL fail when the CLI has a command the reference has no entry for, or an entry has no code span or block with its `prepush-ci <command>` synopsis. The synopsis of an entry SHALL name every flag the `--help` of that command lists, `-h` and `--help` apart.

#### Scenario: The shipped reference is complete
- **WHEN** the check reads the `README.md` of the repository and the `--help` of the CLI
- **THEN** every command of the CLI has an entry and every flag of each command appears in its synopsis

#### Scenario: A command left out
- **WHEN** the check reads a README text without any entry for `doctor`
- **THEN** it reports that `doctor` has no entry

#### Scenario: A flag left out
- **WHEN** the check reads a README text whose entry for `init` names every flag of `init` but `--no-session-hook`
- **THEN** it reports `--no-session-hook` as missing from `init`

#### Scenario: The report command left out
- **WHEN** the check reads a README text without any entry for `report`
- **THEN** it reports that `report` has no entry

### Requirement: The exit statuses are stated
The entries of `run`, `verify`, `doctor`, `strip` and `report` SHALL state their exit statuses: `run` and `strip` 0 when they did their work and 1 when they refused or failed; `verify` 0 when the commit is verified and 1 otherwise; `doctor` 0 when every check passed and 1 otherwise; `report` 0 when the result was posted, 1 when it refused or failed and 2 when the parser rejects the command line. The entry of `init` SHALL state that it exits 2 when `--check` is missing and no config exists.

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

#### Scenario: Exit statuses of report
- **WHEN** a reader looks at the entry of `report`
- **THEN** it says exit 0 means the result was posted, exit 1 that it refused or failed and exit 2 that the parser rejected the command line
