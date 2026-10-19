## MODIFIED Requirements

### Requirement: Report posts the result of a run
`prepush-ci report --result passed|failed --tree <hash>` SHALL, from any directory inside a worktree, post the result of a run of the check for the commit named by `--commit` (default `HEAD`), as the next requirements say; with `--start` in place of `--result` it SHALL mark the run as started. It SHALL print one line on standard output that names the full sha of the commit, the result (`started` for `--start`) and how it was posted (`check run` or `commit status`).

#### Scenario: Result posted
- **WHEN** `prepush-ci report --result passed --tree <the tree of HEAD>` runs with a token and the API accepts the request
- **THEN** it exits 0 and prints one line holding the 40-hex sha of `HEAD`, `passed` and `commit status`

#### Scenario: Commit other than HEAD
- **WHEN** `--commit` names an earlier commit and `--tree` is that commit's tree
- **THEN** the request is for the sha of that commit

#### Scenario: Run from a subdirectory
- **WHEN** `prepush-ci report` starts in a subdirectory of the worktree
- **THEN** it posts as it does from the root

#### Scenario: Not inside a worktree
- **WHEN** `prepush-ci report` runs outside a git worktree
- **THEN** it exits 1 and sends no request

#### Scenario: Commit not found
- **WHEN** `--commit` names no commit
- **THEN** it exits 1, the reason names the argument and no request is sent

#### Scenario: Start posted
- **WHEN** `prepush-ci report --start --tree <the tree of HEAD>` runs with a token and the API accepts the request
- **THEN** it exits 0 and prints one line holding the 40-hex sha of `HEAD`, `started` and `commit status`

### Requirement: The exit status says whether the result was posted
`report` SHALL exit 0 when the result was posted, 2 when the command line is rejected (a missing or unknown flag, a malformed value) and 1 in every other case, and a refusal SHALL send no request. Exactly one of `--result` and `--start` SHALL be given.

#### Scenario: Result missing or unknown
- **WHEN** `--result` is neither given with a value of `passed` or `failed` nor replaced by `--start`
- **THEN** it exits 2, names `--result` and sends no request

#### Scenario: Tree missing
- **WHEN** `--tree` is missing
- **THEN** it exits 2, names `--tree` and sends no request

#### Scenario: Unknown flag
- **WHEN** `prepush-ci report` runs with a flag it does not have
- **THEN** it exits 2, names the flag and sends no request

#### Scenario: Help
- **WHEN** `prepush-ci report --help` runs
- **THEN** it exits 0, lists every flag of the command and sends no request

#### Scenario: Result and start together
- **WHEN** `--start` and `--result passed` are given together
- **THEN** it exits 2, the reason names `--start` and `--result` and no request is sent

### Requirement: The check run names what ran
The check run SHALL be, for the sha of the commit, a run with the name given by `--name` or `prepush-ci / full`, `status` `completed` and `conclusion` `success` for `passed` and `failure` for `failed`; it is the run started by `--start` when there is one (see "The final report completes the run in progress") and a new run otherwise. Its title SHALL be the test counts when a JUnit file was given and `Passed` or `Failed` otherwise.

#### Scenario: Green run
- **WHEN** `report --result passed` runs with a JUnit file of 3 passing, 1 skipped tests and a coverage file of 94.5%
- **THEN** the check run has `conclusion` `success`, a title with `3 passed`, `0 failed` and `1 skipped`, and a summary with `94.5%`

#### Scenario: Red run
- **WHEN** `report --result failed` runs with a JUnit file with 2 failing tests
- **THEN** the check run has `conclusion` `failure` and a title with `2 failed`

#### Scenario: Default name
- **WHEN** `--name` is not given
- **THEN** the check run is called `prepush-ci / full`

#### Scenario: Chosen name
- **WHEN** `--name "prepush-ci / unit"` is given
- **THEN** the check run is called `prepush-ci / unit`

#### Scenario: Without files
- **WHEN** neither `--junit` nor `--coverage` is given
- **THEN** the title is `Passed` and the summary has no coverage entry

## ADDED Requirements

### Requirement: A run can be shown as in progress
`report --start --tree <hash>` SHALL, with an app, create the check run of the commit (named by `--name` or `prepush-ci / full`) with `status` `in_progress`, the title `Running` and a summary that names the sha, the tree, the `check`, the `preflight` and that the result will be reported from a session. It SHALL check `--tree` and read the config as a result does. When the app already has an `in_progress` run of that name on the commit, it SHALL update that run's `started_at` instead.

