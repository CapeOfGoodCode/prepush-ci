## MODIFIED Requirements

### Requirement: The reference lists every command and flag
The README SHALL have a command reference with an entry for each of `init`, `install`, `hook commit-msg`, `hook pre-push`, `run`, `verify`, `land`, `strip`, `doctor`, `skill`, `report` and `app setup`, and the check SHALL fail when the CLI has a command the reference has no entry for, or an entry has no code span or block with its `prepush-ci <command>` synopsis. The synopsis of an entry SHALL name every flag the `--help` of that command lists, `-h` and `--help` apart.

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

#### Scenario: The app setup command left out
- **WHEN** the check reads a README text without any entry for `app setup`
- **THEN** it reports that `app setup` has no entry

#### Scenario: The land command left out
- **WHEN** the check reads a README text without any entry for `land`
- **THEN** it reports that `land` has no entry

## MODIFIED Requirements

### Requirement: The exit statuses are stated
The entries of `run`, `verify`, `doctor`, `strip`, `report` and `land` SHALL state their exit statuses, as the scenarios below give them. The entry of `init` SHALL state that it exits 2 when `--check` is missing and no config exists.

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

#### Scenario: Exit statuses of land
- **WHEN** a reader looks at the entry of `land`
- **THEN** it says exit 0 means landed or already on the branch, exit 1 that it refused or failed and exit 2 that the parser rejected the command line
