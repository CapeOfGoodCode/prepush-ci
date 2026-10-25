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

### Requirement: A damaged ref in the clone does not hide a result on the remote
The lookup of a result on `origin` SHALL NOT turn into a miss because a ref in the clone is damaged: a result ref whose file is empty or a ref under `refs/prepush-ci` whose name git refuses. When `origin` holds the result of the key, the lookup SHALL fetch it and the result SHALL be reused as for a clone with healthy refs.

#### Scenario: Another result ref emptied
- **WHEN** a session passed the check on a tree in a push to `origin`, a fresh clone holds an emptied file under `.git/refs/prepush-ci/results/` of another name, and it pushes a commit of that tree with the trailer
- **THEN** the check does not run, the push succeeds and the hook's line contains `origin`, the first twelve characters of the tree and the first twelve characters of the commit that passed

#### Scenario: A ref with a refused name
- **WHEN** a fresh clone holds the ref `refs/prepush-ci/results/bad..name`, `origin` holds the result for the tip, and the tip with the trailer is pushed
- **THEN** the check does not run and the push succeeds

### Requirement: The lookup past a damaged ref SHALL NOT start housekeeping
The fetch of the lookup SHALL NOT run auto-maintenance (`gc --auto`), so that no pruning of history happens while git is told to ignore damaged refs.

#### Scenario: A broken ref holds the only copy of a commit
- **WHEN** a ref under `refs/prepush-ci/results/` with a name git refuses (`bad..name`) holds a commit no other ref holds, git's auto-gc is set to run on every fetch and prune at once, `origin` holds the result for the tip, and the tip with the trailer is pushed
- **THEN** the check does not run, the push succeeds and the commit still exists

### Requirement: A lookup that cannot write the result ref is a miss
A lookup whose fetch cannot write the ref of the key, because the clone's ref of that very name is damaged, or because `refs/prepush-ci` is a regular file, SHALL be a miss and the check SHALL run. The push SHALL NOT be refused for it.

#### Scenario: The damaged ref has the name of the key
- **WHEN** the file of the ref `refs/prepush-ci/results/<tree>-<config>` in a fresh clone is empty, `origin` holds the result for the tip, and the tip with the trailer is pushed
- **THEN** the check runs and the push succeeds

#### Scenario: Cache path is a file
- **WHEN** `refs/prepush-ci` in a fresh clone's git directory is a regular file, `origin` holds the result for the tip, and the tip with the trailer is pushed
- **THEN** the check runs and the push succeeds

### Requirement: The warning that a result was not shared is one line
When the push of the result ref to `origin` fails, the warning SHALL be one line on standard error, `prepush-ci: the result was not shared through origin (<cause>), so another clone runs the check again; the push goes on`, with nothing of git's output in it.

#### Scenario: A rejected ref
- **WHEN** `origin` declines every ref outside `refs/heads/` with a hook and a tip with the trailer whose check passes is pushed to `origin`
- **THEN** the push succeeds and standard error holds the line `prepush-ci: the result was not shared through origin (origin rejected the ref), so another clone runs the check again; the push goes on`

#### Scenario: Git's lines stay out
- **WHEN** the push of the result ref fails with several lines of output
- **THEN** the warning is one line and holds no `fatal:`, `error:` or `remote:` text from git

### Requirement: The warning names the cause in a few words
The cause SHALL be `origin refused the ref, HTTP <status>` when a line of git's output that does not start with `remote:` holds `HTTP <status>` or `error: <status>` with a status from 400 to 599, else `origin rejected the ref` when it holds a `[remote rejected]` line, else `git could not push it`.

#### Scenario: A status from the transport
- **WHEN** git's output for the failed push is `fatal: unable to access 'http://h/x.git/': The requested URL returned error: 403`, or `error: RPC failed; HTTP 403 curl 22 The requested URL returned error: 403` followed by `fatal: expected 'acknowledgments', received 'packfile'`
- **THEN** the cause is `origin refused the ref, HTTP 403`

#### Scenario: A failure without a status
- **WHEN** git's output is `fatal: '/x.git' does not appear to be a git repository`
- **THEN** the cause is `git could not push it`

