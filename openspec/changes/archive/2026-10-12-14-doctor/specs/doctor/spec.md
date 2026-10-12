## ADDED Requirements

### Requirement: The report
`prepush-ci doctor` SHALL run six checks in this order and print one line for each: `config`, `commit-msg`, `pre-push`, `preflight`, `PREPUSH_CI`, `up-to-date`. A line SHALL start with `ok`, `fail` or `skip`, then the check's name and a colon. A failed check SHALL NOT stop the later ones.

#### Scenario: Everything is set up
- **WHEN** the config is valid, `install` ran, `PREPUSH_CI` is `full` and the remote `origin` has the branch `main`
- **THEN** `doctor` exits 0, prints six lines that start with `ok` in the order above and a last line saying all checks passed

#### Scenario: Nothing is set up
- **WHEN** `doctor` runs in a repository without config or hooks
- **THEN** it exits 1 and prints six lines in the order above, the `config`, `commit-msg` and `pre-push` lines starting with `fail`

#### Scenario: A failure does not stop the later checks
- **WHEN** the config is invalid and the hooks are installed
- **THEN** the `config` line starts with `fail`, the `commit-msg` and `pre-push` lines start with `ok` and the exit status is 1

### Requirement: The closing line and the exit status
The last line SHALL say that all checks passed or how many of the six did not, counting every line that does not start with `ok`, `skip` included. The exit status SHALL be 0 only when every line starts with `ok`, otherwise 1.

#### Scenario: The last line counts
- **WHEN** the hooks are installed, the config is valid, `PREPUSH_CI` is `foo` and the remote `origin` is unreachable
- **THEN** the last line says that 2 of 6 checks did not pass

### Requirement: Every failure names its fix
After the line of every failed check, `doctor` SHALL print a line that starts with whitespace and `fix:` and names the command to run, or the file and key to change. A line that starts with `ok` or `skip` SHALL have no such line after it.

#### Scenario: Hooks missing
- **WHEN** no hook is installed in a repository without a hook manager
- **THEN** the line after each of the `commit-msg` and `pre-push` failures starts with `fix:` after its whitespace and contains `prepush-ci install`

#### Scenario: Config missing
- **WHEN** the repository has no config
- **THEN** the line after the `config` failure contains `prepush-ci init`

#### Scenario: Passing checks have no fix line
- **WHEN** every check passes
- **THEN** the output contains no line with `fix:`

### Requirement: Doctor changes nothing
`doctor` SHALL NOT write a file, change a git config value, fetch, update a ref or write the run cache, in the working tree or in the git directory. The `preflight` command of the config is the user's own and runs as the hook runs it.

#### Scenario: Set-up repository untouched
- **WHEN** `doctor` runs in a repository where every check passes
- **THEN** every file of the working tree and of the git directory has the same contents and modification time as before, and no file was added

#### Scenario: Broken repository untouched
- **WHEN** `doctor` runs in a repository without config or hooks
- **THEN** no file was added, changed or removed and `core.hooksPath` is still unset

#### Scenario: No fetch
- **WHEN** the remote `main` has a commit the local `origin/main` lacks and `doctor` runs
- **THEN** the local `origin/main` still points to its old commit

### Requirement: The config check
The `config` check SHALL pass when the config loads as the `config` capability specifies, and its line SHALL name the file it was read from. When it does not load, the check SHALL fail and its line SHALL carry every problem the `config` capability reports, each naming its key, or name both places for a missing config.

#### Scenario: Dedicated file
- **WHEN** `.prepush-ci.toml` holds `check = "scripts/ci"`
- **THEN** the `config` line starts with `ok` and names `.prepush-ci.toml`

#### Scenario: Config in pyproject.toml
- **WHEN** there is no `.prepush-ci.toml` and `pyproject.toml` has `[tool.prepush-ci]` with a check
- **THEN** the `config` line starts with `ok` and names `pyproject.toml`

#### Scenario: No config
- **WHEN** neither place holds a config
- **THEN** the `config` line starts with `fail` and names `.prepush-ci.toml` and `[tool.prepush-ci]`

