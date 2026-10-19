## ADDED Requirements

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
