## ADDED Requirements

### Requirement: The warning that a result was not shared is one line
When the push of the result ref to `origin` fails, the warning SHALL be one line on standard error, `prepush-ci: the result was not shared through origin (<cause>), so another clone runs the check again; the push goes on`, with nothing of git's output in it.

#### Scenario: A rejected ref
- **WHEN** `origin` declines every ref outside `refs/heads/` with a hook and a tip with the trailer whose check passes is pushed to `origin`
- **THEN** the push succeeds and standard error holds the line `prepush-ci: the result was not shared through origin (origin rejected the ref), so another clone runs the check again; the push goes on`

#### Scenario: Git's lines stay out
- **WHEN** the push of the result ref fails with several lines of output
- **THEN** the warning is one line and holds no `fatal:`, `error:` or `remote:` text from git

### Requirement: The warning names the cause in a few words
The cause SHALL be `origin refused the ref, HTTP <status>` when a line of git's output that does not start with `remote:` holds `HTTP <status>` or `error: <status>` with a status from 400 to 599, else `origin rejected the ref` when it holds a `[remote rejected]` line, else `git could not push it`.

#### Scenario: A status from the transport
- **WHEN** git's output for the failed push is `fatal: unable to access 'http://h/x.git/': The requested URL returned error: 403`, or `error: RPC failed; HTTP 403 curl 22 The requested URL returned error: 403` followed by `fatal: expected 'acknowledgments', received 'packfile'`
- **THEN** the cause is `origin refused the ref, HTTP 403`

#### Scenario: A failure without a status
- **WHEN** git's output is `fatal: '/x.git' does not appear to be a git repository`
- **THEN** the cause is `git could not push it`

#### Scenario: A status in the remote's own text
- **WHEN** git's output is `remote: error: 500 files are over the limit` followed by ` ! [remote rejected] main -> refs/prepush-ci/results/t-k (pre-receive hook declined)`
- **THEN** the cause is `origin rejected the ref`, because a line from the remote is its author's text and not a transport status

#### Scenario: A number that is not a status
- **WHEN** git's output holds `error: 200` or `HTTP 302`
- **THEN** the cause is `git could not push it`

### Requirement: Git's output of that push can be asked for
With `PREPUSH_CI_DEBUG` set to a non-empty value, the lines git printed for the failed push of the result ref SHALL follow the warning on standard error, unchanged. With it unset or empty, nothing of them SHALL be printed.

#### Scenario: Debug on
- **WHEN** `PREPUSH_CI_DEBUG=1` and `origin` declines the result ref
- **THEN** the warning line is followed by git's lines, including the `[remote rejected]` line

#### Scenario: Debug off or empty
- **WHEN** `PREPUSH_CI_DEBUG` is unset, or set to the empty string, and `origin` declines the result ref
- **THEN** standard error holds the warning line and no line of git's output
