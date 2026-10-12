## ADDED Requirements

### Requirement: Run checks HEAD
`prepush-ci run` SHALL, from any directory inside a worktree, require `HEAD` to point to a commit, then require the worktree to be clean and free of hidden changes with the same rules and reasons as the `pre-push-hook` capability, then satisfy the `preflight` capability, then run the `check` of the worktree config through the shell from the repository root with its output shown. It SHALL exit 0 when the check exits 0 and 1 in every other case, and SHALL run nothing after a refusal.

#### Scenario: Check passes
- **WHEN** the worktree is clean and the check exits 0
- **THEN** `prepush-ci run` exits 0

#### Scenario: Check fails
- **WHEN** the check exits 1
- **THEN** `prepush-ci run` exits 1 and the output names the check

#### Scenario: Run from a subdirectory
- **WHEN** `prepush-ci run` starts in a subdirectory and the check writes its working directory to a file
- **THEN** the file holds the repository root

#### Scenario: Dirty worktree
- **WHEN** a tracked file is modified and `prepush-ci run` starts
- **THEN** it exits 1, the check does not run and the reason names the file

#### Scenario: Preflight fails
- **WHEN** the config sets a failing `preflight`
- **THEN** `prepush-ci run` exits 1 and the check does not run

#### Scenario: Preflight before check
- **WHEN** the config sets a `preflight` and a `check` that each append their name to one file
- **THEN** `prepush-ci run` leaves the preflight listed before the check

#### Scenario: Invalid config
- **WHEN** the config contains an unknown key
- **THEN** `prepush-ci run` exits 1 and the error names the key

#### Scenario: No commit
- **WHEN** `prepush-ci run` starts in a repository without a commit
- **THEN** it exits 1 and the check does not run

### Requirement: Run is not a hook
`prepush-ci run` SHALL NOT read `PREPUSH_CI` and SHALL NOT require `HEAD` to carry the trailer. It SHALL always run the check and SHALL NOT answer from the cache.

#### Scenario: No trailer
- **WHEN** `HEAD` has no trailer and `prepush-ci run` starts
- **THEN** the check runs

#### Scenario: Mode off
- **WHEN** `PREPUSH_CI=off` and `prepush-ci run` starts
- **THEN** the check runs

#### Scenario: Run after a cached pass
- **WHEN** `prepush-ci run` passed on `HEAD` and runs again
- **THEN** the check runs again

### Requirement: A pass is cached
When the check passes in `prepush-ci run` or in the pre-push hook, and `cache` is `true`, the tool SHALL record the pass under `prepush-ci/` in the repository's git directory, for the key made of the commit sha of `HEAD`, its tree hash and the values of `check`, `preflight`, `require_env` and `require_up_to_date`. It SHALL record nothing when the check fails or a refusal stops the run.

#### Scenario: Pass is recorded
- **WHEN** `prepush-ci run` passes
- **THEN** the git directory holds a record under `prepush-ci/`

#### Scenario: Failure is not recorded
- **WHEN** `prepush-ci run` fails because the check exits 1
- **THEN** the git directory holds no record

#### Scenario: Refusal is not recorded
- **WHEN** `prepush-ci run` is refused because the worktree is dirty
- **THEN** the git directory holds no record

#### Scenario: Hook pass is recorded
- **WHEN** a push of a tip with the trailer passes the check in the hook
- **THEN** the git directory holds a record under `prepush-ci/`

### Requirement: A cached pass skips the check in the hook
When the pre-push hook has satisfied every requirement that precedes the check, including the preflight, and the cache holds a record for the key of the pushed tip, it SHALL NOT run the check, SHALL print a line on standard error that names the commit and says the check passed earlier, and SHALL let the push go on.

#### Scenario: Run, then push
- **WHEN** `prepush-ci run` passed on a commit with the trailer and the commit is pushed
- **THEN** the push succeeds, the check ran exactly once and the hook said it skipped the check

#### Scenario: Retried push
- **WHEN** the remote rejects a push after the hook passed, and the same commit is pushed again
- **THEN** the check ran exactly once and the second push said it skipped the check

#### Scenario: Preflight still runs
- **WHEN** a pass is cached for the tip, the config sets `preflight = "test -f ready"` unchanged, and the file `ready` that made it pass is deleted before the commit is pushed
- **THEN** the push is refused, the reason names the preflight and the check does not run

#### Scenario: Refusals still apply
- **WHEN** a pass is cached for the tip and the worktree is dirty
- **THEN** the push is refused

### Requirement: The key follows the state
A record SHALL count only for the exact key it was made for. Another commit sha, another tree hash or another value of `check`, `preflight`, `require_env` or `require_up_to_date` SHALL be a miss and the check SHALL run.

#### Scenario: New commit
- **WHEN** a pass is cached and the commit is amended with a new message, which keeps the tree
- **THEN** pushing it runs the check

#### Scenario: Changed check command
- **WHEN** a pass is cached, the worktree config is an ignored file and its `check` is changed to another command that passes
- **THEN** pushing the same commit runs the check

#### Scenario: Changed required variables
- **WHEN** a pass is cached, the worktree config is an ignored file and its `require_env` gains a variable that is set
- **THEN** pushing the same commit runs the check

#### Scenario: Other keys do not matter
- **WHEN** a pass is cached, the worktree config is an ignored file and only its `default_branch` changes
- **THEN** pushing the same commit skips the check

### Requirement: The cache can be turned off
With `cache = false` the tool SHALL neither read nor write the cache: `prepush-ci run` SHALL record no pass and the hook SHALL NOT skip the check for a record that exists.

#### Scenario: Disabled run records nothing
- **WHEN** the config sets `cache = false` and `prepush-ci run` passes
- **THEN** the git directory holds no record

#### Scenario: Disabled hook ignores a record
- **WHEN** a pass is cached, the worktree config is an ignored file that now sets `cache = false`, and the commit is pushed
- **THEN** the check runs

#### Scenario: Disabled hook records nothing
- **WHEN** the config sets `cache = false` and a push of a tip with the trailer passes the check
- **THEN** the git directory holds no record

### Requirement: A cache that cannot be trusted is a miss
A record that is missing, empty, truncated or made for another key SHALL be a miss, and the check SHALL run. A cache that cannot be written SHALL produce a warning on standard error and SHALL NOT change the exit code of `run` or the hook's decision about the push.

#### Scenario: Damaged record
- **WHEN** the record of a cached pass is truncated to zero bytes and the commit is pushed
- **THEN** the check runs

#### Scenario: Record for another key
- **WHEN** the record of a cached pass is overwritten with the record of another commit and the commit is pushed
- **THEN** the check runs

#### Scenario: Unwritable cache
- **WHEN** `prepush-ci/` in the git directory is a regular file and `prepush-ci run` passes
- **THEN** it exits 0 and warns that the pass could not be cached

#### Scenario: Unwritable cache in the hook
- **WHEN** `prepush-ci/` in the git directory is a regular file and a tip with the trailer is pushed whose check passes
- **THEN** the push succeeds and a warning says the pass could not be cached

#### Scenario: Unwritable cache and a failing check
- **WHEN** `prepush-ci/` in the git directory is a regular file and the check exits 1
- **THEN** `prepush-ci run` exits 1
