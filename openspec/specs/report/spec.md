# report Specification

## Purpose
`prepush-ci report`: posts the result of a run of the check, made in a session or on a machine, for a commit, as a check run through the team's GitHub App or, without an app, as a commit status. It refuses a tree that is not the commit's tree, runs nothing itself, and names in the check run what ran. With `--markdown` it posts nothing and prints the same summary as Markdown, behind a hidden marker that names the check, for a session that cannot reach the API to put into a comment.

## Requirements

### Requirement: Report posts the result of a run
Without `--markdown`, `prepush-ci report --result passed|failed --tree <hash>` SHALL, from any directory inside a worktree, post the result of a run of the check for the commit named by `--commit` (default `HEAD`), as the next requirements say; with `--start` in place of `--result` it SHALL mark the run as started. It SHALL print one line on standard output that names the full sha of the commit, the result (`started` for `--start`) and how it was posted (`check run` or `commit status`).

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
Without `--markdown`, `report` SHALL exit 0 when the result was posted, 2 when the command line is rejected (a missing or unknown flag, a malformed value) and 1 in every other case, and a refusal SHALL send no request. Exactly one of `--result` and `--start` SHALL be given.

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

### Requirement: Malformed values are refused
`report` SHALL refuse, before it reads anything else or sends a request, a `--tool` that is not `NAME=VERSION` with both parts non-empty, a `--duration` that is not a whole number of seconds of 0 or more, and an empty `--name`. It SHALL exit 2 and name the flag.

#### Scenario: Tool without a version
- **WHEN** `--tool ruff` is given
- **THEN** it exits 2, the reason names `--tool` and no request is sent

#### Scenario: Tool without a name
- **WHEN** `--tool =1.0` is given
- **THEN** it exits 2 and the reason names `--tool`

#### Scenario: Duration that is not a number
- **WHEN** `--duration abc` is given
- **THEN** it exits 2, the reason names `--duration` and no request is sent

#### Scenario: Negative duration
- **WHEN** `--duration -5` is given
- **THEN** it exits 2 and the reason names `--duration`

#### Scenario: Empty name
- **WHEN** `--name ""` is given
- **THEN** it exits 2, the reason names `--name` and no request is sent

### Requirement: Report runs nothing and reads the commit's config
`report` SHALL run neither the `check` nor the `preflight`. It SHALL read both from the config committed in the commit it reports on, and SHALL exit 1 without a request when that commit holds no config or an invalid one.

#### Scenario: The check does not run
- **WHEN** the config sets a `check` and a `preflight` that each write a file and `prepush-ci report` posts a result
- **THEN** neither file exists

#### Scenario: No config in the commit
- **WHEN** the commit holds no config
- **THEN** it exits 1, the reason says so and no request is sent

#### Scenario: Invalid config in the commit
- **WHEN** the config committed in the commit contains an unknown key
- **THEN** it exits 1, the reason names the key and no request is sent

#### Scenario: The committed config decides
- **WHEN** the worktree config differs from the one committed in the commit and `report` runs
- **THEN** the summary names the `check` of the commit's config

### Requirement: A result never shows on a state it did not check
`report` SHALL compare `--tree` with the tree hash of the commit it reports on. When they differ it SHALL exit 1, name both hashes and send no request. `--tree` SHALL be given in full; an abbreviation SHALL be refused.

#### Scenario: Tree differs
- **WHEN** `--tree` is the tree of another commit
- **THEN** it exits 1, the reason names the given tree and the commit's tree and no request is sent

#### Scenario: Tree of an amended commit
- **WHEN** a commit was checked, then amended with a new message (the tree is unchanged), and `report` runs with the checked tree for the amended commit
- **THEN** the result is posted for the amended commit's sha

#### Scenario: Tree of a later commit
- **WHEN** a commit was checked, a commit that changes a file was made on top, and `report` runs with the checked tree for `HEAD`
- **THEN** it exits 1 and no request is sent

#### Scenario: Abbreviated tree
- **WHEN** `--tree` is the first 7 characters of the commit's tree hash
- **THEN** it exits 1 and no request is sent