#### Scenario: Several problems
- **WHEN** the config contains an unknown key `foo` and sets `default_branch = 3`
- **THEN** the `config` line starts with `fail` and names `foo` and `default_branch`

#### Scenario: Malformed file
- **WHEN** `.prepush-ci.toml` is not valid TOML
- **THEN** the `config` line starts with `fail` and names `.prepush-ci.toml`

### Requirement: Checks that need the config are skipped without it
When the `config` check failed, the `preflight` and `up-to-date` checks SHALL print `skip` and say that the config is not valid. The `commit-msg`, `pre-push` and `PREPUSH_CI` checks SHALL NOT read the config.

#### Scenario: Invalid config
- **WHEN** the config contains an unknown key
- **THEN** the `preflight` and `up-to-date` lines start with `skip`, and the `commit-msg`, `pre-push` and `PREPUSH_CI` lines start with `ok` or `fail` by their own checks

#### Scenario: A skip is not a pass
- **WHEN** the config is missing, the hooks are installed and `PREPUSH_CI` is `full`
- **THEN** the `config` line starts with `fail`, the `preflight` and `up-to-date` lines start with `skip`, the exit status is 1 and the last line says that 3 of 6 checks did not pass

### Requirement: The choice of hooks
`doctor` SHALL accept `--hooks` with the values `install` accepts and `none`; any other value SHALL exit 2 and the message SHALL list them. The hooks checked SHALL be the given ones, else those of the one manager whose files `install` detects, else native. When several managers are detected and `--hooks` is absent, the `commit-msg` and `pre-push` checks SHALL fail, naming the managers and `--hooks`.

#### Scenario: Detected manager
- **WHEN** `.pre-commit-config.yaml` exists, `install` ran and `doctor` runs without `--hooks`
- **THEN** the `commit-msg` and `pre-push` lines start with `ok`

#### Scenario: Native forced
- **WHEN** `.pre-commit-config.yaml` exists, only the native hooks were installed and `doctor --hooks native` runs
- **THEN** the `commit-msg` and `pre-push` lines start with `ok`

#### Scenario: Unknown value
- **WHEN** `doctor --hooks jenkins` runs
- **THEN** it exits 2, prints no check line and the message contains `native`, `pre-commit`, `husky`, `lefthook` and `none`

#### Scenario: Native chosen over a detected manager
- **WHEN** `.pre-commit-config.yaml` exists, only the native hooks were installed and `doctor` runs without `--hooks`
- **THEN** the `commit-msg` and `pre-push` lines start with `fail` and the fix lines contain `--hooks native`

#### Scenario: Two managers
- **WHEN** `.pre-commit-config.yaml` and `lefthook.yml` both exist and `doctor` runs without `--hooks`
- **THEN** the `commit-msg` and `pre-push` lines start with `fail` and name `pre-commit`, `lefthook` and `--hooks`

#### Scenario: The option settles it
- **WHEN** both files exist, `install --hooks lefthook` ran and `doctor --hooks lefthook` runs
- **THEN** the `commit-msg` and `pre-push` lines start with `ok`

#### Scenario: A named manager that is not set up
- **WHEN** `.pre-commit-config.yaml` does not exist and `doctor --hooks pre-commit` runs
- **THEN** the `commit-msg` and `pre-push` lines start with `fail` and name `.pre-commit-config.yaml`

### Requirement: No local hooks wanted
`doctor --hooks none` SHALL make the `commit-msg` and `pre-push` checks pass, and their lines SHALL say that no local hooks are wanted. It SHALL inspect no hook, hook manager file or git config value. `none` is for `doctor` only; `install` does not accept it.

#### Scenario: No local hooks wanted
- **WHEN** `.pre-commit-config.yaml` exists, no hook was installed and `doctor --hooks none` runs
- **THEN** the `commit-msg` and `pre-push` lines start with `ok` and say that no local hooks are wanted

#### Scenario: Install does not accept none
- **WHEN** `install --hooks none` runs
- **THEN** it exits 2

