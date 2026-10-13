## ADDED Requirements

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
