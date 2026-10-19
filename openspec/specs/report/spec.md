# report Specification

## Purpose
`prepush-ci report`: posts the result of a run of the check, made in a session or on a machine, for a commit, as a check run through the team's GitHub App or, without an app, as a commit status. It refuses a tree that is not the commit's tree, runs nothing itself, and names in the check run what ran.

## Requirements

### Requirement: Report posts the result of a run
`prepush-ci report --result passed|failed --tree <hash>` SHALL, from any directory inside a worktree, post the result of a run of the check for the commit named by `--commit` (default `HEAD`), as the next requirements say. It SHALL print one line on standard output that names the full sha of the commit, the result and how it was posted (`check run` or `commit status`).

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

### Requirement: The exit status says whether the result was posted
`report` SHALL exit 0 when the result was posted, 2 when the command line is rejected (a missing or unknown flag, a malformed value) and 1 in every other case, and a refusal SHALL send no request.

#### Scenario: Result missing or unknown
- **WHEN** `--result` is missing or is neither `passed` nor `failed`
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
`report` SHALL post to the GitHub repository named by the URL of the remote `origin` as `git remote get-url origin` prints it, in the forms `https://[<userinfo>@]<host>/<owner>/<repo>[.git]`, `ssh://[<user>@]<host>[:<port>]/<owner>/<repo>[.git]` and `git@<host>:<owner>/<repo>[.git]`, with `github.com` or `ssh.github.com` as `<host>`; the userinfo SHALL be ignored. When no repository can be read from `origin`, the environment SHALL name it (next requirement).

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
When no repository can be read from `origin`, `GITHUB_REPOSITORY` SHALL name it, in the form `<owner>/<repo>`; an empty value counts as unset. When neither names a repository, or the value is not of that form, `report` SHALL exit 1 and send no request, and the reason SHALL name `GITHUB_REPOSITORY` when it was the one at fault.

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
`report` SHALL send its requests to the address in `GITHUB_API_URL` or, when it is unset or empty, to `https://api.github.com`. A host other than `github.com` or `ssh.github.com` in the URL of `origin` SHALL count only when `GITHUB_API_URL` is set and non-empty.

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
An empty variable SHALL count as unset. With `PREPUSH_CI_APP_ID` and `PREPUSH_CI_APP_KEY` set, `report` SHALL post a check run as the app. With neither set and `GITHUB_TOKEN` or `GH_TOKEN` set (`GITHUB_TOKEN` first), it SHALL post a commit status with that token. With only one of the two app variables set, or with no credentials at all, it SHALL exit 1 and send no request, and the reason SHALL name what is missing.

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
`report` SHALL NOT write the key into the repository or leave it on disk. When `openssl` cannot be run or rejects the key, `report` SHALL exit 1 and name the program or the key problem, with no request sent.

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
The check run SHALL be created for the sha of the commit with the name given by `--name` or `prepush-ci / full`, `status` `completed` and `conclusion` `success` for `passed` and `failure` for `failed`. Its title SHALL be the test counts when a JUnit file was given and `Passed` or `Failed` otherwise.

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
Without an app, `report` SHALL create a commit status for the sha with `state` `success` for `passed` and `failure` for `failed`, the `context` given by `--name` or `prepush-ci/full`, and a one-line `description` made of the counts when a JUnit file was given, the coverage when a coverage file was given, the first 7 characters of the tree and `(reported from a session)`.

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
