## MODIFIED Requirements

### Requirement: pre-commit entries
For pre-commit, `install` SHALL add to the end of the `repos:` list a `- repo: local` entry with a hook for the `commit-msg` stage that runs `prepush-ci hook commit-msg` (pre-commit appends the message file) and a hook for the `pre-push` stage that runs `prepush-ci hook pre-push` with `pass_filenames: false` and `always_run: true`. Both hooks SHALL use `language: system`. `repos:` SHALL be a block list or `[]`; otherwise `install` SHALL exit 1, naming `repos`, and change nothing.

#### Scenario: Trailer written through pre-commit
- **WHEN** `install` ran for a `.pre-commit-config.yaml` that lists another hook, `pre-commit install` ran, and `git commit -m "add x"` runs with `PREPUSH_CI=full`
- **THEN** the commit's message ends with the trailer `Prepush-CI: full` and the other hook ran

#### Scenario: Check run on push through pre-commit
- **WHEN** `install` and `pre-commit install` ran, the config's `check` writes a marker file, and `git push origin main` pushes a clean, checked-out commit that carries the trailer
- **THEN** the marker file exists and the push reaches the remote

#### Scenario: Failing check refuses the push through pre-commit
- **WHEN** `install` and `pre-commit install` ran, the config's `check` exits 1, and `git push origin main` pushes a clean, checked-out commit that carries the trailer
- **THEN** the push is refused and the remote has no new commit

#### Scenario: Entry goes after the existing repos
- **WHEN** `.pre-commit-config.yaml` lists two repos, followed by the key `exclude: '^vendor/'`, and `install` runs
- **THEN** the block follows the second repo and precedes `exclude`, with the indentation of the other `- repo:` lines, and both repos and `exclude` are unchanged

#### Scenario: Repos is not a block list
- **WHEN** `.pre-commit-config.yaml` contains `repos: [{repo: local}]` and `install` runs
- **THEN** it exits 1, the message names `repos` and the file has the same contents as before

#### Scenario: Repos is an empty list
- **WHEN** `.pre-commit-config.yaml` contains `repos: []` and `install` runs, then `pre-commit validate-config` runs on the file
- **THEN** `install` exits 0, the file has the line `repos:` followed by the block, its entries indented by two spaces, and `pre-commit validate-config` exits 0

#### Scenario: An empty list with a comment
- **WHEN** `.pre-commit-config.yaml` contains `repos: [] # none` and `install` runs
- **THEN** `install` exits 0 and the file has the line `repos: # none` followed by the block