#### Scenario: A status in the remote's own text
- **WHEN** git's output is `remote: error: 500 files are over the limit` followed by ` ! [remote rejected] main -> refs/prepush-ci/results/t-k (pre-receive hook declined)`
- **THEN** the cause is `origin rejected the ref`, because a line from the remote is its author's text and not a transport status

#### Scenario: A number that is not a status
- **WHEN** git's output holds `error: 200` or `HTTP 302`
- **THEN** the cause is `git could not push it`

### Requirement: Git's output of that push can be asked for
With `PREPUSH_CI_DEBUG` set to a non-empty value, the lines git printed for the failed push of the result ref SHALL follow the warning on standard error, unchanged. With it unset or empty, nothing of them SHALL be printed.

#### Scenario: Debug on
- **WHEN** `PREPUSH_CI_DEBUG=1` and `origin` declines the result ref
- **THEN** the warning line is followed by git's lines, including the `[remote rejected]` line

#### Scenario: Debug off or empty
- **WHEN** `PREPUSH_CI_DEBUG` is unset, or set to the empty string, and `origin` declines the result ref
- **THEN** standard error holds the warning line and no line of git's output

### Requirement: A recorded pass holds the facts of its run
When the tool records a pass (in `prepush-ci run` or in the pre-push hook), the message of the result commit SHALL hold, after the paragraph that names the checked commit, the paragraph `facts <JSON on one line>`: the duration of the check command alone in whole seconds, and what the files named in `results` say (see "The files named in results become facts"). A ref without that paragraph, or with one that cannot be read, SHALL stay a valid pass without facts.

#### Scenario: The duration is recorded
- **WHEN** the check takes at least two seconds and passes in `prepush-ci run`
- **THEN** the facts of the result ref hold a duration of two seconds or more

#### Scenario: The hook records them as well
- **WHEN** a push of a tip with the trailer passes the check in the pre-push hook
- **THEN** the facts of the result ref hold a duration

#### Scenario: A pass without facts
- **WHEN** the result ref points at a commit whose message names the checked commit and holds no facts paragraph
- **THEN** pushing that tree skips the check, as for any cached pass

#### Scenario: Facts that cannot be read
- **WHEN** the result ref's message holds `facts not json`
- **THEN** pushing that tree skips the check, and the post-push hook shows no facts

#### Scenario: A pass from origin brings its facts
- **WHEN** a clone fetches the result ref of a pass from `origin` and the post-push hook runs there
- **THEN** it reads the facts of that pass

### Requirement: The files named in results become facts
For each file named in `results` that the check wrote and the tool could read, the facts SHALL hold: for `junit` the numbers of passed, failed and skipped cases (counted as `report` counts them, all files added) and the same three numbers per test file; for `coverage` the percentage; for `ruff` the number of entries of its array; for `mypy` the number in its `Found <n> error` line, or 0 for `Success`.

#### Scenario: Test counts per file
- **WHEN** `results` names a JUnit file and the check writes it with three passed cases and one skipped case, all with `file="tests/a_spec.py"`, a file of the tree
- **THEN** the facts hold 3 passed, 0 failed and 1 skipped, and the same numbers for `tests/a_spec.py`

#### Scenario: Several JUnit files
- **WHEN** `results` names two JUnit files and the check writes them with 2 and 3 passing cases
- **THEN** the facts hold 5 passed

#### Scenario: Coverage and the tools
- **WHEN** `results` names a coverage file of 94.5%, a ruff file with an empty array and a mypy file with `Success: no issues found in 12 source files`, and the check writes them
- **THEN** the facts hold coverage `94.5` (the text of the file), 0 ruff errors and 0 mypy errors

#### Scenario: Errors counted
- **WHEN** the check passes and writes a ruff file with two errors and a mypy file with `Found 3 errors in 1 file`
- **THEN** the facts hold 2 ruff errors and 3 mypy errors

#### Scenario: Nothing named
- **WHEN** the config has no `results`
- **THEN** the facts hold the duration and nothing else

### Requirement: The files of this run only
When the cache is on, before it starts the check the tool SHALL delete each file named in `results` that exists and that it may delete (see "A path that is not safe to delete is left alone"), so that a file left by an earlier run is never read as a fact of this one. A cached pass that skips the check, and a repository with `cache = false`, SHALL delete nothing.