### Requirement: Native hooks are installed
For native hooks, the `commit-msg` and `pre-push` checks SHALL each pass only when the effective `core.hooksPath`, made absolute against the worktree root, is the hooks directory `install` writes; the script of that check's name exists there and is executable; and the interpreter recorded in the file `python` exists. A failed check SHALL say which of the three does not hold.

#### Scenario: After install
- **WHEN** `install` ran
- **THEN** the `commit-msg` and `pre-push` lines start with `ok`

#### Scenario: Before install
- **WHEN** `core.hooksPath` is unset and no native hooks directory exists
- **THEN** both lines start with `fail` and name `core.hooksPath`

#### Scenario: Another tool took over the hooks
- **WHEN** `install` ran and `core.hooksPath` was then set to `.githooks`
- **THEN** both lines start with `fail` and name `.githooks`

#### Scenario: One script is missing
- **WHEN** `install` ran and the script `pre-push` was then deleted
- **THEN** the `commit-msg` line starts with `ok` and the `pre-push` line starts with `fail` and names `pre-push`

#### Scenario: A script is not executable
- **WHEN** `install` ran and the script `commit-msg` lost its executable bit
- **THEN** the `commit-msg` line starts with `fail` and says the script is not executable

#### Scenario: The interpreter vanished
- **WHEN** `install` ran and the file `python` now names a path that does not exist
- **THEN** both lines start with `fail` and name that path

#### Scenario: Linked worktree
- **WHEN** `install` ran in the main worktree and `doctor` runs in a linked worktree of the repository
- **THEN** the `commit-msg` and `pre-push` lines start with `ok`

### Requirement: A manager's block is present
For the hooks of a manager, the `commit-msg` and `pre-push` checks SHALL each require a block, as the `install` capability defines it, that contains `prepush-ci hook <name>` in the file `install` would change for that hook: `.pre-commit-config.yaml` for pre-commit, `.husky/<name>` for husky, the lefthook file for lefthook. A failed check SHALL name the file.

#### Scenario: pre-commit file without the block
- **WHEN** `.pre-commit-config.yaml` lists a hook and `install` did not run
- **THEN** both lines start with `fail` and name `.pre-commit-config.yaml`

#### Scenario: One husky file lacks the block
- **WHEN** `install --hooks husky` ran, `core.hooksPath` is `.husky/_` and the block was then removed from `.husky/pre-push`
- **THEN** the `commit-msg` line starts with `ok` and the `pre-push` line starts with `fail` and names `.husky/pre-push`

#### Scenario: A lefthook section lost its block
- **WHEN** `install --hooks lefthook` and `lefthook install` ran and the block was then removed from the `commit-msg:` section
- **THEN** the `commit-msg` line starts with `fail` and names `lefthook.yml`, and the `pre-push` line starts with `ok`

### Requirement: pre-commit and lefthook are activated
For pre-commit and lefthook, a check SHALL also require that the hook of its name in the directory git uses for hooks (the effective `core.hooksPath`, else the directory `git rev-parse --git-path hooks` prints) exists, is executable and contains the manager's name, `pre-commit` or `lefthook`. A failed check SHALL name `pre-commit install` or `lefthook install` as the step.

#### Scenario: pre-commit activated
- **WHEN** `install` and `pre-commit install` ran
- **THEN** the `commit-msg` and `pre-push` lines start with `ok`

#### Scenario: pre-commit not activated
- **WHEN** `install` ran and `pre-commit install` did not
- **THEN** both lines start with `fail` and the fix lines contain `pre-commit install`

#### Scenario: Only the default hook type activated
- **WHEN** `install` ran and `pre-commit install --hook-type pre-commit` ran
- **THEN** the `commit-msg` and `pre-push` lines start with `fail`

#### Scenario: lefthook not activated
- **WHEN** `install --hooks lefthook` ran and `.git/hooks/pre-push` does not exist
- **THEN** the `pre-push` line starts with `fail` and the fix line contains `lefthook install`

#### Scenario: lefthook activated
- **WHEN** `install --hooks lefthook` ran and `.git/hooks/commit-msg` and `.git/hooks/pre-push` are executable scripts that contain `lefthook`
- **THEN** the `commit-msg` and `pre-push` lines start with `ok`

