## ADDED Requirements

### Requirement: A manager's hooks run the prepush-ci that doctor is
For the hooks of a manager (pre-commit, husky, lefthook), the `commit-msg` and `pre-push` checks SHALL also run the first `prepush-ci` on the `PATH` of `doctor` with `--version`, as the hook would find it, and pass only when the first line it prints equals the line `prepush-ci --version` prints for `doctor` itself. Their line SHALL contain the path of that executable and the line it printed, whether the check passes or fails; a fix line SHALL contain `PATH` and the line of `doctor`.

#### Scenario: The same version is found
- **WHEN** `install` and `pre-commit install` ran and the `prepush-ci` on `PATH` prints the line `doctor` itself prints for `--version`
- **THEN** the `commit-msg` and `pre-push` lines start with `ok` and contain the path of that executable and that line

#### Scenario: An older version is found
- **WHEN** `install` and `pre-commit install` ran and the `prepush-ci` on `PATH` prints `prepush-ci 0.0.1`, which is not the line of `doctor`
- **THEN** the `commit-msg` and `pre-push` lines start with `fail` and contain the path of that executable, `prepush-ci 0.0.1` and the line of `doctor`, each fix line contains `PATH` and the line of `doctor`, and the last line says that 2 of 6 checks did not pass

#### Scenario: Husky
- **WHEN** `install --hooks husky` ran, `core.hooksPath` is `.husky/_` and the `prepush-ci` on `PATH` prints `prepush-ci 0.0.1`
- **THEN** the `commit-msg` and `pre-push` lines start with `fail` and contain `prepush-ci 0.0.1`

#### Scenario: lefthook
- **WHEN** `install --hooks lefthook` and `lefthook install` ran and the `prepush-ci` on `PATH` prints the line of `doctor`
- **THEN** the `commit-msg` and `pre-push` lines start with `ok` and contain the path of that executable

### Requirement: An executable that cannot say its version fails the check
When no `prepush-ci` is on `PATH`, the checks of the previous requirement SHALL fail and their lines SHALL name `PATH`. When the executable exits with a non-zero status, prints no line, or has not finished 10 seconds after it was started, they SHALL fail, and their lines SHALL name its path and say that its version could not be read. An executable that has not finished SHALL be ended.

#### Scenario: No prepush-ci on PATH
- **WHEN** `install` and `pre-commit install` ran and `PATH` holds no executable named `prepush-ci`
- **THEN** the `commit-msg` and `pre-push` lines start with `fail` and name `PATH`

#### Scenario: The executable fails
- **WHEN** `install` and `pre-commit install` ran and the `prepush-ci` on `PATH` prints `prepush-ci 1.0` and exits 1
- **THEN** the `commit-msg` and `pre-push` lines start with `fail`, name the path of that executable and say that its version could not be read

#### Scenario: The executable prints nothing
- **WHEN** `install` and `pre-commit install` ran and the `prepush-ci` on `PATH` exits 0 and prints nothing
- **THEN** the `commit-msg` and `pre-push` lines start with `fail`, name the path of that executable and say that its version could not be read

#### Scenario: The executable does not finish
- **WHEN** `install` and `pre-commit install` ran and the `prepush-ci` on `PATH` is still running 10 seconds after it was started
- **THEN** `doctor` exits 1 after about 10 seconds, the `commit-msg` and `pre-push` lines start with `fail`, name the path of that executable and say that its version could not be read, and the process was ended

### Requirement: Only a check that would otherwise pass looks at PATH
The look-up of the previous requirements SHALL apply to a check only when every other requirement for its manager holds for it; otherwise that failure stands and no executable is run. Native hooks and `--hooks none` SHALL NOT look at `PATH`. Where a scenario of another requirement about a manager says its lines start with `ok`, it assumes a `prepush-ci` on `PATH` that prints the line of `doctor`.

#### Scenario: A failure that is already there stands
- **WHEN** `.pre-commit-config.yaml` lists a hook, `install` did not run and the `prepush-ci` on `PATH` writes a file when it runs
- **THEN** the `commit-msg` and `pre-push` lines start with `fail` and name `.pre-commit-config.yaml`, do not contain the path of that executable, and that file was not written

#### Scenario: Only one hook of the manager is incomplete
- **WHEN** `install --hooks husky` ran, the block was removed from `.husky/pre-push` and the `prepush-ci` on `PATH` prints `prepush-ci 0.0.1`
- **THEN** the `commit-msg` line starts with `fail` and contains `prepush-ci 0.0.1`, and the `pre-push` line starts with `fail` and names `.husky/pre-push`

#### Scenario: Native hooks do not use PATH
- **WHEN** `install` ran for native hooks and `PATH` holds no executable named `prepush-ci`
- **THEN** the `commit-msg` and `pre-push` lines start with `ok`

#### Scenario: No local hooks wanted
- **WHEN** `.pre-commit-config.yaml` exists and `doctor --hooks none` runs while the `prepush-ci` on `PATH` writes a file when it runs
- **THEN** the `commit-msg` and `pre-push` lines start with `ok` and say that no local hooks are wanted, and that file was not written

### Requirement: A doctor that cannot read its own version fails the manager checks
When `doctor` cannot read the version line of its own installation (it runs from source that is not an installed distribution), the manager checks that would otherwise pass SHALL fail with a line saying that this `prepush-ci` cannot read its own version and a fix line saying to run `doctor` from an installed `prepush-ci`. No executable SHALL be run for them and `doctor` SHALL NOT end with a traceback.

#### Scenario: Not an installed distribution
- **WHEN** `install` and `pre-commit install` ran and `doctor` runs from a copy of the code that is not an installed distribution
- **THEN** the `commit-msg` and `pre-push` lines start with `fail` and say that `prepush-ci` cannot read its own version, each fix line says to install it, the last line says that 2 of 6 checks did not pass, no executable on `PATH` was run, and the standard error holds no traceback

#### Scenario: Native hooks do not need the version
- **WHEN** `install` ran for native hooks and `doctor` runs from a copy of the code that is not an installed distribution
- **THEN** the `commit-msg` and `pre-push` lines start with `ok`

#### Scenario: A failure that is already there stands without the version
- **WHEN** `.pre-commit-config.yaml` lists a hook, `install` did not run and `doctor` runs from a copy of the code that is not an installed distribution
- **THEN** the `commit-msg` and `pre-push` lines start with `fail` and name `.pre-commit-config.yaml`
