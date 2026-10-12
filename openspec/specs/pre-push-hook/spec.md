# pre-push-hook Specification

## Purpose
The `pre-push` hook that enforces the trailer: a pushed branch tip that carries it reaches the remote only if it is the checked-out `HEAD`, the worktree is clean and the full check passed on it, so a trailer commit on the remote implies the check passed on exactly that commit.

## Requirements

### Requirement: Pushed refs
`prepush-ci hook pre-push` SHALL read the refs being pushed from git's pre-push protocol on standard input (lines `<local ref> <local sha> <remote ref> <remote sha>`). When standard input holds no lines, it SHALL fall back to the variables pre-commit sets, as the next requirement says. When no ref can be taken from either source it SHALL exit 0.

#### Scenario: Native git push
- **WHEN** the hook is installed as the repository's `pre-push` hook and `git push origin main` pushes a commit that carries the trailer
- **THEN** the hook runs the check on that commit

#### Scenario: No refs
- **WHEN** the hook runs with empty standard input and none of `PRE_COMMIT_TO_REF` and `PRE_COMMIT_LOCAL_BRANCH`
- **THEN** it exits 0 and runs no check

### Requirement: The pre-commit fallback
When standard input holds no lines, the pushed tip SHALL be the sha in `PRE_COMMIT_TO_REF`, otherwise the commit that `PRE_COMMIT_LOCAL_BRANCH` resolves to. `PRE_COMMIT_REMOTE_BRANCH` SHALL be its remote ref, and a missing or empty one SHALL count as a branch. A `PRE_COMMIT_LOCAL_BRANCH` that does not resolve to a commit SHALL refuse the push.

#### Scenario: Run by pre-commit
- **WHEN** `prepush-ci hook pre-push` runs with empty standard input, `PRE_COMMIT_TO_REF` set to the sha of a checked-out commit with the trailer and `PRE_COMMIT_REMOTE_BRANCH` set to `refs/heads/main`
- **THEN** the hook runs the check on that commit

#### Scenario: pre-commit without a remote branch
- **WHEN** the hook runs with empty standard input, `PRE_COMMIT_TO_REF` set to the sha of a checked-out commit with the trailer and no `PRE_COMMIT_REMOTE_BRANCH`
- **THEN** the hook runs the check on that commit

#### Scenario: pre-commit pushes the root commit
- **WHEN** the hook runs with empty standard input, no `PRE_COMMIT_TO_REF`, `PRE_COMMIT_LOCAL_BRANCH` set to `refs/heads/main` and `PRE_COMMIT_REMOTE_BRANCH` set to `refs/heads/main`, and `main` is the checked-out root commit with the trailer
- **THEN** the hook runs the check on that commit

#### Scenario: Unresolvable local branch
- **WHEN** the hook runs with empty standard input, no `PRE_COMMIT_TO_REF` and `PRE_COMMIT_LOCAL_BRANCH` set to `refs/heads/gone`, which does not exist
- **THEN** the push is refused and the error names `refs/heads/gone`

### Requirement: Known limits under pre-commit
pre-commit hands the hook at most one ref and does not run it for refs whose commits the remote already has. The hook SHALL check only the ref it is given and SHALL NOT claim to cover the others; the native `pre-push` hook sees every ref and is the preferred way to install the hook.

#### Scenario: Two refs pushed through pre-commit
- **WHEN** `git push origin main b` runs through pre-commit, `b` has new commits and a tip with the trailer that is not `HEAD`, and pre-commit gives the hook only `main`
- **THEN** the hook checks `main` only and `b` is not refused by it

#### Scenario: Refs the remote already has
- **WHEN** a new branch is pushed through pre-commit and its tip is already on the remote
- **THEN** pre-commit does not run the hook and the push succeeds

### Requirement: Only branch updates count
The hook SHALL ignore a pushed ref whose remote ref is not under `refs/heads/` (tags and other refs) and a ref whose pushed sha is all zeros (a deletion). It SHALL NOT read the config for them and SHALL exit 0 when nothing else is pushed.

#### Scenario: Tag push
- **WHEN** a tag that points to a commit with the trailer is pushed with `git push origin v1`
- **THEN** the push succeeds and the check does not run

#### Scenario: Branch deletion
- **WHEN** `git push origin --delete old` deletes a branch
- **THEN** the push succeeds and the check does not run

#### Scenario: Tag push in a repository without a config
- **WHEN** a repository has no config and a tag is pushed
- **THEN** the push succeeds

#### Scenario: Pushed to a non-branch ref
- **WHEN** a commit with the trailer is pushed with `git push origin HEAD:refs/notes/x`
- **THEN** the push succeeds and the check does not run

#### Scenario: Branch pushed under another local name
- **WHEN** a commit with the trailer is pushed with `git push origin HEAD:refs/heads/x`
- **THEN** the hook runs the check on that commit