#### Scenario: Run started
- **WHEN** `report --start --tree <the tree of HEAD>` runs with an app and the commit has no check run
- **THEN** exactly one check run is created, with `status` `in_progress`, the name `prepush-ci / full`, the title `Running` and a summary that holds the commit's sha, its tree and the `check`, and the command exits 0

#### Scenario: Chosen name
- **WHEN** `--start --name "prepush-ci / unit"` is given
- **THEN** the check run is called `prepush-ci / unit`

#### Scenario: Started twice
- **WHEN** `report --start` runs twice for the same commit and name, and the first run is still `in_progress`
- **THEN** the second call creates no check run and updates the `started_at` of the first

#### Scenario: A completed run is left alone
- **WHEN** the commit has a completed check run of that name made by the app, and `report --start` runs
- **THEN** a new check run is created and the completed one is not updated

#### Scenario: Tree differs
- **WHEN** `--start` is given a tree that is not the commit's tree
- **THEN** it exits 1, the reason names both hashes and no request is sent

#### Scenario: Without an app a pending status
- **WHEN** `report --start` runs without an app and with `GITHUB_TOKEN` set
- **THEN** the only request that creates a result is a commit status with `state` `pending`, the `context` given by `--name` or `prepush-ci/full` and a description with the first 7 characters of the tree and `reported from a session`

### Requirement: A start takes no flag of a result
`report --start` SHALL accept `--tree`, `--commit` and `--name` and no other flag of a result (`--result`, `--junit`, `--coverage`, `--ruff`, `--mypy`, `--duration`, `--tool`). A refused combination SHALL exit 2, name the flag and send no request.

#### Scenario: A flag of a result
- **WHEN** `--start` is given together with `--junit results.xml`
- **THEN** it exits 2, the reason names `--junit` and no request is sent

### Requirement: The final report completes the run in progress
With an app, `report --result` SHALL look up the check runs of the commit's sha with the name of the run, the status `in_progress` and the app's id (`GET /repos/<owner>/<repo>/commits/<sha>/check-runs?check_name=<name>&status=in_progress&app_id=<id>`). When it finds one it SHALL complete that run with `PATCH /repos/<owner>/<repo>/check-runs/<id>` and create no other. When it finds none it SHALL create the check run as before. When several are found it SHALL complete the one with the highest id.

#### Scenario: The started run is completed
- **WHEN** `report --start` and then `report --result passed` run for the same commit with an app
- **THEN** the final call updates the run the first one created to `completed` with `conclusion` `success` and creates no check run

#### Scenario: No run in progress
- **WHEN** `report --result passed` runs with an app and the commit has no run in progress of that name
- **THEN** it creates one check run, `completed` with `conclusion` `success`, and updates none

#### Scenario: Another name
- **WHEN** a run named `prepush-ci / full` is in progress and `report --result passed --name "prepush-ci / unit"` runs
- **THEN** the run `prepush-ci / full` is not updated and a new run `prepush-ci / unit` is created

#### Scenario: Several in progress
- **WHEN** the lookup finds two runs in progress with the ids 7 and 9
- **THEN** run 9 is completed and run 7 is not updated

#### Scenario: Lookup fails
- **WHEN** the lookup is answered with 403
- **THEN** it exits 1, the error names `403` and no check run is created

#### Scenario: Without an app a status replaces the pending one
- **WHEN** `report --start` and then `report --result passed` run without an app, with the same name
- **THEN** the second call creates a commit status with `state` `success` and the same `context` as the pending one

### Requirement: Failures become annotations
With an app, each failure SHALL become one annotation with the `path` of its file, `start_line` and `end_line` both its line, `annotation_level` `failure`, a `title` naming the tool (`pytest`, `ruff` or `mypy`) and a `message`. Without an app the failure files SHALL be read and checked, not posted.

#### Scenario: Without an app
- **WHEN** a ruff file with one error is given and `report --result failed` runs without an app
- **THEN** it exits 0, the commit status is created as without the file and no annotation is sent

### Requirement: A failed case sits on its line plus one
`--junit` SHALL yield one annotation per failed case that has a `file` and a `line` attribute, with the message of the case. The `line` of a case is 0-based, as pytest writes it, so the annotation's `start_line` and `end_line` SHALL be `line` + 1.

#### Scenario: A failing test on its line
- **WHEN** a JUnit file holds a failed case with `file="tests/a_spec.py"` and `line="117"` and `report --result failed` runs with an app
- **THEN** the check run has one annotation with `path` `tests/a_spec.py`, `start_line` 118, `end_line` 118, `annotation_level` `failure` and the title `pytest`

