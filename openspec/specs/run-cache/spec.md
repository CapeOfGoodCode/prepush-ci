# run-cache Specification

## Purpose
`prepush-ci run`, which starts the pre-push hook's sequence by hand on HEAD, and the result refs under `refs/prepush-ci/results/` that let the hook skip a check that already passed on exactly that tree with the same inputs, whatever commit it was made for. The cache can only cost time: anything damaged, stale or unwritable means the check runs.

## Requirements

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
When the check passes in `prepush-ci run` or in the pre-push hook, and `cache` is `true`, the tool SHALL record the pass as the ref `refs/prepush-ci/results/<tree>-<config>` of the key defined below, read before the preflight starts. The ref SHALL point at a commit of that tree whose message names the commit that was checked. It SHALL record nothing when the check fails or a refusal stops the run.

#### Scenario: Pass is recorded
- **WHEN** `prepush-ci run` passes
- **THEN** exactly one ref exists under `refs/prepush-ci/results/`, its name starts with the tree of `HEAD`, and the tree of the commit it points at is that tree

#### Scenario: Failure is not recorded
- **WHEN** `prepush-ci run` fails because the check exits 1
- **THEN** no ref exists under `refs/prepush-ci/results/`

#### Scenario: Refusal is not recorded
- **WHEN** `prepush-ci run` is refused because the worktree is dirty
- **THEN** no ref exists under `refs/prepush-ci/results/`

#### Scenario: Hook pass is recorded
- **WHEN** a push of a tip with the trailer passes the check in the hook
- **THEN** a ref exists under `refs/prepush-ci/results/` for the tree of the tip

#### Scenario: Commit made during the check
- **WHEN** the check makes a commit that adds a file, and then passes
- **THEN** the ref is for the tree that was checked, and a push of the new commit runs the check

### Requirement: A cached pass skips the check in the hook
When the pre-push hook has satisfied every requirement that precedes the check, including the preflight, and a result ref exists for the tree of the pushed tip and the current inputs, it SHALL NOT run the check, SHALL print a line on standard error that names the tree and the commit that passed, each by its first twelve characters, and says the check passed earlier, and SHALL let the push go on.

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

#### Scenario: The line names the commit that passed
- **WHEN** a pass is cached for a commit, the commit is amended with a new message, and the amended commit is pushed
- **THEN** the hook's line holds the first twelve characters of the tree and the first twelve characters of the commit that passed, and not the first twelve characters of the amended commit

### Requirement: The cache can be turned off
With `cache = false` the tool SHALL neither read nor write result refs: `prepush-ci run` SHALL record no pass and the hook SHALL NOT skip the check for a ref that exists.

#### Scenario: Disabled run records nothing
- **WHEN** the config sets `cache = false` and `prepush-ci run` passes
- **THEN** no ref exists under `refs/prepush-ci/results/`

#### Scenario: Disabled hook ignores a record
- **WHEN** a pass is cached, the worktree config is an ignored file that now sets `cache = false`, and the commit is pushed
- **THEN** the check runs

#### Scenario: Disabled hook records nothing
- **WHEN** the config sets `cache = false` and a push of a tip with the trailer passes the check
- **THEN** no ref exists under `refs/prepush-ci/results/`

### Requirement: A cache that cannot be trusted is a miss
A result ref that is missing, unreadable or points at a commit of another tree SHALL be a miss, and the check SHALL run. A ref that cannot be written SHALL produce a warning on standard error and SHALL NOT change the exit code of `run` or the hook's decision about the push.

#### Scenario: Damaged record
- **WHEN** the file of the ref of a cached pass is emptied and the commit is pushed
- **THEN** the check runs

#### Scenario: Record for another key
- **WHEN** the ref of a cached pass is moved to a commit of another tree and the commit is pushed
- **THEN** the check runs

#### Scenario: Unwritable cache
- **WHEN** `refs/prepush-ci` in the git directory is a regular file and `prepush-ci run` passes
- **THEN** it exits 0 and warns that the pass could not be cached

#### Scenario: Unwritable cache in the hook
- **WHEN** `refs/prepush-ci` in the git directory is a regular file and a tip with the trailer is pushed whose check passes
- **THEN** the push succeeds and a warning says the pass could not be cached

#### Scenario: Unwritable cache and a failing check
- **WHEN** `refs/prepush-ci` in the git directory is a regular file and the check exits 1
- **THEN** `prepush-ci run` exits 1

### Requirement: The result is keyed by the tree and the inputs
A result ref SHALL count only for the key it was made for: `<tree>` is the tree hash of `HEAD` and `<config>` a hash of `check`, `preflight`, `require_env`, `require_up_to_date` and the standard output of the `preflight` command. Another value of any of them SHALL be a miss and the check SHALL run; another commit with the same key SHALL be a hit. The output of the `preflight` SHALL still reach standard output.

#### Scenario: Amended message keeps the result
- **WHEN** a pass is cached and the commit is amended with a new message, which keeps the tree
- **THEN** pushing it skips the check

#### Scenario: Squashed commits keep the result
- **WHEN** a pass is cached for a tip with the trailer, and the tip and its parent are squashed into one commit with the trailer, which keeps the tree
- **THEN** pushing the new tip skips the check

#### Scenario: Another tree
- **WHEN** a pass is cached and a commit that changes a file is made and pushed
- **THEN** the check runs

#### Scenario: Changed check command
- **WHEN** a pass is cached, the worktree config is an ignored file and its `check` is changed to another command that passes
- **THEN** pushing the same commit runs the check

#### Scenario: Changed required variables
- **WHEN** a pass is cached, the worktree config is an ignored file and its `require_env` gains a variable that is set
- **THEN** pushing the same commit runs the check

#### Scenario: Other keys do not matter
- **WHEN** a pass is cached, the worktree config is an ignored file and only its `default_branch` changes
- **THEN** pushing the same commit skips the check

#### Scenario: Changed tool version
- **WHEN** the config sets `preflight = "echo $TOOL_VERSION"`, a pass is cached with `TOOL_VERSION=1`, and the commit is pushed with `TOOL_VERSION=2`
- **THEN** the check runs

#### Scenario: Same tool version
- **WHEN** the config sets `preflight = "echo $TOOL_VERSION"`, a pass is cached with `TOOL_VERSION=1`, and the commit is pushed with `TOOL_VERSION=1`
- **THEN** the push skips the check

#### Scenario: The preflight's output is still shown
- **WHEN** the config sets `preflight = "echo versions-ok"` and `prepush-ci run` starts
- **THEN** its standard output contains `versions-ok`

### Requirement: The preflight's error stream stays its own
The standard error of the `preflight` command SHALL reach standard error only, never the standard output nor the key. The order between its standard output and its standard error need not be kept when both end in one place.

#### Scenario: The preflight's error stream stays its own
- **WHEN** the config sets `preflight = "echo to-out; echo to-err >&2"` and `prepush-ci run` starts
- **THEN** `to-err` appears on standard error only and `to-out` on standard output only

#### Scenario: The preflight's error stream is not in the key
- **WHEN** the config sets `preflight = "echo $TOOL_VERSION >&2"`, a pass is cached with `TOOL_VERSION=1`, and the commit is pushed with `TOOL_VERSION=2`
- **THEN** the push skips the check