### Requirement: A tip demands the check when it carries the trailer
A pushed branch tip SHALL demand the check when its own message has a trailer whose key equals `trailer.key` or one of `legacy_keys`, compared case-insensitively, whatever the value. The trailers SHALL be read as `git log` reads them (`git log -1 --format=%(trailers:only,unfold)` on the tip), so a `---` line in the message does not hide them. Only the tip counts: trailers on earlier commits of the push SHALL NOT demand the check.

#### Scenario: Tip with the trailer
- **WHEN** a branch whose tip carries `Prepush-CI: full` is pushed
- **THEN** the hook runs the check

#### Scenario: Tip without the trailer
- **WHEN** a branch whose tip has no trailer is pushed
- **THEN** the push succeeds and the check does not run

#### Scenario: Earlier commit with the trailer
- **WHEN** a push has two new commits and only the first carries `Prepush-CI: full`
- **THEN** the push succeeds and the check does not run

#### Scenario: Key in another case
- **WHEN** the tip carries `prepush-ci: full`
- **THEN** the hook runs the check

#### Scenario: Any value demands the check
- **WHEN** the tip carries `Prepush-CI: off`
- **THEN** the hook runs the check

#### Scenario: Legacy key
- **WHEN** the config sets `legacy_keys = ["Full-Pre-Push"]` and the tip carries `Full-Pre-Push: required`
- **THEN** the hook runs the check

#### Scenario: Configured key
- **WHEN** the config sets `trailer = { key = "Full-Check", value = "yes" }` and the tip carries `Full-Check: yes`
- **THEN** the hook runs the check

#### Scenario: Trailer behind a divider line
- **WHEN** the tip's message has a `---` line in its body and `Prepush-CI: full` in its last paragraph
- **THEN** the hook runs the check

#### Scenario: Trailer text in the body
- **WHEN** the tip's message has `Prepush-CI: full` in its body but not in its last paragraph
- **THEN** the push succeeds and the check does not run

### Requirement: Which config decides the demand
The keys that demand the check (`trailer.key` and `legacy_keys`) SHALL be read from the config committed in the pushed tip, which is what CI reads, and from the worktree config; a tip demands the check when either set of keys matches. A tip without a config contributes no keys; an invalid config in the tip SHALL refuse the push as the `config` capability specifies.

#### Scenario: Key set only by the tip's config
- **WHEN** the pushed branch `feature` has a tip whose committed config sets `trailer = { key = "Full-Check", value = "yes" }` and whose message carries `Full-Check: yes`, while the checked-out worktree has the default key, and `git push origin feature` runs
- **THEN** the tip demands the check, and the push is refused because the tip is not `HEAD`

#### Scenario: Key set only by the worktree config
- **WHEN** the tip is `HEAD` with a clean worktree, the worktree config sets `legacy_keys = ["Full-Pre-Push"]` and the tip, whose committed config has none, carries `Full-Pre-Push: required`
- **THEN** the hook runs the check

#### Scenario: Tip without a config
- **WHEN** the tip is `HEAD`, has no config in its commit, the worktree is clean with a valid config and the tip carries `Prepush-CI: full`
- **THEN** the hook runs the check

#### Scenario: Invalid config in the tip
- **WHEN** the tip's committed config contains an unknown key and `git push` pushes that tip
- **THEN** the push is aborted and the error names the unknown key

