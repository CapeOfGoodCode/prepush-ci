## ADDED Requirements

### Requirement: Native hooks through core.hooksPath
`prepush-ci install` SHALL write the scripts `commit-msg` and `pre-push` into the directory `prepush-ci/hooks` of the repository's common git directory, make them executable and set the repository's local `core.hooksPath` to that directory's absolute path. The `commit-msg` script SHALL run `prepush-ci hook commit-msg` with the arguments git passes; the `pre-push` script SHALL run `prepush-ci hook pre-push` with the arguments and standard input git passes. No file of the worktree SHALL change.

#### Scenario: Trailer written after install
- **WHEN** `install` ran in a repository without any hook and `git commit -m "add x"` runs with `PREPUSH_CI=full`
- **THEN** the commit's message ends with the trailer `Prepush-CI: full`

#### Scenario: Check run on push after install
- **WHEN** `install` ran, the config's `check` writes a marker file, and `git push origin main` pushes a clean, checked-out commit that carries the trailer
- **THEN** the marker file exists and the push reaches the remote

#### Scenario: The worktree stays clean
- **WHEN** `install` runs in a repository with a clean worktree
- **THEN** `git status --porcelain` still prints nothing

### Requirement: The tool is found without PATH
The scripts SHALL start the tool as `<python> -m prepush_ci`, where `<python>` is the interpreter that ran `install`, recorded in the file `python` of the hooks directory. They SHALL NOT look up `prepush-ci` on `PATH`.

#### Scenario: prepush-ci is not on PATH
- **WHEN** `install` ran from an interpreter whose scripts directory is not on `PATH`, and a commit runs with `PREPUSH_CI=full`
- **THEN** the commit's message ends with the trailer

### Requirement: A missing interpreter
When the recorded interpreter does not exist, the `pre-push` script SHALL refuse the push and its message SHALL name `prepush-ci install`. The `commit-msg` script SHALL print a warning naming `prepush-ci install` on standard error, write no trailer and exit 0.

#### Scenario: Push with a vanished interpreter
- **WHEN** the file `python` names a path that does not exist and `git push origin main` runs
- **THEN** the push is refused and the error contains `prepush-ci install`

#### Scenario: Commit with a vanished interpreter
- **WHEN** the file `python` names a path that does not exist and `git commit -m "add x"` runs with `PREPUSH_CI=full`
- **THEN** the commit succeeds without the trailer and the warning contains `prepush-ci install`

### Requirement: The previous hooks directory
The previous hooks directory SHALL be the directory git would use for hooks without `install`: the effective `core.hooksPath` of any scope, otherwise the directory `git rev-parse --git-path hooks` prints (under the common git directory, also in a linked worktree). It SHALL be recorded in the file `previous` of the hooks directory. `install` SHALL NOT modify it.

#### Scenario: Linked worktree
- **WHEN** `.git/hooks/pre-push` exits 1, `install` runs in a linked worktree of the repository, and a trailer commit is pushed from either worktree
- **THEN** the push is refused by that hook

#### Scenario: Existing core.hooksPath
- **WHEN** `core.hooksPath` is `custom-hooks`, which holds a `pre-push` hook that exits 1, and `install` ran
- **THEN** a push is refused by that hook, and `custom-hooks` holds the same files with the same contents as before

### Requirement: Existing hooks keep running
For `commit-msg` and `pre-push` the scripts SHALL, each time they run, first run the hook of the same name in the previous directory with the same arguments and standard input, only if it exists and is executable, as git does, and SHALL abort with its exit status when it fails, without running ours.

#### Scenario: Existing pre-push hook that passes
- **WHEN** `.git/hooks/pre-push` exists and exits 0, `install` ran, and a trailer commit is pushed
- **THEN** the existing hook ran and the check ran

#### Scenario: Existing pre-push hook that fails
- **WHEN** `.git/hooks/pre-push` exists and exits 1, `install` ran, and a trailer commit is pushed
- **THEN** the push is refused, the check did not run and the remote has no new commit

#### Scenario: Existing commit-msg hook
- **WHEN** `.git/hooks/commit-msg` appends the line `Reviewed` to the message, `install` ran, and `git commit -m "add x"` runs with `PREPUSH_CI=full`
- **THEN** the commit's message contains `Reviewed` and ends with the trailer

