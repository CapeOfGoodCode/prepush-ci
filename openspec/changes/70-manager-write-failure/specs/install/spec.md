## MODIFIED Requirements

### Requirement: Manager installs are idempotent
Running `install` again for a manager SHALL write no file when nothing differs, print a line containing `already installed` and exit 0. When the block or the hook types differ it SHALL write the difference and print `updated`. A first run SHALL print `installed`. A run that `install` refuses before its first write SHALL write no file of the manager, also when it would have changed another one first. A write the operating system refuses is handled by "A refused write is undone".

#### Scenario: Second run for each manager
- **WHEN** `install` runs twice in a row for pre-commit, husky and lefthook, each in its own repository
- **THEN** each second run exits 0, prints `already installed`, and every file has the same contents and modification time as after the first run

#### Scenario: First run
- **WHEN** `install` runs for the first time for a manager
- **THEN** the output contains `installed` and not `already installed`

#### Scenario: Refusal after a part is done
- **WHEN** `.husky/commit-msg` is missing, `.husky/pre-push` is a directory and `install --hooks husky` runs
- **THEN** it exits 1 and `.husky/commit-msg` was not created

## ADDED Requirements

### Requirement: A refused write is undone
When the operating system refuses a write while `install` edits the files of a manager, `install` SHALL exit 1 with one message on standard error naming the file, relative to the worktree root, and the reason, and SHALL print no traceback. Every file the run already wrote SHALL be put back (previous contents restored, a created file removed); a file it cannot put back SHALL be named on a line of its own after the message.

#### Scenario: A read-only second file
- **WHEN** `.husky/commit-msg` holds `echo hi`, `.husky/pre-push` is read-only, and `install --hooks husky` runs as a user who may not write it
- **THEN** it exits 1, the message names `.husky/pre-push` and contains `Permission denied`, the output holds no `Traceback`, and `.husky/commit-msg` still holds exactly `echo hi`

#### Scenario: A created file is removed
- **WHEN** `.husky/commit-msg` does not exist, `.husky/pre-push` is read-only, and `install --hooks husky` runs as a user who may not write it
- **THEN** it exits 1 and `.husky/commit-msg` does not exist

#### Scenario: Rerun after the fix
- **WHEN** a refused write left `.husky/pre-push` read-only, the user makes it writable, and `install --hooks husky` runs again
- **THEN** it exits 0, prints `installed`, and both files hold the block
