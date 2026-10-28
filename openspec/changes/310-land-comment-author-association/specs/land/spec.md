## MODIFIED Requirements

### Requirement: A comment of the pull request is a pass when no result is found
When neither the clone nor `origin` holds a result for the head's tree, `land` SHALL read the pull request's comments (`GET /repos/<owner>/<repo>/issues/<number>/comments?per_page=100&page=<n>`, as "The comments are walked in order until one counts" says) and take the first that states a pass ("A comment states a pass") and is by a writer ("Only a comment of someone with write access counts"). A found result ref SHALL leave every comment unread. It SHALL write no comment and no ref from one.

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

### Requirement: Only a comment of someone with write access counts
A comment SHALL count only when its author has write access: the author is the token's own user who may push ("A comment of the token's own user counts without a lookup"), or `GET /repos/<owner>/<repo>/collaborators/<login>/permission` answers `permission` `admin` or `write`; any other answer to it, errors included, SHALL mean no write access. `land` SHALL send that request once per author, only for a matching comment the walk reaches ("The comments are walked in order until one counts").

#### Scenario: A writer
- **WHEN** the author is not the token's user and the author's permission is `write`, or `admin`
- **THEN** the comment counts

#### Scenario: Someone who cannot write
- **WHEN** the author is not the token's user, the author's permission is `read` or `none`, and no other comment is a pass
- **THEN** it exits 1 as for no pass

#### Scenario: A permission that cannot be read
- **WHEN** the permission request answers 404, and the author is not the token's user
- **THEN** the comment does not count and it exits 1 as for no pass

#### Scenario: A permission the API does not document
- **WHEN** the author is not the token's user, the permission request answers `permission` `maintain`, and no other comment is a pass
- **THEN** it exits 1 as for no pass

#### Scenario: A reader's comment beside a writer's
- **WHEN** one matching comment is by a user with `read` permission and a later one is by a user with `write` permission
- **THEN** it lands

#### Scenario: Only matching comments are asked about
- **WHEN** the pull request has a comment by a user that names another tree
- **THEN** the stub received no permission request for that user

#### Scenario: A comment that does not match sends no request
- **WHEN** the only comment, by `alice`, names another tree
- **THEN** it exits 1 as for no pass and the stub received only the comments listing

### Requirement: A comment that cannot be read is not a pass
When there is no token, no repository can be read, or the comments listing or a permission request answers an error or something the API does not document, `land` SHALL treat the comment as no pass, and the `not landed:` line SHALL add the reason after the words that say no pass was found, and never hold the token. An error or such an answer of `GET /user` or `GET /repos/<owner>/<repo>` SHALL add no reason: it only leaves the author to the permission request.

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

#### Scenario: A token user that cannot be read adds no reason
- **WHEN** the stub answers `/user` with 500, and the only matching comment is by `alice`, whose permission is `read`
- **THEN** it exits 1, the line says no pass was found and does not hold `500`

#### Scenario: A repository that cannot be read adds no reason
- **WHEN** the stub answers `/user` with `alice` and the repository with 500, and the only matching comment is by `alice`, whose permission is `read`
- **THEN** it exits 1, the line says no pass was found and does not hold `500`, and the stub received one permission request, for `alice`

## ADDED Requirements

### Requirement: A comment of the token's own user counts without a lookup
For each matching comment the walk reaches whose author is known and not an App, `land` SHALL compare its author with the `login` of `GET /user`, asked once per run at the first such comment. At the first such comment by that login, `land` SHALL ask `GET /repos/<owner>/<repo>` once per run; when it answers `permissions.push` `true`, the comment SHALL count with no permission request. An error, an undocumented answer, or `push` not `true` SHALL leave the author to the permission request.

