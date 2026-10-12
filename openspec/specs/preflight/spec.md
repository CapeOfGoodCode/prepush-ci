# preflight Specification

## Purpose
What the `pre-push` hook verifies before it runs the check: the required environment variables, that the branch contains the default branch (fetched, never assumed), and the `preflight` command. A requirement that does not hold refuses the push, and nothing but `require_up_to_date = false` (for the up-to-date step) turns a step off.

## Requirements

### Requirement: Required variables
Before the check, the hook SHALL require every variable named in `require_env` to be set and non-empty in its own environment. When any is not, it SHALL refuse the push without fetching, running the `preflight` command or running the check, and the reason SHALL name every missing variable.

#### Scenario: All variables set
- **WHEN** the config sets `require_env = ["DATABASE_URL"]`, `DATABASE_URL` is set to a value and a tip with the trailer is pushed
- **THEN** the check runs

#### Scenario: Variable unset
- **WHEN** the config sets `require_env = ["DATABASE_URL"]`, `DATABASE_URL` is unset and a tip with the trailer is pushed
- **THEN** the push is refused, the check does not run and the reason names `DATABASE_URL`

#### Scenario: Variable empty
- **WHEN** the config sets `require_env = ["DATABASE_URL"]`, `DATABASE_URL` is the empty string and a tip with the trailer is pushed
- **THEN** the push is refused and the check does not run

#### Scenario: Missing variable stops the fetch
- **WHEN** the config sets `require_env = ["DATABASE_URL"]`, `DATABASE_URL` is unset, the remote `origin` is unreachable and a tip with the trailer is pushed
- **THEN** the push is refused and the reason names `DATABASE_URL` and does not mention a failed fetch

#### Scenario: Several variables missing
- **WHEN** the config sets `require_env = ["A_URL", "B_URL"]` and neither is set
- **THEN** the reason names `A_URL` and `B_URL`

### Requirement: The preflight command
When the config sets `preflight`, the hook SHALL run it, after the variables are verified and before the check, through the shell from the repository root with its output shown. When it exits non-zero the hook SHALL refuse the push without running the check, and the reason SHALL name the command and its exit status.

#### Scenario: Preflight passes
- **WHEN** the config sets a `preflight` that exits 0 and a tip with the trailer is pushed
- **THEN** the preflight runs, then the check runs

#### Scenario: Preflight fails
- **WHEN** the config sets a `preflight` that exits 3 and a tip with the trailer is pushed
- **THEN** the push is refused, the check does not run and the reason names the command and `3`

#### Scenario: Preflight runs from the repository root
- **WHEN** a tip with the trailer is pushed from a subdirectory and the `preflight` writes its working directory to a file
- **THEN** the file holds the repository root

#### Scenario: Missing variable stops the preflight
- **WHEN** the config sets `require_env = ["DATABASE_URL"]` and a `preflight`, `DATABASE_URL` is unset and a tip with the trailer is pushed
- **THEN** the preflight does not run

### Requirement: Preflight fails, never skips
No value of `PREPUSH_CI` and no config key other than `require_up_to_date = false` (for the up-to-date step only) SHALL let a demanding tip reach the check without the variables verified and the `preflight` command run. A preflight that cannot run SHALL fail the push.

#### Scenario: Preflight command not found
- **WHEN** the config sets `preflight = "no-such-command-here"` and a tip with the trailer is pushed
- **THEN** the push is refused and the check does not run

#### Scenario: Unset mode still preflights
- **WHEN** `PREPUSH_CI` is unset, the config sets a failing `preflight` and a tip with the trailer is pushed
- **THEN** the push is refused and the check does not run

#### Scenario: Order of the steps
- **WHEN** a tip with the trailer is pushed and the config sets a `preflight` and a `check` that each append their name to one file
- **THEN** the file lists the preflight before the check

### Requirement: The branch must contain the default branch
When `require_up_to_date` is set, the hook SHALL fetch that ref from its remote and require it to be an ancestor of `HEAD` (or equal to it). Otherwise it SHALL refuse the push without running the `preflight` command or the check, and the reason SHALL name the ref and say to rebase onto it or merge it.

#### Scenario: Branch contains the default branch
- **WHEN** the remote `main` is an ancestor of `HEAD` and a tip with the trailer is pushed
- **THEN** the check runs

#### Scenario: Branch is behind
- **WHEN** another clone pushed a commit to the remote `main` that `HEAD` does not contain and a tip with the trailer is pushed
- **THEN** the push is refused, the check does not run and the reason names `origin/main` and says to rebase or merge

