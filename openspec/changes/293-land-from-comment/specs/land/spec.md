## MODIFIED Requirements

### Requirement: The tree must have a pass for the configured check
`land` SHALL push only when it finds a pass for the head's tree under the key the pre-push hook computes on that commit (the config committed in the head and the output of its `preflight`): in the clone first, then on `origin`, as a push does; else in a pull request comment. It SHALL NOT run the check. Without a pass it SHALL push nothing and print a `not landed:` line naming the first twelve characters of the tree and saying no pass was found, or that the cache is off with `cache = false`.

#### Scenario: A result in the clone
- **WHEN** the clone holds the result ref of the head's tree and key
- **THEN** it lands

#### Scenario: A result only on origin
- **WHEN** a fresh clone holds no result and `origin` holds the ref of the head's tree and key
- **THEN** it lands

#### Scenario: No result
- **WHEN** neither the clone nor `origin` holds a result for the head's tree, and no comment of the pull request is a pass
- **THEN** it exits 1, the line names the first twelve characters of the tree and says no pass was found, and nothing is pushed

#### Scenario: The check changed since the pass
- **WHEN** the result was made with another `check` than the one committed in the head
- **THEN** it exits 1 as for no result

#### Scenario: The check does not run
- **WHEN** the check of the config writes a file and `land` runs, with or without a result
- **THEN** the file does not exist

#### Scenario: The cache is off
- **WHEN** the config committed in the head sets `cache = false`
- **THEN** it exits 1 and the line says the cache is off

## ADDED Requirements

### Requirement: A comment of the pull request is a pass when no result is found
When neither the clone nor `origin` holds a result for the head's tree, `land` SHALL read the comments of the pull request (`GET /repos/<owner>/<repo>/issues/<number>/comments?per_page=100&page=<n>`, from page 1 while a page holds 100 comments) and SHALL take the first comment that states a pass (next requirement) and was written by someone with write access (the one after). A result ref SHALL win: when one is found, no comment is read. `land` SHALL write no comment and create no ref from one.

#### Scenario: A comment of a session is a pass
- **WHEN** `origin` holds no result ref, the pull request has the comment `report --markdown --result passed` printed for the head's tree, written by a user with write access, and `prepush-ci land 7` runs
- **THEN** it exits 0 and prints `landed: <sha> on main`

#### Scenario: A result ref wins
- **WHEN** `origin` holds the result ref of the head's tree and the API stub records requests
- **THEN** it lands and the stub received no request

#### Scenario: The comment is past the first page
- **WHEN** the first page of comments holds 100 comments that are no pass and the second holds one that is
- **THEN** it lands

#### Scenario: Nothing is written
- **WHEN** a landing succeeds on the strength of a comment
- **THEN** the stub received only `GET` requests and the clone and `origin` hold no new result ref

### Requirement: A comment states a pass
A comment SHALL state a pass when its first line is `<!-- prepush-ci:prepush-ci / full -->`, its title line is `### prepush-ci / full: Passed` or `### prepush-ci / full: <n> passed, 0 failed, <m> skipped`, and no line of it is `### Failures`.

#### Scenario: A failed result is not a pass
- **WHEN** the comment is the Markdown of `report --markdown --result failed` for the head's tree, with `--junit` of a file whose cases all passed, or with none
- **THEN** it exits 1 as for no pass

#### Scenario: A pass with failing cases is not a pass
- **WHEN** the title line of the comment is `### prepush-ci / full: 3 passed, 1 failed, 0 skipped`
- **THEN** it exits 1 as for no pass

#### Scenario: Failed with no failed case is not a pass
- **WHEN** the title line of the comment is `### prepush-ci / full: Failed (3 passed, 0 failed, 0 skipped)`
- **THEN** it exits 1 as for no pass

#### Scenario: A comment with a failures section is not a pass
- **WHEN** a comment with the title line `### prepush-ci / full: Passed` also holds the line `### Failures`
- **THEN** it exits 1 as for no pass

#### Scenario: A title of another name
- **WHEN** a comment starts with the default marker and its title line is `### prepush-ci / unit: Passed`
- **THEN** it exits 1 as for no pass

#### Scenario: Another check's comment
- **WHEN** the only comment starts with `<!-- prepush-ci:prepush-ci / unit -->` and names the head's tree
- **THEN** it exits 1 as for no pass

#### Scenario: The marker in the middle of a comment
- **WHEN** a comment holds the marker line after other text, and names the head's tree
- **THEN** it does not count