### Requirement: A demanding tip runs the check
When a pushed tip demands the check, the hook SHALL run the `check` of the worktree config (the tip's own) through the shell from the repository root, whatever `PREPUSH_CI` is (unset, empty or `full`), show its output, and exit non-zero when the check exits non-zero so that git aborts the push. It SHALL run the check only after the requirements of the `preflight` capability pass. When several pushed refs have the same demanding tip, the check SHALL run once.

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

### Requirement: The pushed tip must be the checked-out HEAD
Before the check runs, the hook SHALL require every demanding tip to be the commit `HEAD` points to, and SHALL otherwise refuse the push without running the check, with a reason that names the tip and `HEAD`.

#### Scenario: Pushing another branch
- **WHEN** `main` has the checked-out commit and `git push origin other` pushes `other`, whose tip carries the trailer
- **THEN** the push is refused, the check does not run and the reason names `HEAD`

#### Scenario: Pushing an older commit
- **WHEN** `HEAD` is a commit with the trailer and `git push origin HEAD~1:refs/heads/x` pushes the commit before it, which also carries the trailer
- **THEN** the push is refused and the check does not run

#### Scenario: Two different demanding tips
- **WHEN** `git push origin a b` pushes two branches whose tips carry the trailer and differ
- **THEN** the push is refused and the check does not run

#### Scenario: Detached HEAD
- **WHEN** `HEAD` is detached at a commit with the trailer and `git push origin HEAD:refs/heads/x` pushes it
- **THEN** the check runs

### Requirement: The worktree must be clean
Before the check runs, the hook SHALL require a clean worktree: no staged or unstaged changes to tracked files and no untracked files that are not ignored. Otherwise it SHALL refuse the push without running the check, with a reason that lists the dirty paths.

#### Scenario: Unstaged change
- **WHEN** a tracked file is modified and a tip with the trailer is pushed
- **THEN** the push is refused, the check does not run and the reason names the file

#### Scenario: Staged change
- **WHEN** a change is staged and a tip with the trailer is pushed
- **THEN** the push is refused and the check does not run

#### Scenario: Untracked file
- **WHEN** an untracked, not ignored file exists and a tip with the trailer is pushed
- **THEN** the push is refused and the reason names the file

#### Scenario: Ignored file
- **WHEN** an ignored file exists and a tip with the trailer is pushed
- **THEN** the check runs

#### Scenario: Dirty worktree and a tip without the trailer
- **WHEN** a tracked file is modified and a tip without the trailer is pushed
- **THEN** the push succeeds

### Requirement: Off refuses a demanding tip
With `PREPUSH_CI=off`, the hook SHALL refuse the push of a demanding tip without running the check, with a reason that says the tip demands a check and `PREPUSH_CI` is `off`. No value of `PREPUSH_CI` SHALL let a demanding tip through unchecked.

#### Scenario: Off with a trailer commit
- **WHEN** a tip with the trailer is pushed with `PREPUSH_CI=off`
- **THEN** the push is refused, the check does not run and the reason names `PREPUSH_CI=off`

#### Scenario: Off with a tip without the trailer
- **WHEN** a tip without the trailer is pushed with `PREPUSH_CI=off`
- **THEN** the push succeeds without a hint

### Requirement: Unknown variable values are refused
With `PREPUSH_CI` set to a value other than `full`, `off` or the empty string (compared exactly, case-sensitive), the hook SHALL print an error naming `full` and `off` and exit non-zero before it reads any ref, so git aborts the push.

#### Scenario: Misspelled value
- **WHEN** any branch is pushed with `PREPUSH_CI=ful`
- **THEN** the push is aborted, the check does not run and the error names `full` and `off`

### Requirement: Hint for a tip without the trailer
With `PREPUSH_CI=full`, when no pushed branch tip demands the check, the hook SHALL print once, to standard error, that CI will run for this push and that `git commit --amend --no-edit` adds the trailer, and SHALL let the push go. It SHALL print no hint when `PREPUSH_CI` is unset, empty or `off`, or when only tags and deletions are pushed.

#### Scenario: Full mode and a tip without the trailer
- **WHEN** a tip without the trailer is pushed with `PREPUSH_CI=full`
- **THEN** the push succeeds, the check does not run and the hint names `git commit --amend --no-edit`

#### Scenario: Not opted in
- **WHEN** a tip without the trailer is pushed with `PREPUSH_CI` unset
- **THEN** the push succeeds without a hint

#### Scenario: Full mode and a tag push
- **WHEN** a tag is pushed with `PREPUSH_CI=full`
- **THEN** the push succeeds without a hint

### Requirement: A branch push needs a valid config
When a branch tip is examined, the hook SHALL load the config, and SHALL refuse the push as the `config` capability specifies when it is missing or invalid, whatever `PREPUSH_CI` says, because without it the hook cannot tell whether the tip demands the check.

#### Scenario: Branch push without a config
- **WHEN** a repository has no config and a branch is pushed
- **THEN** the push is aborted and the error names `.prepush-ci.toml`

#### Scenario: Branch push with an invalid config
- **WHEN** the config contains an unknown key and a branch is pushed
- **THEN** the push is aborted and the error names the unknown key

### Requirement: The hook fails closed
When the hook cannot decide whether a pushed branch tip may go, it SHALL exit non-zero with a message that names what it could not do, and SHALL NOT let the push through. This covers a pushed sha that is not a commit of the repository, a tip message that cannot be read, a repository without a worktree and a worktree status that git cannot report. A hook that stops on an unexpected error SHALL exit non-zero.

#### Scenario: Pushed sha is unknown
- **WHEN** the hook receives a ref line whose local sha is no object of the repository
- **THEN** the push is aborted and the error names that sha

#### Scenario: Push from a bare repository
- **WHEN** the hook runs in a bare repository with a branch tip that carries the trailer
- **THEN** the push is refused and the error says the repository has no worktree

#### Scenario: Unborn HEAD
- **WHEN** `HEAD` points to a branch with no commits and a pushed branch tip carries the trailer
- **THEN** the push is refused and the check does not run

#### Scenario: Status cannot be read
- **WHEN** git fails to report the worktree status for a pushed tip with the trailer
- **THEN** the push is aborted, the check does not run and the error says the status could not be read