### Requirement: Where the result is posted
Without `--markdown`, `report` SHALL post to the GitHub repository named by the URL of the remote `origin` as `git remote get-url origin` prints it, in the forms `https://[<userinfo>@]<host>/<owner>/<repo>[.git]`, `ssh://[<user>@]<host>[:<port>]/<owner>/<repo>[.git]` and `git@<host>:<owner>/<repo>[.git]`, with `github.com` or `ssh.github.com` as `<host>`; the userinfo SHALL be ignored. When no repository can be read from `origin`, the environment SHALL name it (next requirement).

#### Scenario: HTTPS remote
- **WHEN** `origin` is `https://github.com/acme/widgets.git`
- **THEN** the request path holds `/repos/acme/widgets/`

#### Scenario: SSH remote without the suffix
- **WHEN** `origin` is `git@github.com:acme/widgets`
- **THEN** the request path holds `/repos/acme/widgets/`

#### Scenario: Remote with credentials
- **WHEN** `origin` is `https://x-access-token:s3cret@github.com/acme/widgets.git`
- **THEN** the request path holds `/repos/acme/widgets/`

#### Scenario: SSH URL form
- **WHEN** `origin` is `ssh://git@github.com/acme/widgets.git`
- **THEN** the request path holds `/repos/acme/widgets/`

#### Scenario: Repository from the environment
- **WHEN** `origin` is a local path and `GITHUB_REPOSITORY` is `acme/widgets`
- **THEN** the request path holds `/repos/acme/widgets/`

#### Scenario: No origin
- **WHEN** the repository has no remote `origin` and `GITHUB_REPOSITORY` is unset
- **THEN** it exits 1, the reason says no repository could be read from `origin` and no request is sent

#### Scenario: SSH over the HTTPS port
- **WHEN** `origin` is `ssh://git@ssh.github.com:443/acme/widgets.git`, `GITHUB_API_URL` is unset and `GITHUB_REPOSITORY` is unset
- **THEN** the request goes to `https://api.github.com` for `/repos/acme/widgets/`

#### Scenario: A short alias of origin
- **WHEN** the config sets `url.https://github.com/acme/.insteadOf` to `gh:`, `origin` is `gh:widgets`, `GITHUB_API_URL` is unset and `GITHUB_REPOSITORY` is unset
- **THEN** the request goes to `https://api.github.com` for `/repos/acme/widgets/`

#### Scenario: A push-only rewrite is ignored
- **WHEN** `origin` is `https://github.com/acme/widgets.git` and the config sets `url.https://github.com/fork/.pushInsteadOf` to `https://github.com/acme/`
- **THEN** the request path holds `/repos/acme/widgets/` and not `/repos/fork/`

#### Scenario: An ssh host alias
- **WHEN** `origin` is `git@github.com-work:acme/widgets.git`, `GITHUB_API_URL` is unset and `GITHUB_REPOSITORY` is unset
- **THEN** it exits 1, the reason says no repository could be read from `origin` and no request is sent

#### Scenario: An ssh host alias with a repository name
- **WHEN** `origin` is `git@github.com-work:acme/widgets.git`, `GITHUB_API_URL` is unset and `GITHUB_REPOSITORY` is `acme/widgets`
- **THEN** the request goes to `https://api.github.com` for `/repos/acme/widgets/`

#### Scenario: A host that only starts like GitHub's
- **WHEN** `origin` is `https://ssh.github.com.example.test/acme/widgets.git`, `GITHUB_API_URL` is unset and `GITHUB_REPOSITORY` is unset
- **THEN** it exits 1 and no request is sent

### Requirement: The repository from the environment
Without `--markdown`, when no repository can be read from `origin`, `GITHUB_REPOSITORY` SHALL name it, in the form `<owner>/<repo>`; an empty value counts as unset. When neither names a repository, or the value is not of that form, `report` SHALL exit 1 and send no request, and the reason SHALL name `GITHUB_REPOSITORY` when it was the one at fault.

