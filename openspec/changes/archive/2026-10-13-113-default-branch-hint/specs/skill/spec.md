## ADDED Requirements

### Requirement: The default branch hint yields a branch name
The `<default branch>` step of the skill SHALL give the command `git symbolic-ref refs/remotes/origin/HEAD` and SHALL tell the agent to remove the leading `refs/remotes/origin/` from its output before passing it to `--default-branch`. The result SHALL be a value `init` accepts.

#### Scenario: A repository with origin/HEAD
- **WHEN** the test runs the hint's command in a repository whose `origin/HEAD` names `origin/trunk`, removes the leading `refs/remotes/origin/` and runs the `init` invocation of the skill with the result as the default branch
- **THEN** `init` exits 0 and the loaded config's default branch is `trunk`

#### Scenario: A branch name with a slash
- **WHEN** the same happens in a repository whose `origin/HEAD` names `origin/release/1`
- **THEN** `init` exits 0 and the loaded config's default branch is `release/1`

#### Scenario: A local branch named like the remote branch
- **WHEN** the same happens in a repository whose `origin/HEAD` names `origin/trunk` and which also has a local branch `origin/trunk`
- **THEN** `init` exits 0 and the loaded config's default branch is `trunk`

#### Scenario: The step says to remove the prefix
- **WHEN** a reader looks at the `<default branch>` step
- **THEN** it names the command and says to remove the leading `refs/remotes/origin/` from its output

### Requirement: Without origin/HEAD the agent asks
The `<default branch>` step SHALL say that the command fails when `origin/HEAD` is unset, and that the agent then asks the user for the name of the default branch and SHALL NOT guess it.

#### Scenario: A repository without origin/HEAD
- **WHEN** the test runs the hint's command in a repository without `origin/HEAD` and then runs the `init` invocation of the skill with `trunk` as the default branch
- **THEN** the command exits non-zero, `init` exits 0 and the loaded config's default branch is `trunk`

#### Scenario: The step says to ask
- **WHEN** a reader looks at the `<default branch>` step
- **THEN** it says the command fails when `origin/HEAD` is unset and to ask the user for the default branch instead of guessing it