### Requirement: husky is activated
For husky, a check SHALL also require that the effective `core.hooksPath`, relative to the worktree root, is `.husky` or `.husky/_`, and that the hook of its name exists there and is executable. A failed check SHALL name husky and either `core.hooksPath` or the missing hook, and its fix SHALL contain `npx husky`.

#### Scenario: husky set up
- **WHEN** `install --hooks husky` ran, `core.hooksPath` is `.husky/_` and `.husky/_/commit-msg` and `.husky/_/pre-push` are executable scripts
- **THEN** the `commit-msg` and `pre-push` lines start with `ok`

#### Scenario: husky not set up on this clone
- **WHEN** `install --hooks husky` ran and `core.hooksPath` is unset
- **THEN** both lines start with `fail`, name `core.hooksPath` and `husky`, and the fix lines contain `npx husky`

#### Scenario: husky stubs removed
- **WHEN** `install --hooks husky` ran, `core.hooksPath` is `.husky/_` and the directory `.husky/_` does not exist
- **THEN** both lines start with `fail` and name husky and the missing hook

### Requirement: The preflight check
The `preflight` check SHALL pass when every variable of `require_env` is set and non-empty in the environment of `doctor` and the `preflight` command, when the config sets one, exits 0 when run as the hook runs it. A failure SHALL name every missing variable, in which case the command is not run, or the command and its exit status; the command's output SHALL be printed, indented, only on failure. When the config sets neither key the check SHALL pass and say there is nothing to verify.

#### Scenario: Variable and command pass
- **WHEN** `require_env = ["DATABASE_URL"]` with the variable set and a `preflight` that exits 0
- **THEN** the `preflight` line starts with `ok`

#### Scenario: Missing variables
- **WHEN** `require_env = ["A_URL", "B_URL"]` and neither is set
- **THEN** the `preflight` line starts with `fail` and names `A_URL` and `B_URL`

#### Scenario: Missing variable stops the command
- **WHEN** `require_env` names an unset variable and the `preflight` command would write a file
- **THEN** the file does not exist

#### Scenario: Failing command
- **WHEN** the config sets a `preflight` that prints `db is down` and exits 3
- **THEN** the `preflight` line starts with `fail` and names the command and `3`, and the output contains `db is down` on an indented line

#### Scenario: Passing command stays quiet
- **WHEN** the config sets a `preflight` that prints `all good` and exits 0
- **THEN** the output does not contain `all good`

#### Scenario: Command runs from the repository root
- **WHEN** `doctor` runs in a subdirectory and the `preflight` writes its working directory to a file
- **THEN** the file holds the repository root

#### Scenario: Nothing to verify
- **WHEN** the config sets neither `preflight` nor `require_env`
- **THEN** the `preflight` line starts with `ok` and says there is nothing to verify

### Requirement: The PREPUSH_CI check
The `PREPUSH_CI` check SHALL pass for the values `full`, `off`, the empty string and unset, compared exactly, and its line SHALL say which one it found and what it means: `full` writes the trailer, `off` refuses the push of a commit with the trailer, empty or unset writes no trailer. Any other value SHALL fail the check, naming `full` and `off` in the line and in its fix.

#### Scenario: Full
- **WHEN** `PREPUSH_CI` is `full`
- **THEN** the `PREPUSH_CI` line starts with `ok` and contains `full`

#### Scenario: Unset
- **WHEN** `PREPUSH_CI` is unset
- **THEN** the `PREPUSH_CI` line starts with `ok` and says no trailer is written

#### Scenario: Misspelled
- **WHEN** `PREPUSH_CI` is `ful`
- **THEN** the `PREPUSH_CI` line starts with `fail` and names `ful`, `full` and `off`, and the fix line contains `PREPUSH_CI=full`

### Requirement: The expected mode
`doctor --mode <mode>` with `full`, `off` or `unset` SHALL also require the value of `PREPUSH_CI` to be that mode, the empty string counting as `unset`. A mismatch SHALL fail the `PREPUSH_CI` check, name the value found and the mode expected, and give a fix that sets or unsets the variable. Any other mode SHALL exit 2, print no check line and name the three.