#### Scenario: Malformed repository name
- **WHEN** `origin` is a local path and `GITHUB_REPOSITORY` is `acme`
- **THEN** it exits 1, the reason names `GITHUB_REPOSITORY` and no request is sent

#### Scenario: Empty repository name
- **WHEN** the repository has no remote `origin` and `GITHUB_REPOSITORY` is empty
- **THEN** it exits 1, the reason says no repository could be read from `origin` and no request is sent

#### Scenario: A proxy remote with a repository name
- **WHEN** `origin` is `https://git.example.test/acme/widgets.git`, `GITHUB_API_URL` is unset and `GITHUB_REPOSITORY` is `acme/widgets`
- **THEN** the request goes to `https://api.github.com` for `/repos/acme/widgets/`

### Requirement: The API address
Without `--markdown`, `report` SHALL send its requests to the address in `GITHUB_API_URL` or, when it is unset or empty, to `https://api.github.com`. A host other than `github.com` or `ssh.github.com` in the URL of `origin` SHALL count only when `GITHUB_API_URL` is set and non-empty.

#### Scenario: Another API address
- **WHEN** `GITHUB_API_URL` is the address of a local server and `origin` is `https://git.example.test/acme/widgets.git`
- **THEN** the request goes to that server for `/repos/acme/widgets/`

#### Scenario: A host without an API address
- **WHEN** `origin` is `https://git.example.test/acme/widgets.git`, `GITHUB_API_URL` is unset and `GITHUB_REPOSITORY` is unset
- **THEN** it exits 1 and no request is sent

#### Scenario: Empty API address
- **WHEN** `GITHUB_API_URL` is empty, `GITHUB_REPOSITORY` is unset and `origin` is `https://git.example.test/acme/widgets.git`
- **THEN** it exits 1 and no request is sent

### Requirement: The credentials decide check run or commit status
Without `--markdown`, an empty variable SHALL count as unset. With `PREPUSH_CI_APP_ID` and `PREPUSH_CI_APP_KEY` set, `report` SHALL post a check run as the app. With neither set and `GITHUB_TOKEN` or `GH_TOKEN` set (`GITHUB_TOKEN` first), it SHALL post a commit status with that token. With only one of the two app variables set, or with no credentials at all, it SHALL exit 1 and send no request, and the reason SHALL name what is missing.

#### Scenario: App configured
- **WHEN** both app variables are set
- **THEN** the only request that creates a result is a check run

#### Scenario: Token only
- **WHEN** no app variable is set and `GITHUB_TOKEN` is set
- **THEN** the only request that creates a result is a commit status, sent with that token

#### Scenario: Token from GH_TOKEN
- **WHEN** no app variable is set, `GITHUB_TOKEN` is unset and `GH_TOKEN` is set
- **THEN** the commit status is sent with the value of `GH_TOKEN`

#### Scenario: Empty token falls to the next
- **WHEN** no app variable is set, `GITHUB_TOKEN` is empty and `GH_TOKEN` is set
- **THEN** the commit status is sent with the value of `GH_TOKEN`

#### Scenario: Empty app id counts as unset
- **WHEN** `PREPUSH_CI_APP_ID` is empty, `PREPUSH_CI_APP_KEY` is unset and `GITHUB_TOKEN` is set
- **THEN** the only request that creates a result is a commit status

#### Scenario: Empty app id with a key
- **WHEN** `PREPUSH_CI_APP_ID` is empty and `PREPUSH_CI_APP_KEY` is set
- **THEN** it exits 1, the reason names `PREPUSH_CI_APP_ID` and no request is sent

#### Scenario: App without a key
- **WHEN** `PREPUSH_CI_APP_ID` is set, `PREPUSH_CI_APP_KEY` is unset and `GITHUB_TOKEN` is set
- **THEN** it exits 1, the reason names `PREPUSH_CI_APP_KEY` and no request is sent

#### Scenario: App without an id
- **WHEN** `PREPUSH_CI_APP_KEY` is set and `PREPUSH_CI_APP_ID` is unset
- **THEN** it exits 1 and the reason names `PREPUSH_CI_APP_ID`

