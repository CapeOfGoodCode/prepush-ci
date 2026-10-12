## MODIFIED Requirements

### Requirement: A demanding tip runs the check
When a pushed tip demands the check, the hook SHALL run the `check` of the worktree config (the tip's own) through the shell from the repository root, whatever `PREPUSH_CI` is other than `off`, show its output and exit non-zero when the check does. It SHALL run the check only after the requirements of the `preflight` capability pass, and SHALL skip it only for a cached pass as the `run-cache` capability specifies. Several pushed refs with one demanding tip SHALL run it once.

#### Scenario: Check passes
- **WHEN** a tip with the trailer is pushed and the check exits 0
- **THEN** the push succeeds

#### Scenario: Check fails
- **WHEN** a tip with the trailer is pushed and the check exits 1
- **THEN** the push is aborted, nothing reaches the remote, and the output names the check

#### Scenario: Variable unset
- **WHEN** a tip with the trailer is pushed with `PREPUSH_CI` unset
- **THEN** the check runs

#### Scenario: Check runs from the repository root
- **WHEN** a tip with the trailer is pushed from a subdirectory and the check writes its working directory to a file
- **THEN** the file holds the repository root

#### Scenario: Two refs, one tip
- **WHEN** `git push origin main:a main:b` pushes one tip with the trailer to two branches
- **THEN** the check runs exactly once