#### Scenario: The proxy refuses the permission path
- **WHEN** the stub answers every `collaborators/<login>/permission` request with 403 and the message `Access to this GitHub API path is not permitted through this proxy.`, answers `/user` with the login `alice` and the repository with `permissions.push` `true`, and the only matching comment is by `alice`, served with `author_association` `MEMBER`
- **THEN** it exits 0, prints `landed: <sha> on main`, and the stub received no permission request

#### Scenario: Another user's comment through the proxy
- **WHEN** the stub refuses the permission path with 403 as the proxy does, answers `/user` with `alice`, and the only matching comment is by `bob`, served with `author_association` `OWNER`
- **THEN** it exits 1 as for no pass, the `not landed:` line holds `403`, and the stub received no request for the repository

#### Scenario: The token's user cannot push
- **WHEN** the stub refuses the permission path with 403, answers `/user` with `alice` and the repository with `permissions.push` `false`, and the only matching comment is by `alice`
- **THEN** it exits 1 as for no pass

#### Scenario: The repository answers without permissions
- **WHEN** the stub answers `/user` with `alice` and the repository with an object that has no `permissions`, and the only matching comment is by `alice`, whose permission is `write`
- **THEN** it lands, and the stub received one permission request, for `alice`

#### Scenario: The token's user after another author
- **WHEN** the stub refuses the permission path with 403, answers `/user` with `alice` and the repository with `permissions.push` `true`, and the first matching comment is by `bob` and a later one by `alice`
- **THEN** it lands, the stub received one `/user` request and one repository request, and standard error holds `ignored a pass by bob: its permission cannot be read`

#### Scenario: The repository is asked once
- **WHEN** the stub refuses the permission path with 403, answers `/user` with `alice` and the repository with `permissions.push` `false`, and two matching comments are by `alice`
- **THEN** it exits 1 as for no pass, the stub received one `/user` request, one repository request and one permission request, for `alice`, and standard error holds the line for `alice` once

#### Scenario: The token's user cannot be read
- **WHEN** the stub answers `/user` with 403, or with an object without `login`, the first matching comment is by `bob`, whose permission is `read`, and a later one by `alice`, whose permission is `write`
- **THEN** it lands, and the stub received one `/user` request, no request for the repository, and one permission request each for `bob` and `alice`

#### Scenario: The token's user is asked once
- **WHEN** two matching comments are by `mallory` and `bob`, the stub answers `/user` with `alice` and both permission requests with `read`
- **THEN** it exits 1 as for no pass and the stub received one `/user` request and no request for the repository

### Requirement: A comment of an unknown author does not count
A comment whose `user` is `null`, or whose `user.login` is a string that is empty or holds a character other than ASCII letters, digits, `-`, `_`, `[` and `]`, SHALL be by an unknown author: it SHALL NOT count, and `land` SHALL send no request about it. A `user` that is neither `null` nor an object with a string `login` and a string `type` SHALL make its page of the comments listing an answer the API does not document.

#### Scenario: A comment without a user
- **WHEN** the only matching comment has `user` `null`
- **THEN** it exits 1 as for no pass and the stub received only the comments listing

#### Scenario: A login that is not plain
- **WHEN** the only matching comment's `login` is empty, or holds a newline (`"alice\nignored a pass by bob"` in the JSON), and the stub would answer `write` to any permission request
- **THEN** it exits 1 as for no pass and the stub received only the comments listing

#### Scenario: An author the API does not document
- **WHEN** a comment's `user` is the string `alice`, an object without `login`, an object without `type`, an object whose `login` is the number `3`, or an object whose `type` is the number `3`
- **THEN** it exits 1 and the line says the answer is not what the API documents

### Requirement: An ignored pass is named
For each author of a matching comment (a pass for this tree, check and preflight) that the walk reaches and that does not count, `land` SHALL print once on standard error `ignored a pass by <login>: <reason>`, the reason `a GitHub App`, `permission <value> is not admin or write` (`<value>` `read` or `none`) or `its permission cannot be read`; for all unknown authors, once, `ignored a pass by an unknown author`. No other comment SHALL print a line; standard output SHALL keep its one line.