### Requirement: A comment names this tree, check and preflight
A passing comment SHALL count only when its `Tree` row holds the head's tree as a code span, and its `Check` and `Preflight` cells are, cell for cell, what `report --markdown` writes for the `check` and `preflight` committed in the head (`none` for no preflight), escaping included. It names the preflight command, not what it printed: it SHALL count whatever the preflight printed.

#### Scenario: A comment of another tree
- **WHEN** the only comment names a tree other than the head's, for example the tree of the commit before it
- **THEN** it exits 1, the line says no pass was found and nothing is pushed

#### Scenario: A comment of another check
- **WHEN** the comment names a `Check` other than the one committed in the head, or a `Preflight` other than the committed one
- **THEN** it exits 1 as for no pass

#### Scenario: A check with a pipe and a backtick
- **WHEN** the config committed in the head has ``check = "sh scripts/ci | tee ci.log && echo `x`"`` and the comment is the Markdown that `report --markdown --result passed` printed for it
- **THEN** it lands

#### Scenario: The preflight printed something else
- **WHEN** the config sets a `preflight` that prints a different text than it printed in the session, so that no result ref matches, and the comment names that `preflight` and the head's tree
- **THEN** it lands

### Requirement: Only a comment of someone with write access counts
A comment SHALL count only when its author has write access to the repository: `GET /repos/<owner>/<repo>/collaborators/<login>/permission` answers `permission` `admin` or `write`. Any other permission, and an author whose permission cannot be read (the answer is an error, or not what the API documents), SHALL mean the comment does not count. `land` SHALL ask only about the author of a comment that already matches the rest, once per author.

#### Scenario: A writer
- **WHEN** the author's permission is `write`, or `admin`
- **THEN** the comment counts

#### Scenario: Someone who cannot write
- **WHEN** the author's permission is `read` or `none`, and no other comment is a pass
- **THEN** it exits 1 as for no pass

#### Scenario: A permission that cannot be read
- **WHEN** the permission request answers 404
- **THEN** the comment does not count and it exits 1 as for no pass

#### Scenario: A reader's comment beside a writer's
- **WHEN** one matching comment is by a user with `read` permission and a later one is by a user with `write` permission
- **THEN** it lands

#### Scenario: Only matching comments are asked about
- **WHEN** the pull request has a comment by a user that names another tree
- **THEN** the stub received no permission request for that user

### Requirement: A comment of an App does not count
A comment whose `user.type` is `Bot` (a GitHub App) SHALL NOT count, whatever the permission of its login, and `land` SHALL send no permission request for it.

#### Scenario: A comment of an App
- **WHEN** the author's `user.type` is `Bot` (`acme-ci[bot]`) and the stub would answer `write` to its permission request
- **THEN** it exits 1 as for no pass and the stub received no permission request for it

### Requirement: The comments are read as report reaches GitHub
`land` SHALL read the comments with the token in `GITHUB_TOKEN` or, when it is unset or empty, in `GH_TOKEN`, from the repository `origin` names or, when it names none, `GITHUB_REPOSITORY`, at `GITHUB_API_URL` or `https://api.github.com`, found as `report` finds them. A cache that is off SHALL read no comment.

#### Scenario: Repository from the environment
- **WHEN** `origin` is a local path, `GITHUB_REPOSITORY` is `acme/widgets` and the API stub holds a comment that is a pass
- **THEN** the comments request is for `/repos/acme/widgets/issues/7/comments` and it lands

#### Scenario: The cache is off
- **WHEN** the config committed in the head sets `cache = false`
- **THEN** no request is sent and the line says the cache is off

### Requirement: A comment that cannot be read is not a pass
When there is no token, no repository can be read, or the API answers an error or something it does not document, `land` SHALL treat the comment as no pass, and the `not landed:` line SHALL add the reason after the words that say no pass was found, and never hold the token.

#### Scenario: No token
- **WHEN** no result is found and neither `GITHUB_TOKEN` nor `GH_TOKEN` is set
- **THEN** it exits 1, the line says no pass was found and names `GITHUB_TOKEN`, and the stub received no request

#### Scenario: No repository
- **WHEN** `origin` is a local path, `GITHUB_REPOSITORY` is unset and a token is set
- **THEN** it exits 1 and the line says no repository could be read from `origin`

#### Scenario: The API fails
- **WHEN** the stub answers the comments request with 500
- **THEN** it exits 1, the line holds `500` and nothing is pushed

#### Scenario: The token stays secret
- **WHEN** the stub answers 401 to a request that carried the token `s3cret`
- **THEN** neither standard output nor standard error holds `s3cret`