#### Scenario: Behind branch stops the preflight
- **WHEN** the remote `main` has a commit `HEAD` does not contain, the config sets a `preflight` that writes a file and a tip with the trailer is pushed
- **THEN** the push is refused and the file does not exist

#### Scenario: Branch is the default branch tip
- **WHEN** `HEAD` is the remote `main` itself and a tip with the trailer is pushed
- **THEN** the check runs

#### Scenario: A stale tracking ref does not decide
- **WHEN** the local `origin/main` is an ancestor of `HEAD` but the remote `main` has moved on to a commit `HEAD` does not contain
- **THEN** the push is refused

#### Scenario: Configured ref
- **WHEN** the config sets `require_up_to_date = "upstream/develop"` and the remote `upstream` has a `develop` that `HEAD` does not contain
- **THEN** the push is refused and the reason names `upstream/develop`

#### Scenario: Branch name with a slash
- **WHEN** the config sets `require_up_to_date = "origin/release/1"` and the remote has a `release/1` that `HEAD` does not contain
- **THEN** the push is refused and the reason names `origin/release/1`

### Requirement: The fetch must succeed
A fetch that fails, a ref that is not `<remote>/<branch>` of a configured remote and a `git merge-base` that fails for a reason other than "not an ancestor" SHALL refuse the push without running the `preflight` command or the check, with a reason that names the cause. None of them SHALL count as up to date.

#### Scenario: Remote unreachable
- **WHEN** the remote's URL points to a directory that does not exist and a tip with the trailer is pushed
- **THEN** the push is refused, the check does not run and the reason says the fetch failed

#### Scenario: Remote not configured
- **WHEN** the config sets `require_up_to_date = "upstream/develop"` and the repository has no remote `upstream`
- **THEN** the push is refused and the reason names `upstream`

#### Scenario: Ref without a remote
- **WHEN** the config sets `require_up_to_date = "main"`
- **THEN** the push is refused and the reason says the ref must be `<remote>/<branch>`

### Requirement: A refused fetch names a way out
A ref the remote does not have, including the default branch of an empty remote, SHALL refuse the push like any failed fetch; it SHALL NOT count as up to date. Every refusal of the previous requirement SHALL name two ways out: `require_up_to_date = false` in the config, and pushing a tip without the trailer, which runs no check.

#### Scenario: Branch missing on the remote
- **WHEN** `require_up_to_date = "origin/gone"` and the remote has no `gone`
- **THEN** the push is refused, the check does not run and the reason says the fetch failed

#### Scenario: First push to an empty remote
- **WHEN** the remote is a new bare repository without branches, the config keeps the default `require_up_to_date` and a tip with the trailer is pushed
- **THEN** the push is refused and the check does not run

#### Scenario: The reason names a way out
- **WHEN** a tip with the trailer is pushed to an empty remote
- **THEN** the reason names `require_up_to_date = false` and says a tip without the trailer can be pushed

#### Scenario: Pushing without the trailer gets past an empty remote
- **WHEN** the remote is a new bare repository without branches and a tip without the trailer is pushed
- **THEN** the push succeeds

### Requirement: The up-to-date check can be disabled
With `require_up_to_date = false` the hook SHALL NOT fetch and SHALL NOT compare, and the preflight steps SHALL still run.

#### Scenario: Disabled and behind
- **WHEN** the config sets `require_up_to_date = false`, the remote `main` has a commit `HEAD` does not contain and a tip with the trailer is pushed
- **THEN** the check runs

#### Scenario: Disabled does not fetch
- **WHEN** the config sets `require_up_to_date = false`, the remote `origin` is unreachable and a tip with the trailer is pushed to a second, reachable remote
- **THEN** the check runs

#### Scenario: Disabled does not skip the variables
- **WHEN** the config sets `require_up_to_date = false` and `require_env = ["DATABASE_URL"]`, which is unset
- **THEN** the push is refused

### Requirement: Only a demanding tip is preflighted
The hook SHALL verify variables, run the `preflight` command and fetch only when at least one pushed branch tip demands the check and no earlier refusal applies. Tips without the trailer, tags and deletions SHALL NOT.

#### Scenario: Tip without the trailer
- **WHEN** the config sets a failing `preflight` and `require_env = ["DATABASE_URL"]`, which is unset, and a tip without the trailer is pushed
- **THEN** the push succeeds and neither runs

#### Scenario: Tag push
- **WHEN** the same config is in place and a tag that points at a commit with the trailer is pushed
- **THEN** the push succeeds