#### Scenario: No credentials
- **WHEN** no app variable, no `GITHUB_TOKEN` and no `GH_TOKEN` is set
- **THEN** it exits 1 and the reason names the app variables and the token variables

### Requirement: A failing app does not become a status
When the app is configured and a step of its authentication or its request fails, `report` SHALL exit 1 and SHALL NOT post a commit status instead, whatever other credentials are set.

#### Scenario: App not installed
- **WHEN** both app variables are set, the installation lookup answers 404 and `GITHUB_TOKEN` is set
- **THEN** it exits 1, the reason says the app is not installed on the repository and no commit status is posted

#### Scenario: Check run rejected
- **WHEN** both app variables are set, the check run request answers 403 and `GITHUB_TOKEN` is set
- **THEN** it exits 1 and no commit status is posted

### Requirement: Authenticating as the app
To post a check run `report` SHALL sign a JSON Web Token with the key in `PREPUSH_CI_APP_KEY` using RS256 through the program `openssl`, with the claims `iss` (the app id), `iat` (60 seconds before now) and `exp` (not more than 10 minutes after now). It SHALL send that token as the bearer credential to `GET /repos/<owner>/<repo>/installation`, request an installation token with `POST /app/installations/<id>/access_tokens`, and create the check run with the installation token only.

#### Scenario: The token is signed with the key
- **WHEN** `report` runs with a generated RSA key and a local server that holds the public key
- **THEN** the server receives a bearer token whose signature verifies against the public key and whose header says RS256

#### Scenario: The token's claims
- **WHEN** the server decodes the bearer token it received
- **THEN** `iss` is the app id, `iat` is in the past and `exp` is not more than 10 minutes after `iat` plus 60 seconds

#### Scenario: The check run is created with the installation token
- **WHEN** the access-token request answers with a token `T`
- **THEN** the check run is created with `T` as the bearer credential and neither the app JWT nor the key is sent to that request

### Requirement: The key stays private and the signer must exist
`report` SHALL NOT write the key into the repository or leave it on disk. Without `--markdown`, when `openssl` cannot be run or rejects the key, `report` SHALL exit 1 and name the program or the key problem, with no request sent.

#### Scenario: The key is not left behind
- **WHEN** `report` has run with an app
- **THEN** no file in the repository or its git directory contains the key, and the temporary directory holds no new file with it

#### Scenario: Key that is not a key
- **WHEN** `PREPUSH_CI_APP_KEY` is `not a key`
- **THEN** it exits 1, the reason says the key cannot be used and no request is sent

#### Scenario: openssl missing
- **WHEN** `openssl` is not on the `PATH`
- **THEN** it exits 1, the reason names `openssl` and no request is sent

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

### Requirement: The summary names what ran
The summary of the check run SHALL be Markdown that names the commit sha and the tree, the `check` command, the `preflight` command (or `none`), every `--tool NAME=VERSION` as `NAME VERSION`, the operating system, the duration when `--duration <seconds>` was given, the coverage when a coverage file was given, and that the result was reported from a session.

#### Scenario: What ran is named
- **WHEN** the config sets `check = "sh scripts/ci"` and `preflight = "test -f ready"` and the check run is created
- **THEN** the summary holds the commit's sha, its tree, `sh scripts/ci` and `test -f ready`

#### Scenario: No preflight
- **WHEN** the config sets no `preflight`
- **THEN** the summary's preflight entry says `none`

#### Scenario: Tools, duration and system
- **WHEN** `report` runs with `--tool ruff=0.14.2 --tool mypy=1.18.2 --duration 492`
- **THEN** the summary holds `ruff 0.14.2`, `mypy 1.18.2`, `8m 12s` and the name of the operating system

#### Scenario: Reported from a session
- **WHEN** the check run is created
- **THEN** the summary says the result was reported from a session

### Requirement: Results are read from standard formats
`--junit <path>`, repeatable, SHALL be read as JUnit XML and counted by test case: a case with a `failure` or `error` child is failed, one with a `skipped` child is skipped, every other case is passed, whatever the nesting of the suites. The counts of all files SHALL be added. `--coverage <path>` SHALL be read as the `coverage.json` of coverage.py, and the summary SHALL show its `totals.percent_covered_display`.

