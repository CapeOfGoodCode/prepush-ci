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

### Requirement: A pass is published to origin by a push to origin
When the pre-push hook records a pass, or skips the check for a result that exists locally, for a push to `origin` (see the requirement on how the hook learns the remote), it SHALL push the result ref to `origin` under the same name, without running the repository's hooks. The hook SHALL NOT publish a result for a push to any other remote, and `prepush-ci run` SHALL NOT publish at all. A result ref SHALL leave the machine only in a push to `origin`.

#### Scenario: Hook pass publishes
- **WHEN** a tip with the trailer is pushed to `origin` and passes the check in the hook
- **THEN** `origin` holds the ref `refs/prepush-ci/results/<tree>-<config>` of the tree of the tip, and the check ran exactly once

#### Scenario: Publishing does not start the hook again
- **WHEN** a tip with the trailer is pushed to `origin` in a clone whose `pre-push` hook appends a line to a file and then runs the prepush-ci hook, and the check passes
- **THEN** the file holds one line and the ref is on `origin`

#### Scenario: A reused local result is published
- **WHEN** the check passed in a push to `origin` that declined the ref, `origin` then accepts it, and the same tip is pushed to `origin` as another branch
- **THEN** the hook skips the check and `origin` holds the ref

#### Scenario: Another remote is pushed to
- **WHEN** the check passes in the hook run with the arguments `other` and its url, where `other` is a remote that is not `origin`
- **THEN** the push succeeds, and neither `origin` nor the other remote holds a ref under `refs/prepush-ci/`

#### Scenario: Run publishes nothing
- **WHEN** `prepush-ci run` passes in a clone whose `origin` accepts every ref
- **THEN** `origin` holds no ref under `refs/prepush-ci/`

#### Scenario: Failed check publishes nothing
- **WHEN** a tip with the trailer is pushed to `origin`, which accepts every ref, and the check exits 1
- **THEN** the push is refused, `origin` holds no ref under `refs/prepush-ci/` and no warning names `origin`

### Requirement: A dry run or a declined push to origin still publishes
When the requirement `A pass is published to origin by a push to origin` calls for a publish, the hook SHALL publish even if the push is a `--dry-run` or `origin` then declines the branch: git tells a `pre-push` hook neither. Such a push SHALL therefore leave the result ref, and with it the files of the tree, on `origin`.

#### Scenario: Dry run publishes
- **WHEN** a tip with the trailer is pushed with `git push --dry-run origin main` and the check passes
- **THEN** `origin` holds the ref `refs/prepush-ci/results/<tree>-<config>` and its branch `main` has not moved

#### Scenario: Declined push publishes
- **WHEN** a tip with the trailer is pushed to `origin`, whose `pre-receive` hook declines `refs/heads/main`, and the check passes
- **THEN** the push fails, `origin` holds the ref `refs/prepush-ci/results/<tree>-<config>` and its branch `main` has not moved

### Requirement: Only origin and only with the cache
The hook SHALL use the remote `origin` for results whichever remote a push goes to. A repository without a remote named `origin` SHALL share nothing and SHALL print nothing about it. With `cache = false` the tool SHALL NOT contact the remote for results.

#### Scenario: Cache off
- **WHEN** the config sets `cache = false` and a tip with the trailer that passes the check is pushed to `origin`
- **THEN** `origin` holds no ref under `refs/prepush-ci/`

#### Scenario: No origin
- **WHEN** the repository has no remote named `origin` and a tip with the trailer that passes the check is pushed to another remote
- **THEN** the push succeeds and no warning is printed

### Requirement: A result on the remote is reused
When the pre-push hook has satisfied every requirement that precedes the check, including the preflight, and no result ref matches locally, it SHALL ask `origin` for the result ref of the key and fetch a ref it finds into the same name. That ref SHALL count as a result found locally: the check is not run, the push goes on, and the line the hook prints names the tree and the commit that passed, as for a local result, and says that the result came from `origin`.

#### Scenario: Fresh clone finds the result
- **WHEN** a session passed the check on a tree in a push to `origin`, and a fresh clone of the same remote pushes a commit of that tree with the trailer
- **THEN** the check does not run, the push succeeds and the hook's line contains `origin`, the first twelve characters of the tree and the first twelve characters of the commit that passed

#### Scenario: Found result is kept
- **WHEN** a fresh clone reused a result from `origin`
- **THEN** the clone holds the result ref locally

#### Scenario: Preflight still runs
- **WHEN** `origin` holds the result for the tip, the config sets `preflight = "test -f ready"` and the file `ready` does not exist
- **THEN** the push is refused, the reason names the preflight and the check does not run

