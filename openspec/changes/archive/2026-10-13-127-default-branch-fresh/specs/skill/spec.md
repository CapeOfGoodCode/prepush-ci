## MODIFIED Requirements

### Requirement: The default branch hint yields a branch name
The `<default branch>` step of the skill SHALL give the commands `git remote set-head origin --auto` and then `git symbolic-ref refs/remotes/origin/HEAD`, SHALL tell the agent to remove the leading `refs/remotes/origin/` from the output of the second before passing it to `--default-branch`, and SHALL say that the first refreshes the local record from the remote. The result SHALL be a value `init` accepts, and the branch the remote has as its default.

#### Scenario: A repository with origin/HEAD
- **WHEN** the test runs the hint's commands in a repository whose remote's default branch is `trunk`, removes the leading `refs/remotes/origin/` and runs the `init` invocation of the skill with the result as the default branch
- **THEN** `init` exits 0 and the loaded config's default branch is `trunk`

#### Scenario: A branch name with a slash
- **WHEN** the same happens in a repository whose remote's default branch is `release/1`
- **THEN** `init` exits 0 and the loaded config's default branch is `release/1`

#### Scenario: A local branch named like the remote branch
- **WHEN** the same happens in a repository whose remote's default branch is `trunk` and which also has a local branch `origin/trunk`
- **THEN** `init` exits 0 and the loaded config's default branch is `trunk`

#### Scenario: A record older than a rename
- **WHEN** the same happens in a clone whose `origin/HEAD` names `origin/master` after the remote renamed its default branch to `main` and the clone ran `git fetch --prune origin`
- **THEN** `init` exits 0 and the loaded config's default branch is `main`

#### Scenario: The step says to remove the prefix
- **WHEN** a reader looks at the `<default branch>` step
- **THEN** it names `git remote set-head origin --auto` before `git symbolic-ref refs/remotes/origin/HEAD` and says to remove the leading `refs/remotes/origin/` from the output of the second

### Requirement: Without origin/HEAD the agent asks
The `<default branch>` step SHALL say that the commands fail when `origin` does not exist, cannot be reached, has no default branch, or the clone does not fetch it (a single-branch clone of another branch), and that the agent then asks the user for the name of the default branch and SHALL NOT guess it, nor read a record that was left from before. If the first command fails the agent SHALL NOT use the output of the second.

#### Scenario: A repository without origin/HEAD
- **WHEN** the test runs the hint's first command in a repository without a remote `origin` (so without `origin/HEAD`)
- **THEN** the command exits non-zero

#### Scenario: A remote that cannot be reached
- **WHEN** the test runs the hint's first command in a repository whose `origin/HEAD` names `origin/master` and whose remote `origin` is a path that is not a repository
- **THEN** the command exits non-zero

#### Scenario: A single-branch clone
- **WHEN** the test runs the hint's first command in a clone made with `--single-branch -b feature` of a remote whose default branch is `main`
- **THEN** the command exits non-zero

#### Scenario: The step says to ask
- **WHEN** a reader looks at the `<default branch>` step
- **THEN** it says the commands fail without a reachable `origin` with a default branch that the clone fetches, to ask the user for the default branch instead of guessing it, and not to use the second command's output when the first failed