#### Scenario: Expected and set
- **WHEN** `doctor --mode full` runs with `PREPUSH_CI=full`
- **THEN** the `PREPUSH_CI` line starts with `ok`

#### Scenario: Expected but unset
- **WHEN** `doctor --mode full` runs with `PREPUSH_CI` unset
- **THEN** the `PREPUSH_CI` line starts with `fail`, names `unset` and `full`, and the fix line contains `export PREPUSH_CI=full`

#### Scenario: Expected unset but set
- **WHEN** `doctor --mode unset` runs with `PREPUSH_CI=off`
- **THEN** the `PREPUSH_CI` line starts with `fail` and the fix line contains `unset PREPUSH_CI`

#### Scenario: Empty counts as unset
- **WHEN** `doctor --mode unset` runs with `PREPUSH_CI` set to the empty string
- **THEN** the `PREPUSH_CI` line starts with `ok`

#### Scenario: Unknown mode
- **WHEN** `doctor --mode on` runs
- **THEN** it exits 2, prints no check line and the message contains `full`, `off` and `unset`

### Requirement: The up-to-date ref is reachable
When `require_up_to_date` is `false`, the `up-to-date` check SHALL pass, say it is disabled and contact no remote. Otherwise it SHALL pass only when the ref is `<remote>/<branch>` of a configured remote and `git ls-remote --exit-code -- <remote> refs/heads/<branch>` finds the branch. It SHALL NOT check that `HEAD` contains the ref.

#### Scenario: Branch on the remote
- **WHEN** the default `require_up_to_date` is `origin/main` and the remote `origin` has `main`
- **THEN** the `up-to-date` line starts with `ok` and names `origin/main`

#### Scenario: Behind is not checked
- **WHEN** the remote `main` has a commit `HEAD` does not contain
- **THEN** the `up-to-date` line starts with `ok`

#### Scenario: Disabled
- **WHEN** the config sets `require_up_to_date = false` and the remote `origin` is unreachable
- **THEN** the `up-to-date` line starts with `ok` and says it is disabled

### Requirement: A failed up-to-date check says why
A failed `up-to-date` check SHALL say which holds: the ref has another form than `<remote>/<branch>`, the remote is not configured, the remote cannot be reached, or the remote has no such branch. Its fix SHALL name `require_up_to_date = false` as a way out.

#### Scenario: Ref without a remote
- **WHEN** the config sets `require_up_to_date = "main"`
- **THEN** the line starts with `fail`, says the ref must be `<remote>/<branch>` and the fix names `require_up_to_date = false`

#### Scenario: Remote not configured
- **WHEN** the config sets `require_up_to_date = "upstream/develop"` and the repository has no remote `upstream`
- **THEN** the line starts with `fail` and names `upstream`

#### Scenario: Unreachable remote
- **WHEN** the URL of `origin` points to a directory that does not exist
- **THEN** the line starts with `fail`, says the remote cannot be reached and the fix names `require_up_to_date = false`

#### Scenario: Branch missing on the remote
- **WHEN** `require_up_to_date = "origin/gone"` and the remote has no `gone`
- **THEN** the line starts with `fail` and names `origin/gone`

#### Scenario: Branch name with a slash
- **WHEN** `require_up_to_date = "origin/release/1"` and the remote has `release/1`
- **THEN** the `up-to-date` line starts with `ok`

### Requirement: Where doctor runs
`doctor` SHALL check the working tree that contains the current directory, wherever in it the command runs. Outside a git repository, and in a repository without a working tree, it SHALL exit 1, print no check line and say so.

#### Scenario: Subdirectory
- **WHEN** the config is valid, `install` ran, `PREPUSH_CI` is `full`, the remote has `main` and `doctor` runs in a subdirectory of the working tree
- **THEN** it exits 0 and the six lines start with `ok`

#### Scenario: Not a repository
- **WHEN** `doctor` runs in a directory that is not inside a git repository
- **THEN** it exits 1, prints no check line and the message says there is no git repository

#### Scenario: Bare repository
- **WHEN** `doctor` runs in a bare repository
- **THEN** it exits 1, prints no check line and the message says the repository has no working tree
