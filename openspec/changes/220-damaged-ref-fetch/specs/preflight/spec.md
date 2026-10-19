## ADDED Requirements

### Requirement: A damaged ref under refs/prepush-ci does not fail the fetch
The fetch of the up-to-date step SHALL NOT fail because a ref under `refs/prepush-ci` is damaged: `refs/prepush-ci` being a regular file, a result ref whose file is empty, or a ref under it whose name git refuses. The step SHALL then decide as it does for a healthy repository: refuse when the ref is not contained in `HEAD` or the fetch fails for another reason, go on otherwise.

#### Scenario: Result ref file emptied, hook
- **WHEN** the check passed with `prepush-ci run`, the file of the result ref under `.git/refs/prepush-ci/results/` is emptied, and the same tip with the trailer is pushed to a remote that holds its default branch
- **THEN** the push succeeds and the check runs

#### Scenario: Cache path is a file, hook
- **WHEN** `refs/prepush-ci` in the git directory is a regular file and a tip with the trailer whose check passes is pushed to a remote that holds its default branch
- **THEN** the push succeeds and a warning says the pass could not be cached

#### Scenario: Cache path is a file, run
- **WHEN** `refs/prepush-ci` in the git directory is a regular file, the remote holds the default branch and `prepush-ci run` passes
- **THEN** it exits 0 and warns that the pass could not be cached

#### Scenario: Result ref file emptied, run
- **WHEN** the file of a result ref is emptied, the remote holds the default branch and `prepush-ci run` passes
- **THEN** it exits 0

#### Scenario: A damaged ref does not hide a stale branch
- **WHEN** `refs/prepush-ci` is a regular file and the pushed tip does not contain `origin`'s default branch
- **THEN** the push is refused and the reason names `origin/main` and says to rebase or merge

#### Scenario: A damaged ref does not hide an unreachable remote
- **WHEN** `refs/prepush-ci` is a regular file and the remote's URL points to a directory that does not exist
- **THEN** the push is refused and the reason says the fetch failed

### Requirement: The fetch past a damaged ref SHALL NOT start housekeeping
The fetch of the up-to-date step SHALL NOT run auto-maintenance (`gc --auto`), so that no pruning of history happens while git is told to ignore damaged refs.

#### Scenario: A broken ref holds the only copy of a commit
- **WHEN** a ref under `refs/prepush-ci/results/` with a name git refuses (`bad..name`) holds a commit no other ref holds, git's auto-gc is set to run on every fetch and prune at once, and a tip with the trailer is pushed to a remote that holds its default branch
- **THEN** the push succeeds and the commit still exists