#### Scenario: A stale file is not read
- **WHEN** `results` names `out/a.xml`, an untracked `out/a.xml` with 4 failing cases exists, and the check passes without writing it
- **THEN** the facts hold no test counts

#### Scenario: The file the check writes is read
- **WHEN** an untracked `out/a.xml` from an earlier run exists and the check writes it again with 3 passing cases
- **THEN** the facts hold 3 passed

#### Scenario: A skipped check deletes nothing
- **WHEN** a pass is cached and the push skips the check while an untracked `out/a.xml` exists
- **THEN** `out/a.xml` is still there

#### Scenario: No cache, no deletion
- **WHEN** `cache = false`, `results` names `out/a.xml`, an untracked `out/a.xml` exists and the check passes
- **THEN** `out/a.xml` is still there

#### Scenario: A failing check
- **WHEN** an untracked `out/a.xml` exists and the check fails
- **THEN** no result ref is recorded

### Requirement: A path that is not safe to delete is left alone
A path named in `results` SHALL be deleted only when it is a regular file, not a link, that is neither in `HEAD` nor in the index, with no symbolic link or junction on its way, and whose real path lies under the real path of the worktree. Anything else that exists, and a deletion that fails, SHALL be left alone and not read after the check, and the run SHALL go on.

#### Scenario: A tracked file is left alone
- **WHEN** `results` names `docs/cov.json`, which is tracked, and the check passes
- **THEN** the file is unchanged, the facts hold no coverage and standard error has one line naming `results.coverage` that says the file is tracked

#### Scenario: A file that is only staged is left alone
- **WHEN** `results` names `out/a.xml`, which is added to the index and not committed, and the check passes
- **THEN** the file is unchanged and standard error has one line naming `results.junit` that says the file is tracked

#### Scenario: A directory
- **WHEN** `results = { coverage = "out" }` and `out` is a directory
- **THEN** `out` and what it holds are still there, standard error has one line naming `results.coverage` that says it is a directory, the exit status is 0 and the facts hold no coverage

#### Scenario: A symbolic link on the way
- **WHEN** `out` is a symbolic link to a directory outside the worktree that holds `a.xml`, `results = { junit = ["out/a.xml"] }` and the check passes
- **THEN** the `a.xml` outside the worktree is still there, standard error has one line naming `results.junit` that says a link is on the way, and the facts hold no test counts

#### Scenario: A junction on the way
- **WHEN** on Windows `out` is a directory junction to a directory outside the worktree that holds `a.xml`, and `results = { junit = ["out/a.xml"] }`
- **THEN** the `a.xml` outside the worktree is still there and standard error has one line naming `results.junit` that says a link is on the way

#### Scenario: A symbolic link as the file
- **WHEN** `results.coverage` names `cov.json`, a symbolic link to a file, and the check passes
- **THEN** the link and its target are still there, standard error has one line naming `results.coverage` that says it is a link, and the facts hold no coverage

### Requirement: A path in another repository or under a tracked name is left alone
A path SHALL also be left alone when a directory on its way holds a `.git`, or is a gitlink of `HEAD` or the index (a submodule or a nested repository), or when it names a path of `HEAD` or the index once each component is compared without case and without trailing dots and spaces. This SHALL hold on every operating system.

#### Scenario: A file of a submodule
- **WHEN** `sub` is a submodule, `results = { coverage = "sub/README.md" }` and `sub/README.md` exists, untracked by the superproject
- **THEN** the file is unchanged and standard error has one line naming `results.coverage` that says it is in another repository

#### Scenario: A nested repository
- **WHEN** `vendor/lib` holds a `.git` and is not a submodule, and `results = { junit = ["vendor/lib/a.xml"] }` names an existing file there
- **THEN** the file is unchanged and standard error has one line naming `results.junit` that says it is in another repository

#### Scenario: A tracked file under another case
- **WHEN** `docs/cov.json` is tracked, an untracked `Docs/Cov.json` exists and `results = { coverage = "Docs/Cov.json" }`
- **THEN** `Docs/Cov.json` is unchanged and standard error has one line naming `results.coverage` that says the file is tracked