#### Scenario: Existing hook gets the push input
- **WHEN** the existing `pre-push` hook copies its standard input to a file and a commit is pushed after `install`
- **THEN** the file holds git's ref line for the pushed branch and the remote name is its first argument

#### Scenario: Existing pre-push hook that is not executable
- **WHEN** `.git/hooks/pre-push` exists without the executable bit and exits 1, `install` ran, and a trailer commit is pushed
- **THEN** the check ran and the push reached the remote

#### Scenario: Samples are not hooks
- **WHEN** `.git/hooks/pre-push.sample` exists and `install` ran
- **THEN** the sample did not run on a push and `install` wrote no forwarding script for it

### Requirement: Other hooks are forwarded
For every regular file of the previous directory, executable or not, that is not named `*.sample` and is not `commit-msg` or `pre-push`, `install` SHALL write a script of the same name into the hooks directory that does what git would do with the previous directory each time it runs: it starts the previous hook with the same arguments and standard input and exits with its status, only if that hook exists and is executable; otherwise it exits 0.

#### Scenario: Existing pre-commit hook
- **WHEN** `.git/hooks/pre-commit` exists and exits 1, and `install` ran
- **THEN** `git commit` fails because of that hook

#### Scenario: Non-executable hook
- **WHEN** `.git/hooks/pre-commit` exists without the executable bit and exits 1, and `install` ran
- **THEN** `git commit` succeeds

#### Scenario: Hook deleted after install
- **WHEN** `install` ran with an executable `.git/hooks/pre-commit`, which is then deleted
- **THEN** `git commit` succeeds without a rerun of `install`

#### Scenario: Hook receives its arguments
- **WHEN** `.git/hooks/post-checkout` writes its arguments to a file and `install` ran, and `git checkout -b topic` runs
- **THEN** the file holds the three arguments git passes to `post-checkout`

### Requirement: Install is idempotent
Running `install` again SHALL write no file and change no config when nothing differs from what it would write, print a line containing `already installed` and exit 0. When something differs (another interpreter, a new hook in the previous directory) it SHALL write the difference and print a line containing `updated`. A first run SHALL print a line containing `installed`.

#### Scenario: Second run
- **WHEN** `install` runs twice in a row
- **THEN** the second run exits 0 and prints `already installed`, every file in the hooks directory has the same contents and modification time as after the first run, and `core.hooksPath` is unchanged

#### Scenario: New hook after install
- **WHEN** `install` ran, then `.git/hooks/post-merge` is added, and `install` runs again
- **THEN** the second run prints `updated` and the hooks directory has a `post-merge` script that runs it

#### Scenario: Another interpreter
- **WHEN** `install` ran from one interpreter and runs again from another
- **THEN** the second run prints `updated` and the file `python` names the second interpreter

### Requirement: A rerun keeps the previous directory
While the effective `core.hooksPath` is ours, a rerun SHALL keep the recorded previous directory, never recording the hooks directory itself. When it is something else (a hook manager set it after the first run), that value SHALL become the previous directory, so a rerun never drops it, and the run SHALL print `updated`.

#### Scenario: Existing hook survives a second run
- **WHEN** `.git/hooks/pre-push` exits 1 and `install` runs twice
- **THEN** a push of a trailer commit is refused by that hook

#### Scenario: A manager changed core.hooksPath
- **WHEN** `install` ran, then `core.hooksPath` is set to `managed-hooks`, which holds a `pre-push` hook that exits 1, and `install` runs again
- **THEN** the second run prints `updated`, `core.hooksPath` is ours again and a push of a trailer commit is refused by that hook



### Requirement: The report and its errors
`install` SHALL print the hooks directory and, when the previous directory holds any hook it chains or forwards, the previous directory. Outside a git repository it SHALL exit 1 and its message SHALL say there is no git repository.

#### Scenario: Report
- **WHEN** `install` runs in a repository whose `.git/hooks/pre-push` exists
- **THEN** the output names the hooks directory and `.git/hooks`

#### Scenario: Not a repository
- **WHEN** `install` runs in a directory that is not inside a git repository
- **THEN** it exits 1 and the message says there is no git repository