#### Scenario: Another key on the remote
- **WHEN** `origin` holds a result for the tree of the tip made with another `check`
- **THEN** the check runs

#### Scenario: A ref of another tree is a miss
- **WHEN** the ref `origin` holds under the name of the key points at a commit of another tree
- **THEN** the check runs

#### Scenario: A local result is not looked up
- **WHEN** a result matches locally and `origin` holds the same ref
- **THEN** the push skips the check and the hook's line does not say that the result came from `origin`

#### Scenario: Remote without the ref
- **WHEN** `origin` holds no result ref and a tip with the trailer is pushed
- **THEN** the check runs and no warning about the remote is printed

#### Scenario: Cache off ignores the remote
- **WHEN** `origin` holds the result for the tip and the config sets `cache = false`
- **THEN** the check runs

### Requirement: Run does not read the remote
`prepush-ci run` SHALL NOT contact `origin` for results and SHALL run the check.

#### Scenario: Run ignores the remote
- **WHEN** `origin` holds the result for `HEAD` and `prepush-ci run` starts in a fresh clone
- **THEN** the check runs

### Requirement: A remote that fails costs time and nothing else
A remote that cannot be reached, or that refuses the result ref, SHALL produce a warning on standard error that names `origin` and says that the result was not shared or could not be looked up. It SHALL NOT change the hook's decision about the push. When the lookup fails, the result SHALL count as a miss and the check SHALL run.

#### Scenario: Remote refuses the ref
- **WHEN** `origin` declines every ref outside `refs/heads/` and a tip with the trailer whose check passes is pushed to `origin`
- **THEN** the push succeeds and a warning names `origin`

#### Scenario: Unreachable remote at lookup
- **WHEN** the url of `origin` names a directory that is no repository and a tip with the trailer is pushed to another remote
- **THEN** the check runs, the push succeeds and a warning names `origin`

### Requirement: The hook reads the remote of the push from its arguments or pre-commit
The hook SHALL take the remote of the push from its first argument when it has one (native hooks and husky pass the remote name there), and otherwise from the environment variable `PRE_COMMIT_REMOTE_NAME` (pre-commit sets it and passes no argument). The remote SHALL count as `origin` only when that value is the name `origin`; a remote given by url, whatever the url, is not `origin`.

#### Scenario: Remote name from the argument
- **WHEN** the hook runs with the arguments `origin` and the url of `origin`, and a tip with the trailer passes the check
- **THEN** `origin` holds the ref `refs/prepush-ci/results/<tree>-<config>`

#### Scenario: Remote name from pre-commit
- **WHEN** the hook runs with no arguments and `PRE_COMMIT_REMOTE_NAME=origin`, and a tip with the trailer passes the check
- **THEN** `origin` holds the ref

#### Scenario: Argument wins over the environment
- **WHEN** the hook runs with the arguments `upstream` and its url, `PRE_COMMIT_REMOTE_NAME=origin` is set, and the check passes
- **THEN** `origin` holds no ref under `refs/prepush-ci/`

#### Scenario: Push by url is not a push to origin
- **WHEN** the hook runs with the url of `origin` as both arguments, as git passes them for `git push <url>`, and the check passes
- **THEN** the push succeeds and `origin` holds no ref under `refs/prepush-ci/`

### Requirement: A hook that does not know the remote publishes nothing
A hook that cannot tell the remote of the push, as with lefthook, which passes no argument, SHALL NOT publish and SHALL print nothing about it. An unknown remote SHALL NOT default to `origin`. The lookup does not depend on the remote of the push and SHALL work as for any other push.

#### Scenario: Unknown remote publishes nothing
- **WHEN** the hook runs with no arguments and without `PRE_COMMIT_REMOTE_NAME`, and a tip with the trailer passes the check
- **THEN** the push succeeds, `origin` holds no ref under `refs/prepush-ci/` and no warning names `origin`

#### Scenario: Unknown remote still looks up
- **WHEN** the hook runs with no arguments and without `PRE_COMMIT_REMOTE_NAME`, and `origin` holds the result for the tip
- **THEN** the check does not run

### Requirement: A result older than 30 days is deleted
A result ref under `refs/prepush-ci/results/` SHALL count as expired when its commit is older than 30 days, measured by the commit's committer date. A cleanup SHALL delete an expired ref and SHALL keep a ref that is 30 days old or younger, a ref dated in the future and a ref that cannot be read. A repository without a remote named `origin` SHALL run the cleanup on its own clone, in `prepush-ci run` and in the hook alike.

#### Scenario: Expired ref is deleted
- **WHEN** the repository has no remote, a result ref points at a commit made 31 days ago, and `prepush-ci run` passes
- **THEN** that ref is gone and the ref of the new pass exists