#### Scenario: A tracked file under a trailing dot
- **WHEN** `docs/cov.json` is tracked, an untracked `docs/cov.json.` exists and `results = { coverage = "docs/cov.json." }`
- **THEN** `docs/cov.json.` is unchanged and standard error has one line naming `results.coverage` that says the file is tracked

### Requirement: A path that is left alone costs one line
For each path that "A path that is not safe to delete is left alone" leaves alone, the tool SHALL print one line on standard error that names its `results` key and the entry and says why in a few words (a directory, a link, tracked, in another repository, the deletion failed), never the content of any file.

#### Scenario: A deletion that fails
- **WHEN** an untracked `out/a.xml` exists that the operating system refuses to delete (a read-only directory on POSIX, an open file on Windows), and the check passes without writing it
- **THEN** standard error has one line naming `results.junit` that says the deletion failed, the exit status is 0, the pass is recorded with its duration and the facts hold no test counts

#### Scenario: The line holds no content
- **WHEN** a named untracked directory `out` holds a file with the text `TOKEN=abc123`, and `results = { coverage = "out" }`
- **THEN** standard error has one line naming `results.coverage` and it does not hold `abc123`

### Requirement: A fact that cannot be read costs a warning
A file named in `results` that the check did not write, or that is not of the format of its key (`report`'s readers decide), SHALL yield no fact for it and SHALL cost one line on standard error that names the key and says why in a few words, never the content of the file. The run SHALL still pass and the pass SHALL still be recorded, with the other facts.

#### Scenario: A file that was not written
- **WHEN** `results` names `out/a.xml`, the check passes and does not write it
- **THEN** standard error has one line naming `results.junit`, the exit status is 0 and the pass is recorded with its duration

#### Scenario: A file of the wrong format
- **WHEN** `results.coverage` names a file the check wrote as plain text
- **THEN** standard error has one line naming `results.coverage` that holds none of the text, the exit status is 0 and the facts hold no coverage

#### Scenario: A failing case in a passing check
- **WHEN** the check passes and the JUnit file it wrote holds one failing case
- **THEN** the pass is recorded and the facts hold 1 failed

### Requirement: Test-file names are paths of the tree
The facts SHALL name a test file only when the `file` of a case, taken from the top of the worktree as `report` takes paths, is a path of a file in the tree of the checked commit; the cases of any other `file`, and the cases without one, SHALL be counted under the name `other`. At most 50 test files SHALL be kept, the ones with the most cases first, and the cases of the rest SHALL be added to `other`.

#### Scenario: A file name that is not in the tree
- **WHEN** a JUnit case has `file="/home/someone/secret.py"`
- **THEN** the facts do not hold that text and the case is counted under `other`

#### Scenario: A case without a file
- **WHEN** the JUnit file comes from pytest without `junit_family=xunit1`, which writes no `file`
- **THEN** the facts hold the totals and `other` holds all cases

#### Scenario: More than 50 files
- **WHEN** the JUnit file holds cases of 60 files of the tree
- **THEN** the facts list 50 of them and the cases of the other 10 are counted under `other`

### Requirement: Only numbers are kept
Apart from the test-file names above, the facts SHALL hold numbers only. A coverage value is kept only when the text of `totals.percent_covered_display` (as `report` reads it, without a `%`) is ASCII digits `0`-`9` with at most one `.`, a digit on each side of the `.`, and a number from 0 to 100; it SHALL be kept as that text, so `100` stays `100`. No output of the check is part of the facts.

#### Scenario: A coverage value that is not a number
- **WHEN** the coverage file's `percent_covered_display` is `see https://example.com`
- **THEN** the facts hold no coverage and standard error has one line naming `results.coverage`

#### Scenario: Forms that are not coverage
- **WHEN** `percent_covered_display` is, in turn, `nan`, `inf`, `1e3`, `-5`, `101`, `9 4`, `.`, `.5`, `100.`, `١٠٠` and `٩٤.٥`
- **THEN** in each case the facts hold no coverage and standard error has one line naming `results.coverage`

#### Scenario: A whole number stays whole
- **WHEN** `percent_covered_display` is `100`
- **THEN** the facts hold coverage `100`, not `100.0`

#### Scenario: Output is not kept
- **WHEN** the check prints `TOKEN=abc123` to both streams and passes
- **THEN** the result commit's message does not hold `abc123`