#### Scenario: pytest file
- **WHEN** a JUnit file from pytest has one passed, one failed, one skipped and one setup-error case
- **THEN** the counts are 1 passed, 2 failed and 1 skipped

#### Scenario: node file
- **WHEN** a JUnit file from `node --test` has nested suites with 1 passed, 1 failed and 1 skipped case
- **THEN** the counts are 1 passed, 1 failed and 1 skipped

#### Scenario: Several files
- **WHEN** two JUnit files with 2 and 3 passing cases are given
- **THEN** the counts are 5 passed

### Requirement: Input that cannot be trusted is refused
A file that does not exist or does not have the format SHALL make `report` exit 1 and name the file, with no request sent. A `passed` result with a failing test case in the files SHALL be refused.

#### Scenario: Missing file
- **WHEN** `--junit` names a file that does not exist
- **THEN** it exits 1, the reason names the file and no request is sent

#### Scenario: Not JUnit
- **WHEN** `--junit` names a file of plain text
- **THEN** it exits 1, the reason names the file and no request is sent

#### Scenario: Not coverage
- **WHEN** `--coverage` names a JSON file without `totals`
- **THEN** it exits 1 and the reason names the file

#### Scenario: Passed with a failing test
- **WHEN** `--result passed` is given with a JUnit file that has a failing case
- **THEN** it exits 1, the reason says the result contradicts the file and no request is sent

#### Scenario: Failed without a failing test
- **WHEN** `--result failed` is given with a JUnit file that has only passing cases
- **THEN** the check run is created with `conclusion` `failure`

### Requirement: Without an app the result is a commit status
Without `--markdown` and without an app, `report` SHALL create a commit status for the sha with `state` `success` for `passed` and `failure` for `failed`, the `context` given by `--name` or `prepush-ci/full`, and a one-line `description` made of the counts when a JUnit file was given, the coverage when a coverage file was given, the first 7 characters of the tree and `(reported from a session)`.

#### Scenario: Green status
- **WHEN** `report --result passed` runs without an app, with a JUnit file of 3 passing cases and a coverage file of 94.5%
- **THEN** the status has `state` `success`, `context` `prepush-ci/full` and a description with `3 passed`, `94.5%`, the first 7 characters of the tree and `reported from a session`

#### Scenario: Red status
- **WHEN** `report --result failed` runs without an app
- **THEN** the status has `state` `failure`

#### Scenario: Chosen context
- **WHEN** `--name unit` is given without an app
- **THEN** the status has `context` `unit`

#### Scenario: Description without files
- **WHEN** `report --result passed` runs without an app and without a JUnit or a coverage file
- **THEN** the description holds the first 7 characters of the tree and `reported from a session`, and no counts

### Requirement: An answer of the API that is not success fails the command
When a request of `report` is answered with a status of 300 or more (a redirect is never followed, so no request is repeated, as another method or to another host), or cannot be sent, `report` SHALL exit 1 and print on standard error the status code and the message GitHub gave, or the reason the request could not be sent. Neither standard output nor standard error SHALL ever hold the value of a token, of `PREPUSH_CI_APP_KEY`, of a JSON Web Token or the userinfo of a remote URL.

#### Scenario: Rejected request
- **WHEN** the API answers the status request with 422 and a message
- **THEN** it exits 1 and the error names `422` and the message

#### Scenario: Server unreachable
- **WHEN** `GITHUB_API_URL` is the address of a port nobody listens on
- **THEN** it exits 1 and the error says the request could not be sent

#### Scenario: Redirect refused
- **WHEN** the API answers the status request, or the installation lookup of an app, with 301 and a `Location` naming another server
- **THEN** it exits 1, the error names `301`, no request is repeated and the other server receives no request

#### Scenario: Secrets stay out of the output
- **WHEN** the API answers 401 with a body that quotes the request's bearer token, in a run with an app and in a run with `GITHUB_TOKEN`
- **THEN** the token, the key and the JSON Web Token appear in neither standard output nor standard error