#### Scenario: A failing test without a location
- **WHEN** a JUnit file holds a failed case with no `line` attribute
- **THEN** the check run has no annotation for it and the counts still hold it as failed

### Requirement: Ruff and mypy output is read
`--ruff <path>` (repeatable) SHALL be read as the output of `ruff check --output-format json`, one annotation per element, with the message `<code> <message>`. `--mypy <path>` (repeatable) SHALL be read as the output of mypy, one annotation per line of the form `<path>:<line>[:<column>]: error: <message>` where `<path>` may begin with a drive letter such as `C:\`; `note:` lines SHALL yield none.

#### Scenario: A ruff error
- **WHEN** a ruff JSON file holds an error `F401` "`os` imported but unused" at row 3 of the absolute path of `src/a.py` inside the worktree
- **THEN** the check run has an annotation with `path` `src/a.py`, `start_line` 3, the title `ruff` and a message holding `F401` and `os` imported but unused

#### Scenario: A mypy error
- **WHEN** a mypy file holds `src/a.py:42: error: Returning Any from function declared to return "Mode"  [no-any-return]`, a `note:` line and `Found 1 error in 1 file (checked 1 source file)`
- **THEN** the check run has exactly one annotation, with `path` `src/a.py`, `start_line` 42 and the title `mypy`

#### Scenario: A mypy error with a column
- **WHEN** a mypy file holds `src/a.py:42:9: error: Name "x" is not defined  [name-defined]`
- **THEN** the annotation is on line 42 of `src/a.py`

#### Scenario: Several files
- **WHEN** two ruff files are given
- **THEN** the annotations of both are on the check run

### Requirement: Paths of failures are taken from the top of the worktree
A path of a failure that is relative SHALL be taken from the top of the worktree, whatever directory `report` runs in. A path that is absolute and inside the worktree SHALL be made relative to its top. A path outside the worktree SHALL make `report` exit 1, name the path and send no request. The `path` of an annotation SHALL use `/` as separator whatever the platform, because GitHub matches it against the paths of the repository; a `\` in a path read from a file SHALL be taken as a separator.

#### Scenario: A relative path
- **WHEN** a mypy file names `src/a.py` and `report` runs in a subdirectory of the worktree
- **THEN** the annotation's `path` is `src/a.py`

#### Scenario: An absolute path
- **WHEN** a ruff file names the absolute path of `src/a.py` inside the worktree
- **THEN** the annotation's `path` is `src/a.py`

#### Scenario: A path outside the worktree
- **WHEN** a ruff file holds a path outside the worktree
- **THEN** it exits 1, the reason names that path and no request is sent

#### Scenario: A path with backslashes
- **WHEN** a mypy file holds `src\a.py:42: error: Name "x" is not defined  [name-defined]`
- **THEN** the annotation's `path` is `src/a.py`

#### Scenario: An absolute path with a drive letter
- **WHEN** a ruff file names `C:\work\repo\src\a.py` and the top of the worktree is `C:\work\repo`
- **THEN** the annotation's `path` is `src/a.py`

#### Scenario: A mypy path with a drive letter
- **WHEN** a mypy file holds `C:\work\repo\src\a.py:42: error: Name "x" is not defined  [name-defined]` and the top of the worktree is `C:\work\repo`
- **THEN** the annotation is on line 42 of `src/a.py`

### Requirement: Failure files that cannot be trusted are refused
A `--ruff` file that is not a JSON array of objects with a `filename`, a `location` with a `row`, a `code` and a `message`, or a `--mypy` file that holds neither `Success: no issues found` nor `Found <n> error` SHALL make `report` exit 1 and name the file, with no request sent. A file that does not exist SHALL be refused likewise. A `passed` result with an error in a `--ruff` or `--mypy` file SHALL be refused.

#### Scenario: Missing file
- **WHEN** `--ruff` names a file that does not exist
- **THEN** it exits 1, the reason names the file and no request is sent

#### Scenario: Not ruff
- **WHEN** `--ruff` names a file of plain text
- **THEN** it exits 1, the reason names the file and no request is sent

#### Scenario: Not mypy
- **WHEN** `--mypy` names a file of plain text with no summary line of mypy
- **THEN** it exits 1, the reason names the file and no request is sent

#### Scenario: Clean mypy output
- **WHEN** `--mypy` names a file that holds `Success: no issues found in 12 source files` and `--result passed` is given
- **THEN** the check run is created with `conclusion` `success` and no annotation

#### Scenario: Passed with a lint error
- **WHEN** `--result passed` is given with a ruff file that holds one error
- **THEN** it exits 1, the reason says the result contradicts the file and no request is sent

#### Scenario: Passed with a type error
- **WHEN** `--result passed` is given with a mypy file that holds one `error:` line
- **THEN** it exits 1, the reason says the result contradicts the file and no request is sent

### Requirement: Annotations are sent in batches of 50
`report` SHALL send the annotations in requests of at most 50 each, in the order of the files given: the request that creates or completes the check run carries the first 50 and each following `PATCH` of the same run the next 50 with the same `output` title and summary. Every annotation SHALL arrive exactly once. When a request fails, `report` SHALL exit 1 and send no further request.

#### Scenario: Exactly 50
- **WHEN** a mypy file holds 50 errors and `report --result failed` runs with an app
- **THEN** one request carries all 50 annotations and no later request carries any

#### Scenario: More than 50
- **WHEN** a mypy file holds 120 errors and `report --result failed` runs with an app
- **THEN** the requests carry 50, 50 and 20 annotations, every one of the 120 arrives exactly once and every request goes to the same check run

#### Scenario: No failures
- **WHEN** `report --result failed` runs with an app and no file holds a located failure
- **THEN** the check run is sent without annotations

#### Scenario: A later batch is rejected
- **WHEN** the second batch of three is answered with 422
- **THEN** it exits 1, the error names `422` and the third batch is not sent

### Requirement: The summary of a red run lists the failures first
When the check run's summary is made for a `failed` result that has failures in its files (failed cases, ruff errors, mypy errors), the Markdown SHALL begin with a section that lists them, before the entries that name what ran: at most 20, then a line `and <n> more` when there are more. A failed case without a location SHALL be listed, with its name.

#### Scenario: Failures before the table
- **WHEN** `report --result failed` runs with a JUnit file that has one failing case and a mypy file with one error
- **THEN** the summary holds the failing case and the mypy error before the commit's sha and the `check` command

#### Scenario: More than 20 failures
- **WHEN** a mypy file holds 25 errors
- **THEN** the summary lists 20 of them followed by `and 5 more`, and all 25 are annotations

#### Scenario: A failure without a location is listed
- **WHEN** a JUnit file holds a failed case named `test_a` without a `line`
- **THEN** the summary lists `test_a` in the section of the failures

#### Scenario: A green run has no such section
- **WHEN** `report --result passed` runs
- **THEN** the summary holds no section of failures

### Requirement: A listed failure is one short line
A failure in the summary SHALL be one line with its tool, its location when known and its text: the first line of its message, or the name of the case for a failed case without a location. The text SHALL be at most 200 characters, cut with `…` as the 200th character when it is longer; the characters counted are those of the text, not of what wraps it (see "A listed failure is shown as typed").

#### Scenario: A message of several lines
- **WHEN** a JUnit file holds a failed case with a location whose message is `AssertionError: assert a == b` followed by a line break and more lines of a diff
- **THEN** the summary lists the case with `AssertionError: assert a == b` and none of the lines after the break

#### Scenario: A long message is cut
- **WHEN** a failure's message, or the name of a failed case, is 5000 characters long
- **THEN** its text in the summary is 200 characters long and ends with `…`

#### Scenario: A short message is whole
- **WHEN** a failure's message is exactly 200 characters long
- **THEN** its text in the summary is that message, with no `…`

### Requirement: A listed failure is shown as typed
In the summary, the location and the text of a listed failure SHALL each be written as a Markdown code span, as `main` writes the other free values of the summary, so that GitHub shows the characters as they are in the file: `*`, `_`, `<`, `>`, `|` and backticks included.

#### Scenario: Markdown characters in a message
- **WHEN** a failed case has the message `assert 2*3 == 7*1` and another has `<built-in function len>`
- **THEN** each text is a code span in the summary, so GitHub shows `2*3`, `7*1` and `<built-in function len>` as typed, without emphasis and without a vanished tag

#### Scenario: Markdown characters in a name
- **WHEN** a failed case without a location is named `test_x[__init__]`
- **THEN** the summary lists it as a code span, so GitHub shows `test_x[__init__]` as typed

#### Scenario: A backtick in a message
- **WHEN** a failure's message holds a backtick
- **THEN** the code span is closed by a longer run of backticks than any in the message, and GitHub shows the message as typed
