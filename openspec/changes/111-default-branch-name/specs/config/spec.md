## ADDED Requirements

### Requirement: The default branch is a branch name
The tool SHALL reject a `default_branch` that begins with `refs/` or with `origin/`, naming `default_branch` and exiting non-zero. A name that merely contains a slash SHALL load.

#### Scenario: A branch name with a slash
- **WHEN** the config sets `default_branch = "release/1"`
- **THEN** the config loads with default branch `release/1` and up-to-date ref `origin/release/1`

#### Scenario: Reported with the other problems
- **WHEN** the config contains an unknown key `foo` and sets `default_branch = "refs/heads/main"`
- **THEN** the tool reports both `foo` and `default_branch` and exits non-zero

### Requirement: The refusal says which branch to write
When the rejected value begins with `refs/remotes/origin/`, `refs/heads/` or `origin/` (checked in that order) and the rest is not empty, the message SHALL contain the phrase `use "<rest>"`, `<rest>` being the value without that prefix. For any other rejected value, the message SHALL say that a branch name is expected and SHALL NOT contain `use "`.

#### Scenario: A full remote-tracking ref
- **WHEN** the config sets `default_branch = "refs/remotes/origin/trunk"`
- **THEN** the tool reports `default_branch`, the message contains `use "trunk"` and it exits non-zero

#### Scenario: A full local ref
- **WHEN** the config sets `default_branch = "refs/heads/release/1"`
- **THEN** the tool reports `default_branch`, the message contains `use "release/1"` and it exits non-zero

#### Scenario: A remote-tracking name
- **WHEN** the config sets `default_branch = "origin/trunk"`
- **THEN** the tool reports `default_branch`, the message contains `use "trunk"` and it exits non-zero

#### Scenario: A ref without a branch to suggest
- **WHEN** the config sets `default_branch = "refs/tags/v1"`
- **THEN** the tool reports `default_branch`, the message says a branch name is expected, does not contain `use "` and it exits non-zero

#### Scenario: Nothing after the prefix
- **WHEN** the config sets `default_branch = "origin/"`
- **THEN** the tool reports `default_branch`, the message does not contain `use "` and it exits non-zero