#### Scenario: Userinfo of the remote stays out of the output
- **WHEN** `origin` is `https://x-access-token:s3cret@git.example.test/acme/widgets.git`, `GITHUB_API_URL` and `GITHUB_REPOSITORY` are unset and `report` refuses
- **THEN** `s3cret` appears in neither standard output nor standard error

### Requirement: A pipe in a value stays in its cell
Every `|` in a value of the facts table of the summary SHALL be written `\|`, so that GitHub shows the whole value in its cell, also when the value is a code span. A value without a `|` SHALL be written as before.

#### Scenario: Pipe in the check
- **WHEN** the config sets `check = "sh scripts/ci | tee ci.log"` and the check run is created
- **THEN** the row `Check` of the summary has the value `` ` sh scripts/ci \| tee ci.log ` `` and no `|` in it that is not preceded by a backslash

#### Scenario: Pipe in the preflight
- **WHEN** the config sets `preflight = "make lint | cat"` and the check run is created
- **THEN** the row `Preflight` of the summary has the value `` ` make lint \| cat ` ``

#### Scenario: Pipe in a tool name
- **WHEN** `report` runs with `--tool 'a|b=1.0'`
- **THEN** the row `Tools` of the summary has the value `a\|b 1.0`

#### Scenario: Backslash before a pipe in the check
- **WHEN** the config sets `check = 'echo \| cat'` and the check run is created
- **THEN** the row `Check` of the summary has the value `` ` echo \\| cat ` ``

#### Scenario: No pipe
- **WHEN** the config sets `check = "sh scripts/ci"` and the check run is created
- **THEN** the row `Check` of the summary has the value `` ` sh scripts/ci ` ``

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
With an app and without `--markdown`, `report --result` SHALL look up the check runs of the sha with the run's name, the status `in_progress` and the app's id (`GET /repos/<owner>/<repo>/commits/<sha>/check-runs?check_name=<name>&status=in_progress&app_id=<id>`). When it finds one it SHALL complete that run with `PATCH /repos/<owner>/<repo>/check-runs/<id>` and create no other. When it finds none it SHALL create the check run. When several are found it SHALL complete the one with the highest id.

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
With an app and without `--markdown`, each failure SHALL become one annotation with the `path` of its file, `start_line` and `end_line` both its line, `annotation_level` `failure`, a `title` naming the tool (`pytest`, `ruff` or `mypy`) and a `message`. Without an app the failure files SHALL be read and checked, not posted.

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
Without `--markdown`, `report` SHALL send the annotations in requests of at most 50 each, in the order of the files given: the request that creates or completes the check run carries the first 50 and each following `PATCH` of the same run the next 50 with the same `output` title and summary. Every annotation SHALL arrive exactly once. When a request fails, `report` SHALL exit 1 and send no further request.

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

### Requirement: Report prints the result as Markdown
`prepush-ci report --markdown --result passed|failed --tree <hash>` SHALL print the Markdown of the result on standard output and exit 0, and SHALL post nothing: it needs no token, no app, no remote `origin` and no network, and sends no request whatever the environment holds. Standard output SHALL hold the Markdown and nothing else.

#### Scenario: Printed without credentials
- **WHEN** the commit's config sets `check = "sh scripts/ci"` and `report --markdown --result passed --tree <the tree of HEAD>` runs in a repository without a remote, with no `GITHUB_TOKEN`, `GH_TOKEN`, `PREPUSH_CI_APP_ID` or `PREPUSH_CI_APP_KEY`
- **THEN** it exits 0 and standard output holds the sha of `HEAD`, the `check` command of the commit's config and `sh scripts/ci` as the check

#### Scenario: Nothing is sent
- **WHEN** `GITHUB_API_URL` names a local server that records requests, a token is set, and `report --markdown --result passed --tree <the tree of HEAD>` runs
- **THEN** it exits 0 and the server received no request

