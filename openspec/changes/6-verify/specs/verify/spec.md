## ADDED Requirements

### Requirement: Verified commit
`prepush-ci verify <sha>` SHALL exit 0 when the commit `<sha>` carries a demanding trailer and was not made by a server, and SHALL otherwise exit 1. It SHALL print exactly one line on standard output: `verified: <sha> <reason>` or `not verified: <sha> <reason>`, where `<sha>` is the full 40-hex sha of the commit and the reason names the trailer found or why none counts. When the argument does not resolve to a commit, `<sha>` SHALL be the argument as given. No other outcome SHALL exit 0.

#### Scenario: Commit with the trailer
- **WHEN** `HEAD` is a commit made with `PREPUSH_CI=full` and `prepush-ci verify HEAD` runs
- **THEN** it exits 0 and prints one line starting with `verified:` that names `Prepush-CI: full`

#### Scenario: Commit without the trailer
- **WHEN** `HEAD` is a commit without a trailer and `prepush-ci verify HEAD` runs
- **THEN** it exits 1 and prints one line starting with `not verified:` that says there is no trailer

#### Scenario: Full sha given
- **WHEN** `prepush-ci verify` runs with the full sha of a commit with the trailer
- **THEN** it exits 0 and the printed line is `verified: ` followed by that full 40-hex sha

#### Scenario: Abbreviated sha given
- **WHEN** `prepush-ci verify` runs with a 7-character abbreviation of the sha of a commit with the trailer
- **THEN** it exits 0 and the printed line holds the full 40-hex sha, not the abbreviation

#### Scenario: Revision name given
- **WHEN** `prepush-ci verify HEAD` runs on a commit with the trailer
- **THEN** the printed line holds the full 40-hex sha of `HEAD`

### Requirement: The trailer rule of the pre-push hook
A commit SHALL carry a demanding trailer when its message has a trailer whose key equals `trailer.key` or one of `legacy_keys`, compared case-insensitively, whatever the value. The trailers SHALL be read as `git log` shows them (`git log -1 --format=%(trailers:only,unfold)`), so a `---` line in the message does not hide them.

#### Scenario: Key in another case
- **WHEN** the commit carries `prepush-ci: full`
- **THEN** it verifies

#### Scenario: Any value
- **WHEN** the commit carries `Prepush-CI: off`
- **THEN** it verifies and the reason names the trailer

#### Scenario: Configured key
- **WHEN** the config committed in the commit sets `trailer = { key = "Full-Check", value = "yes" }` and the commit carries `Full-Check: yes`
- **THEN** it verifies

#### Scenario: Default key under a configured key
- **WHEN** the config committed in the commit sets `trailer = { key = "Full-Check", value = "yes" }` and the commit carries only `Prepush-CI: full`
- **THEN** it does not verify

#### Scenario: Legacy key
- **WHEN** the config committed in the commit sets `legacy_keys = ["Full-Pre-Push"]` and the commit carries `Full-Pre-Push: required`
- **THEN** it verifies and the reason names `Full-Pre-Push`

#### Scenario: Trailer behind a divider line
- **WHEN** the message has a `---` line in its body and `Prepush-CI: full` in its last paragraph
- **THEN** it verifies

#### Scenario: Trailer text in the body
- **WHEN** the message has `Prepush-CI: full` in its body but not in its last paragraph
- **THEN** it does not verify

### Requirement: Only the given commit counts
Trailers on the commit's ancestors SHALL NOT make it verify.

#### Scenario: Trailer on the parent only
- **WHEN** the parent carries `Prepush-CI: full` and the commit does not
- **THEN** `prepush-ci verify` for the commit exits 1

#### Scenario: Trailer on the commit only
- **WHEN** the commit carries `Prepush-CI: full` and its parent does not
- **THEN** `prepush-ci verify` for the commit exits 0

### Requirement: The config committed in the commit decides
The demanded keys SHALL be read from the config as committed in `<sha>`, located and validated as the `config` capability specifies, and SHALL NOT be read from the worktree. A commit with no config, or whose config is invalid, SHALL NOT verify, and the reason SHALL say which.

#### Scenario: Worktree config differs
- **WHEN** the worktree config sets `trailer = { key = "Full-Check", value = "yes" }`, the commit's own config has the default key and the commit carries `Prepush-CI: full`
- **THEN** it verifies

#### Scenario: Commit without a config
- **WHEN** the commit has neither `.prepush-ci.toml` nor a `[tool.prepush-ci]` table, and carries `Prepush-CI: full`
- **THEN** it exits 1 and the reason says the commit has no config