#### Scenario: A reader's pass is named
- **WHEN** the only matching comment is by `mallory`, who is not the token's user and whose permission is `read`
- **THEN** it exits 1, standard output is the one `not landed:` line and standard error holds `ignored a pass by mallory: permission read is not admin or write`

#### Scenario: A pass whose permission cannot be read is named
- **WHEN** the stub refuses the permission path with 403, answers `/user` with `alice`, and the only matching comment is by `bob`
- **THEN** standard error holds `ignored a pass by bob: its permission cannot be read`

#### Scenario: An undocumented permission is not printed
- **WHEN** the only matching comment is by `mallory`, who is not the token's user and whose permission request answers `permission` `maintain`
- **THEN** standard error holds `ignored a pass by mallory: its permission cannot be read` and does not hold `maintain`

#### Scenario: An App's pass is named
- **WHEN** the only matching comment is by `acme-ci[bot]`, whose `user.type` is `Bot`
- **THEN** standard error holds `ignored a pass by acme-ci[bot]: a GitHub App` and the stub received only the comments listing

#### Scenario: Unknown authors are named once
- **WHEN** one matching comment has `user` `null` and another's `login` is `"alice\nignored a pass by bob"` in the JSON
- **THEN** it exits 1, standard error holds the line `ignored a pass by an unknown author` once and no line that starts with `ignored a pass by bob`

#### Scenario: Once per author
- **WHEN** two matching comments are by `mallory`, who is not the token's user and whose permission is `read`
- **THEN** standard error holds the line for `mallory` once

#### Scenario: The ignored pass is named before a landing
- **WHEN** one matching comment is by `mallory`, who is not the token's user, with `read` permission and a later one is by `alice` with `write`
- **THEN** it lands, standard output is the one `landed:` line and standard error holds the line for `mallory`

#### Scenario: A comment that does not match is not named
- **WHEN** the only comment by `mallory`, whose permission is `read`, is a pass for another tree
- **THEN** standard error holds no line that starts with `ignored a pass`

### Requirement: The comments are walked in order until one counts
`land` SHALL walk the comments in the order the listing gives them, from page 1, reading the next page only while the last one held 100 comments and none of them counted. The walk SHALL end at the first comment that counts: no request SHALL be sent and no line printed for a comment after it. A page that cannot be read ("A comment that cannot be read is not a pass"), a page with a `user` the API does not document among them, SHALL end the walk before its first comment, with no pass.

#### Scenario: A later page is not read
- **WHEN** the first page holds 100 comments and its first is a pass by a writer
- **THEN** it lands and the stub received one request for the comments listing

#### Scenario: A writer's comment before a reader's
- **WHEN** neither author is the token's user, one matching comment is by `alice` with `write` permission and a later one is by `mallory` with `read` permission
- **THEN** it lands, the stub received one permission request, for `alice`, and standard error holds no line that starts with `ignored a pass`

#### Scenario: A writer's comment before the token's user's
- **WHEN** the stub answers `/user` with `alice` and the repository with `permissions.push` `true`, and the first matching comment is by `bob`, whose permission is `write`, and a later one by `alice`
- **THEN** it lands, and the stub received one `/user` request, no request for the repository and one permission request, for `bob`

#### Scenario: Nothing after the token's user's pass is asked about
- **WHEN** the stub answers `/user` with `alice` and the repository with `permissions.push` `true`, and the first matching comment is by `alice` and a later one by `mallory`
- **THEN** it lands, the stub received no permission request, and standard error holds no line that starts with `ignored a pass`

#### Scenario: A page the API does not document ends the walk
- **WHEN** the first matching comment is by `alice`, whose permission is `write`, and a later comment on the same page has `user` the string `bob`
- **THEN** it exits 1, the line says the answer is not what the API documents, the stub received only the comments listing, and standard error holds no line that starts with `ignored a pass`
