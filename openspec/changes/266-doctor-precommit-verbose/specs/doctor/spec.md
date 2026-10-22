## ADDED Requirements

### Requirement: The pre-push hook of a pre-commit block shows its messages
For pre-commit, the `pre-push` check SHALL also require that the hook with the id `prepush-ci-pre-push` in the block holds the line `verbose: true`, because pre-commit hides what a passing hook prints. This SHALL be checked after the block is found and before the activation. A failed check SHALL name `.pre-commit-config.yaml` and `verbose: true`, and its fix line SHALL contain `prepush-ci install`. The `commit-msg` check, the other managers and the native hooks SHALL not be affected.

#### Scenario: A block of an earlier version
- **WHEN** the pre-push hook of the block in `.pre-commit-config.yaml` has no `verbose` key and `pre-commit install` ran
- **THEN** the `pre-push` line starts with `fail` and names `.pre-commit-config.yaml` and `verbose: true`, the fix line contains `prepush-ci install`, and the `commit-msg` line starts with `ok`

#### Scenario: The key is there
- **WHEN** `install` and `pre-commit install` ran
- **THEN** the `pre-push` line starts with `ok`

#### Scenario: The key is false
- **WHEN** the pre-push hook of the block holds `verbose: false`
- **THEN** the `pre-push` line starts with `fail` and names `verbose: true`

#### Scenario: The key is only a comment
- **WHEN** the pre-push hook of the block holds the line `# verbose: true` and no other `verbose` line
- **THEN** the `pre-push` line starts with `fail`

#### Scenario: The key is on the other hook
- **WHEN** the `commit-msg` hook of the block holds `verbose: true` and the pre-push hook has no `verbose` key
- **THEN** the `pre-push` line starts with `fail`

#### Scenario: The commit-msg hook lacks it
- **WHEN** the pre-push hook of the block holds `verbose: true` and the `commit-msg` hook has no `verbose` key
- **THEN** the `commit-msg` and `pre-push` lines start with `ok`

#### Scenario: The fix works
- **WHEN** `install` runs after the check failed for the missing key, and `doctor` runs again
- **THEN** the `pre-push` line starts with `ok`

#### Scenario: The key is reported before the activation
- **WHEN** the pre-push hook of the block has no `verbose` key and `pre-commit install` did not run
- **THEN** the `pre-push` line starts with `fail` and names `verbose: true`

#### Scenario: Other managers do not need it
- **WHEN** husky or lefthook is the manager and `install` ran
- **THEN** the `pre-push` line does not name `verbose`