#### Scenario: Recent ref stays
- **WHEN** the repository has no remote, a result ref points at a commit made 29 days ago, and `prepush-ci run` passes
- **THEN** both that ref and the ref of the new pass exist

#### Scenario: Future date stays
- **WHEN** the repository has no remote, a result ref points at a commit dated a day from now, and `prepush-ci run` passes
- **THEN** that ref still exists

#### Scenario: Unreadable ref stays
- **WHEN** the repository has no remote, the file of an expired result ref is emptied, and `prepush-ci run` passes
- **THEN** it exits 0, the emptied file still exists and the ref of the new pass exists

#### Scenario: Thousands of refs
- **WHEN** the repository has no remote, 2000 result refs point at a commit made 31 days ago, and `prepush-ci run` passes
- **THEN** it exits 0 and only the ref of the new pass is left under `refs/prepush-ci/results/`

### Requirement: A recorded pass is dated when it is recorded
The commit behind a result ref SHALL be dated, as author and committer, at the time the pass is recorded, whatever `GIT_COMMITTER_DATE` and `GIT_AUTHOR_DATE` say in the environment. The cleanup SHALL therefore never expire the ref of the pass it follows.

#### Scenario: A date in the environment does not date the pass
- **WHEN** `GIT_COMMITTER_DATE` and `GIT_AUTHOR_DATE` are both set to 31 days ago and `prepush-ci run` passes in a repository without a remote
- **THEN** the ref of the new pass exists and its commit's author date and committer date are both within a minute of the time of the run

#### Scenario: A pass under old dates survives the cleanup in a push
- **WHEN** `GIT_COMMITTER_DATE` and `GIT_AUTHOR_DATE` are both set to 31 days ago and a tip with the trailer is pushed to `origin` and passes the check in the hook
- **THEN** both `origin` and the clone hold the ref of the new pass, and its commit's author date and committer date are both within a minute of the time of the push

### Requirement: Only a recorded pass cleans up
The cleanup SHALL run when the tool has recorded a pass, in `prepush-ci run` and in the pre-push hook. It SHALL NOT run when the check fails, when a refusal stops the run, when the hook skips the check for a result, or when `cache` is `false`.

#### Scenario: Hook pass cleans up
- **WHEN** the repository has no remote named `origin`, a result ref points at a commit made 31 days ago, and a tip with the trailer is pushed to another remote and passes the check in the hook
- **THEN** the old ref is gone and the ref of the new pass exists

#### Scenario: Reused result cleans nothing
- **WHEN** the repository has no remote, a pass is cached for the tip, a result ref of another tree points at a commit made 31 days ago, and the tip with the trailer is pushed
- **THEN** the hook skips the check and the old ref still exists

#### Scenario: Failed check cleans nothing
- **WHEN** the repository has no remote, a result ref points at a commit made 31 days ago, and `prepush-ci run` fails because the check exits 1
- **THEN** that ref still exists

#### Scenario: Refusal cleans nothing
- **WHEN** the repository has no remote, a result ref points at a commit made 31 days ago, and `prepush-ci run` is refused because the worktree is dirty
- **THEN** that ref still exists

#### Scenario: Cache off cleans nothing
- **WHEN** the repository has no remote, the config sets `cache = false`, a result ref points at a commit made 31 days ago, and `prepush-ci run` passes
- **THEN** that ref still exists

### Requirement: A push to origin cleans origin too
When the pre-push hook records a pass for a push to `origin` (see the requirement on how the hook learns the remote), the cleanup SHALL delete each expired ref that the clone holds from `origin` under the same name, without running the repository's hooks and in batches of at most a hundred refs, and then from the clone: only the refs that `origin` dropped or never held. It SHALL NOT delete from `origin` a result ref that the clone does not hold.

#### Scenario: Expired ref leaves both sides
- **WHEN** a result ref made 31 days ago is held by the clone and by `origin`, and a tip with the trailer is pushed to `origin` and passes the check in the hook
- **THEN** the old ref is gone from `origin` and from the clone, and both hold the ref of the new pass

#### Scenario: Recent ref stays on both sides
- **WHEN** a result ref made 29 days ago is held by the clone and by `origin`, and a tip with the trailer is pushed to `origin` and passes the check in the hook
- **THEN** both still hold it

#### Scenario: A ref only origin holds stays
- **WHEN** `origin` holds a result ref made 31 days ago that the clone does not hold, and a tip with the trailer is pushed to `origin` and passes the check in the hook
- **THEN** `origin` still holds it

#### Scenario: A ref origin never held is dropped locally
- **WHEN** the clone holds a result ref made 31 days ago that `origin` does not hold, and a tip with the trailer is pushed to `origin` and passes the check in the hook
- **THEN** the clone no longer holds it and no warning names `origin`

