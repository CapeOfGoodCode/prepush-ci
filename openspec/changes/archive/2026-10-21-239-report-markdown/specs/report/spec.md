## MODIFIED Requirements

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

## ADDED Requirements

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