### Requirement: The Markdown reads the inputs of a result
`report --markdown` SHALL take the inputs of `report --result` (`--commit`, `--name`, `--duration`, `--tool`, `--junit`, `--coverage`, `--ruff`, `--mypy`) and refuse what `report` refuses for them, with the same exit status and nothing on standard output, so that the text never shows a state the session did not check. It sends no annotations.

#### Scenario: A tree that is not the commit's
- **WHEN** `--tree` is the tree of another commit
- **THEN** it exits 1, the reason names both hashes and standard output is empty

#### Scenario: Inputs are read
- **WHEN** `report --markdown --result failed` runs with `--junit` of a file with 2 failing cases
- **THEN** the Markdown has `2 failed` and lists the two cases

### Requirement: The Markdown is the check run's summary under a marker
The Markdown SHALL be three consecutive lines, a blank line, and the summary of the check run unchanged (so that the failures come first in it as for a red check run). The lines are `<!-- prepush-ci:<name> -->`, `<name>` being `--name` or `prepush-ci / full`; a title line that holds the name and the title of the check run (the test counts, or `Passed` or `Failed`); and a line that names the full sha of the commit it reports.

#### Scenario: Default marker
- **WHEN** `report --markdown` runs without `--name`
- **THEN** the first line is `<!-- prepush-ci:prepush-ci / full -->`

#### Scenario: Chosen name
- **WHEN** `--name "prepush-ci / unit"` is given
- **THEN** the first line is `<!-- prepush-ci:prepush-ci / unit -->` and the title line holds `prepush-ci / unit`

#### Scenario: The commit is named
- **WHEN** `report --markdown --commit <an earlier commit>` runs with that commit's tree
- **THEN** the third line holds the 40-hex sha of that commit and not the sha of `HEAD`

#### Scenario: The summary is the check run's
- **WHEN** `report --markdown --result passed` runs with a JUnit file of 3 passing cases and a coverage file of 94.5%
- **THEN** the Markdown holds the summary that the check run of the same inputs would hold, with `3 passed` in the title line and `94.5%` in it

#### Scenario: Failures first
- **WHEN** `report --markdown --result failed` runs with a mypy file with one error
- **THEN** the mypy error comes before the row `Check` of the table

### Requirement: The Markdown takes no start and no name that breaks the marker
`--markdown` SHALL NOT be combined with `--start`, and a `--name` that holds `--` or a line break SHALL be refused with `--markdown`, because it would end the hidden marker early. A refusal SHALL exit 2, name the flag and print nothing on standard output. Without `--markdown`, such a name SHALL stay valid.

#### Scenario: With start
- **WHEN** `--markdown --start --tree <hash>` is given
- **THEN** it exits 2, the reason names `--markdown` and `--start` and standard output is empty

#### Scenario: A name that closes the marker
- **WHEN** `report --markdown --result passed --name "a-->b"` is given
- **THEN** it exits 2, the reason names `--name` and standard output is empty

#### Scenario: A name with a line break
- **WHEN** `--name` holds a line break and `--markdown` is given
- **THEN** it exits 2 and the reason names `--name`

#### Scenario: The same name posted
- **WHEN** `report --result passed --name "a-->b"` runs with a token and a stub API, without `--markdown`
- **THEN** it exits 0 and the status has the context `a-->b`

### Requirement: A mypy message is read from its first line
The message of a `--mypy` error SHALL be the text after `error:` on that line alone. The lines that follow it (the rest of a message that `mypy --pretty` wrapped, the source line, the caret line) SHALL yield no annotation and no part of the message. The README SHALL advise running mypy without `--pretty` for `report`.

#### Scenario: A wrapped message
- **WHEN** a mypy file holds `src/m.py:1:10: error: Incompatible types in assignment (expression has type`, the line `"str", variable has type "int")  [assignment]`, a source line, a caret line and `Found 1 error in 1 file (checked 1 source file)`
- **THEN** the check run has exactly one annotation, on line 1 of `src/m.py`, whose message is `Incompatible types in assignment (expression has type` and holds nothing of the following lines

#### Scenario: The README advises it
- **WHEN** the reference of `report` in the README is read
- **THEN** it advises running mypy without `--pretty` for `report`