#### Scenario: Cleaning does not start the hook again
- **WHEN** a result ref made 31 days ago is held by the clone and by `origin`, a tip with the trailer is pushed to `origin` in a clone whose `pre-push` hook appends a line to a file and then runs the prepush-ci hook, and the check passes
- **THEN** the file holds one line and the old ref is gone from `origin`

#### Scenario: More refs than a batch
- **WHEN** 250 result refs made 31 days ago are held by the clone and by `origin`, and a tip with the trailer is pushed to `origin` and passes the check in the hook
- **THEN** only the ref of the new pass is left under `refs/prepush-ci/results/` in the clone and on `origin`

### Requirement: A dry run or a declined push to origin still cleans
A push to `origin` that records a pass SHALL clean even if it is a `--dry-run` or `origin` then declines the branch: git tells a `pre-push` hook neither, as for the publish (see the requirement `A dry run or a declined push to origin still publishes`). Such a push SHALL therefore delete the expired refs from `origin` and from the clone.

#### Scenario: Dry run cleans up
- **WHEN** a result ref made 31 days ago is held by the clone and by `origin`, and a tip with the trailer is pushed with `git push --dry-run origin main` and passes the check in the hook
- **THEN** the old ref is gone from `origin` and from the clone, and `main` on `origin` has not moved

#### Scenario: Declined push cleans up
- **WHEN** a result ref made 31 days ago is held by the clone and by `origin`, whose `pre-receive` hook declines `refs/heads/main` and nothing else, and a tip with the trailer is pushed to `origin` and passes the check in the hook
- **THEN** the push fails, the old ref is gone from `origin` and from the clone, and `main` on `origin` has not moved

### Requirement: A repository with origin cleans only in a push to origin
A repository that has a remote named `origin` SHALL delete no expired result ref, from `origin` or from the clone, in `prepush-ci run`, in a push to any other remote, in a push by url, or when the hook cannot tell the remote. An expired ref that is left stays for the next push to `origin` that records a pass.

#### Scenario: Run cleans nothing
- **WHEN** the repository has an `origin`, a result ref made 31 days ago is held by the clone and by `origin`, and `prepush-ci run` passes
- **THEN** both still hold the old ref

#### Scenario: Another remote cleans nothing
- **WHEN** a result ref made 31 days ago is held by the clone and by `origin`, the hook runs with the arguments `other` and its url, where `other` is a remote that is not `origin`, and the check passes
- **THEN** both still hold the old ref

#### Scenario: Push by url cleans nothing
- **WHEN** a result ref made 31 days ago is held by the clone and by `origin`, the hook runs with the url of `origin` as both arguments, and the check passes
- **THEN** both still hold the old ref

#### Scenario: Unknown remote cleans nothing
- **WHEN** a result ref made 31 days ago is held by the clone and by `origin`, the hook runs with no arguments and without `PRE_COMMIT_REMOTE_NAME`, and the check passes
- **THEN** both still hold the old ref

### Requirement: A cleanup that fails costs a warning and nothing else
A deletion that fails SHALL produce a warning on standard error and SHALL NOT change the exit code of `run` or the hook's decision about the push. A deletion from `origin` that `origin` refuses, or that cannot reach it, SHALL produce a warning that names `origin` and says that old results could not be removed from it, and SHALL leave the refs of that batch in the clone so that the next push to `origin` that records a pass tries again.

#### Scenario: Origin declines the delete
- **WHEN** a result ref made 31 days ago is held by the clone and by `origin`, whose `pre-receive` hook declines every deletion of a ref, and a tip with the trailer is pushed to `origin` and passes the check in the hook
- **THEN** the push succeeds, a warning names `origin` and says that old results could not be removed, and the clone and `origin` still hold the old ref

#### Scenario: Origin cannot be reached
- **WHEN** a result ref made 31 days ago is held by the clone, the url of `origin` names a directory that is no repository, the hook runs with the arguments `origin` and that url, and the check passes
- **THEN** the hook exits 0, a warning names `origin` and says that old results could not be removed, and the clone still holds the old ref

#### Scenario: The clone cannot delete
- **WHEN** the repository has no remote, a result ref made 31 days ago has a lock file next to it (`<ref>.lock`), and `prepush-ci run` passes
- **THEN** it exits 0, a warning on standard error says that old results could not be removed, and the old ref still exists

#### Scenario: The next push tries again
- **WHEN** `origin` declined the deletion of an expired result ref, then accepts it, and another tip with the trailer is pushed to `origin` and passes the check in the hook
- **THEN** the old ref is gone from `origin` and from the clone
