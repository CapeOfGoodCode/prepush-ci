## ADDED Requirements

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
