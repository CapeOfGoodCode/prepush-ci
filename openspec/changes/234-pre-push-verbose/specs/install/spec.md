## REMOVED Requirements

### Requirement: pre-commit shows the warning of its commit-msg hook
**Reason**: The `pre-push` hook has messages of its own to show; the requirement now covers both hooks.
**Migration**: "pre-commit shows the messages of its hooks".

## ADDED Requirements

### Requirement: pre-commit shows the messages of its hooks
Both hooks that `install` adds to `.pre-commit-config.yaml` SHALL set `verbose: true`, because pre-commit hides the output of a hook that passes, and neither the warning of the `commit-msg` hook nor what the `pre-push` hook says about a reused or unshared result would be seen.

#### Scenario: The setting is written
- **WHEN** `install` runs for pre-commit
- **THEN** the `commit-msg` hook and the `pre-push` hook of the block both hold `verbose: true`

#### Scenario: A block of an earlier version gets it
- **WHEN** the block in `.pre-commit-config.yaml` has a `pre-push` hook without `verbose: true`, a hook of the user follows it, and `install` runs
- **THEN** it prints `updated`, the `pre-push` hook of the block holds `verbose: true` and the lines outside the block are as they were

#### Scenario: A push shows why the check was not run
- **WHEN** `install` and `pre-commit install` ran, the check passed on a tree, and an amended commit of that tree with the trailer is pushed
- **THEN** the push succeeds and its output contains `not run again`