#### Scenario: Invalid config in the commit
- **WHEN** the committed config contains an unknown key and the commit carries `Prepush-CI: full`
- **THEN** it exits 1 and the reason names the unknown key

#### Scenario: Config in pyproject.toml
- **WHEN** the commit's only config is a `[tool.prepush-ci]` table in `pyproject.toml` with `legacy_keys = ["Full-Pre-Push"]` and it carries `Full-Pre-Push: required`
- **THEN** it verifies

### Requirement: Server-made commits never verify
A commit whose committer e-mail, as recorded in the commit object (`git log --format=%ce`, which ignores `.mailmap`), equals `noreply@github.com` or `noreply@gitlab.com` SHALL NOT verify, even when it carries a demanding trailer. The comparison SHALL be on the whole address, case-insensitively, never a suffix or a substring. The reason SHALL name the committer e-mail.

#### Scenario: Commit made by GitHub
- **WHEN** the commit carries `Prepush-CI: full` and its committer is `GitHub <noreply@github.com>`
- **THEN** it exits 1 and the reason names `noreply@github.com`

#### Scenario: Commit made by GitLab
- **WHEN** the commit carries `Prepush-CI: full` and its committer is `GitLab <noreply@gitlab.com>`
- **THEN** it exits 1 and the reason names `noreply@gitlab.com`

#### Scenario: Server committer in another case
- **WHEN** the commit carries the trailer and its committer e-mail is `NoReply@GitHub.com`
- **THEN** it exits 1

#### Scenario: Server-made squash commit with the author kept
- **WHEN** the commit's author is `A <a@example.com>`, its committer is `GitHub <noreply@github.com>` and it carries the trailer
- **THEN** it exits 1

#### Scenario: Mailmap cannot hide the server
- **WHEN** the commit carries the trailer, its committer is `GitHub <noreply@github.com>` and a `.mailmap` in the checkout maps `noreply@github.com` to `me@example.com`
- **THEN** it exits 1 and the reason names `noreply@github.com`

#### Scenario: Mailmap cannot make a user a server
- **WHEN** the commit carries the trailer, its committer is `me@example.com` and a `.mailmap` in the checkout maps `me@example.com` to `noreply@github.com`
- **THEN** it verifies

#### Scenario: Private GitHub address of a user
- **WHEN** the commit carries the trailer and its committer e-mail is `123+u@users.noreply.github.com`
- **THEN** it verifies

#### Scenario: Local merge commit
- **WHEN** a merge commit made locally with `PREPUSH_CI=full` carries the trailer
- **THEN** it verifies

### Requirement: Unknown or missing commits fail with what to fetch
When `<sha>` does not resolve to a commit, `verify` SHALL exit 1 and print `not verified:` with a reason that names `<sha>` and says what to fetch. In a shallow clone the reason SHALL mention `git fetch --unshallow` and `fetch-depth`; in a complete repository it SHALL name `git fetch origin <sha>`.

#### Scenario: Unknown sha in a complete repository
- **WHEN** `prepush-ci verify` runs with a well-formed sha that no object has
- **THEN** it exits 1 and the reason names that sha and `git fetch origin`

#### Scenario: Commit missing from a shallow clone
- **WHEN** the repository is a shallow clone, the sha is a commit of the origin that the clone does not have, and `prepush-ci verify` runs
- **THEN** it exits 1 and the reason names `git fetch --unshallow` and `fetch-depth`

#### Scenario: Not a sha
- **WHEN** `prepush-ci verify nonsense` runs
- **THEN** it exits 1 and prints one `not verified:` line

#### Scenario: Outside a repository
- **WHEN** `prepush-ci verify HEAD` runs outside a git repository
- **THEN** it exits 1 and prints one `not verified:` line saying so

### Requirement: A misused command line never exits 0
`prepush-ci verify` run without `<sha>`, with an empty `<sha>`, or with more than one argument SHALL exit 1 and print one `not verified:` line saying what is wrong with the arguments. Exit status 0 SHALL stay reserved for a verified commit.

#### Scenario: No sha
- **WHEN** `prepush-ci verify` runs with no argument
- **THEN** it exits 1 and prints one `not verified:` line that says the sha is missing

#### Scenario: Empty sha
- **WHEN** `prepush-ci verify ""` runs, as a CI step does when its sha variable is unset
- **THEN** it exits 1 and prints one `not verified:` line

#### Scenario: Extra argument
- **WHEN** `prepush-ci verify HEAD HEAD~1` runs
- **THEN** it exits 1 and prints one `not verified:` line, and does not decide about either commit
