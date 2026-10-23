## ADDED Requirements

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
- **THEN** the facts hold coverage 94.5, 0 ruff errors and 0 mypy errors

#### Scenario: Errors counted
- **WHEN** the check passes and writes a ruff file with two errors and a mypy file with `Found 3 errors in 1 file`
- **THEN** the facts hold 2 ruff errors and 3 mypy errors

#### Scenario: Nothing named
- **WHEN** the config has no `results`
- **THEN** the facts hold the duration and nothing else

### Requirement: The files of this run only
Before it starts the check, the tool SHALL delete each file named in `results` that exists and is not tracked in `HEAD`, so that a file left by an earlier run is never read as a fact of this one. A named file that is tracked SHALL NOT be deleted and SHALL NOT be read: the tool SHALL print one line on standard error that names its `results` key and says it is tracked. A cached pass that skips the check SHALL delete nothing.

#### Scenario: A stale file is not read
- **WHEN** `results` names `out/a.xml`, an untracked `out/a.xml` with 4 failing cases exists, and the check passes without writing it
- **THEN** the facts hold no test counts

#### Scenario: The file the check writes is read
- **WHEN** an untracked `out/a.xml` from an earlier run exists and the check writes it again with 3 passing cases
- **THEN** the facts hold 3 passed

#### Scenario: A tracked file is left alone
- **WHEN** `results` names `docs/cov.json`, which is tracked, and the check passes
- **THEN** the file is unchanged, the facts hold no coverage and standard error has one line naming `results.coverage` that says the file is tracked

#### Scenario: A skipped check deletes nothing
- **WHEN** a pass is cached and the push skips the check while an untracked `out/a.xml` exists
- **THEN** `out/a.xml` is still there

#### Scenario: A failing check
- **WHEN** an untracked `out/a.xml` exists and the check fails
- **THEN** no result ref is recorded

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
Apart from the test-file names above, the facts SHALL hold numbers only: a coverage value is kept only when it is a decimal number, and no output of the check is part of the facts.

#### Scenario: A coverage value that is not a number
- **WHEN** the coverage file's `percent_covered_display` is `see https://example.com`
- **THEN** the facts hold no coverage and standard error has one line naming `results.coverage`

#### Scenario: Output is not kept
- **WHEN** the check prints `TOKEN=abc123` to both streams and passes
- **THEN** the result commit's message does not hold `abc123`
