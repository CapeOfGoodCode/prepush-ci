# land Specification

## Purpose
`prepush-ci land <pull request number>`: pushes the head of a pull request to the default branch of `origin` as a fast-forward, and only when the head sits on the current tip, its tree has a pass for the configured check, it verifies and the preflight passes in a hook-free checkout of it. It never runs the check, never forces and never reads the pull request's reviews or checks; it prints one line, `landed: …` (exit 0) or `not landed: …` (exit 1).

## Requirements

### Requirement: Land pushes the head of a pull request to the default branch
`prepush-ci land <number>` SHALL, when every requirement below holds, push the head commit of pull request `<number>` to the default branch of `origin` by a fast-forward push, without `--force` and without the repository's hooks, print `landed: <sha> on <branch>` with the full 40-hex sha, and exit 0. It SHALL move no other ref of `origin`, and SHALL NOT change the checked-out branch, the index or the worktree of the clone.

#### Scenario: A checked head lands
- **WHEN** `origin` holds `main` and the pull request head `refs/pull/7/head`, a commit on top of the tip of `main` with the trailer, the clone holds the result of its tree, and `prepush-ci land 7` runs
- **THEN** it exits 0, prints one line `landed: <sha> on main` and `main` of `origin` is the head

#### Scenario: Nothing else moves
- **WHEN** a landing succeeds in a clone with another branch checked out and an uncommitted change
- **THEN** every other ref of `origin` is unchanged, the checked-out branch and the uncommitted change are as they were, and `git status` shows nothing else

#### Scenario: The repository's hooks do not run
- **WHEN** the clone's `pre-push` hook appends a line to a file and a landing succeeds
- **THEN** the file is not written

### Requirement: The head and the branch come from origin
The head SHALL be the commit `origin` holds as `refs/pull/<number>/head` and the default branch the one `origin`'s `HEAD` points to, and `land` SHALL fetch both before it decides anything. A `<number>` that is missing or not a positive integer SHALL be rejected by the command line parser, exit 2, with nothing pushed. A pull request `origin` does not hold and an `origin` that is missing or cannot be reached SHALL give a `not landed:` line that names the cause and exit 1, with nothing pushed.

#### Scenario: The tip is read fresh
- **WHEN** the default branch of `origin` advanced since the clone last fetched, and the head is on top of the new tip
- **THEN** it lands

#### Scenario: A number that is not a number
- **WHEN** `prepush-ci land` runs with no argument, with `abc`, with `0` and with `-1`
- **THEN** each exits 2 and pushes nothing

#### Scenario: A pull request that does not exist
- **WHEN** `prepush-ci land 99` runs and `origin` holds no `refs/pull/99/head`
- **THEN** it exits 1, prints one `not landed:` line naming `99`, and pushes nothing

#### Scenario: No origin
- **WHEN** the repository has no remote `origin`
- **THEN** it exits 1 and prints one `not landed:` line that says there is no `origin`

#### Scenario: Unreachable origin
- **WHEN** the url of `origin` names a directory that is no repository
- **THEN** it exits 1 and prints one `not landed:` line that names `origin`

### Requirement: An origin without a default branch is refused
When `origin`'s `HEAD` names no branch `origin` holds, or `origin` does not report its `HEAD`, `land` SHALL push nothing, print a `not landed:` line that says `origin` names no default branch, and exit 1.

#### Scenario: Head names no branch
- **WHEN** `origin` is a bare repository whose `HEAD` names `master` while it holds only `main`, and `prepush-ci land 7` runs
- **THEN** it exits 1, prints one `not landed:` line that says `origin` names no default branch, and pushes nothing

### Requirement: Only a head on top of the tip lands
`land` SHALL push only when the tip of the default branch of `origin` is an ancestor of the head. Otherwise it SHALL push nothing, print a `not landed:` line that says the branch moved and to rebase onto `<branch>` and push again, and exit 1; a shallow clone gets the line of *A shallow clone says what it cannot tell*. A head that is the tip, or an ancestor of it, is already on the branch: `land` SHALL push nothing, print `landed: <sha> already on <branch>` and exit 0.

#### Scenario: The branch moved
- **WHEN** another commit landed on `main` after the head was made, so the tip is not an ancestor of the head
- **THEN** it exits 1, prints one `not landed:` line that names `main` and says to rebase and push again, and `main` of `origin` is unchanged

#### Scenario: The head is the tip
- **WHEN** the head of the pull request is the tip of `main`
- **THEN** it exits 0, prints `landed: <sha> already on main` and pushes nothing

#### Scenario: The head is behind the tip
- **WHEN** the head is an ancestor of the tip
- **THEN** it exits 0 with the same line and `main` is unchanged

#### Scenario: The config does not relax it
- **WHEN** the config committed in the head sets `require_up_to_date = false` and the tip of `main` is not an ancestor of the head
- **THEN** it exits 1 as for a moved branch and pushes nothing

#### Scenario: Unrelated history
- **WHEN** the head shares no commit with `main`
- **THEN** it exits 1 with the line of a moved branch and pushes nothing

### Requirement: The required variables are set
Before it computes the key, `land` SHALL require every variable named in `require_env` in the config committed in the head to be set and non-empty in its own environment, as the pre-push hook does. When any is not, it SHALL push nothing, run no command committed in the head, print a `not landed:` line that names every missing variable, and exit 1.

#### Scenario: A missing variable
- **WHEN** the config committed in the head sets `require_env = ["A_URL", "B_URL"]`, neither is set, and a result exists
- **THEN** it exits 1, the line names `A_URL` and `B_URL`, and nothing is pushed

#### Scenario: An empty variable
- **WHEN** the config sets `require_env = ["A_URL"]` and `A_URL` is the empty string
- **THEN** it exits 1 and the line names `A_URL`

#### Scenario: The variables are set
- **WHEN** the config sets `require_env = ["A_URL"]`, `A_URL` is set and a result exists
- **THEN** it lands

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

### Requirement: The preflight runs in a checkout of the head
`land` SHALL run the `preflight` of the committed config in a temporary detached checkout of the head, as the hook runs it in `HEAD`, and SHALL print its standard output on standard error. A failing preflight SHALL stop the landing: nothing is pushed, the line names the preflight, and the exit status is 1. The checkout SHALL run none of the repository's hooks, and SHALL be gone afterwards, whether the landing succeeded or not.

#### Scenario: A failing preflight
- **WHEN** the config sets `preflight = "test -f ready"`, the head has no file `ready` and a result exists
- **THEN** it exits 1, the line names the preflight and nothing is pushed

#### Scenario: The preflight sees the head
- **WHEN** the config sets `preflight = "test -f ready"`, the head holds the file `ready` and the clone's worktree does not
- **THEN** the preflight passes

#### Scenario: Its output is not the answer
- **WHEN** the config sets `preflight = "echo versions-ok"` and a landing succeeds
- **THEN** standard output is the one `landed:` line and standard error holds `versions-ok`

#### Scenario: The repository's hooks do not run in the checkout
- **WHEN** the clone's `post-checkout` hook appends a line to a file and a landing succeeds
- **THEN** the file is not written

#### Scenario: The checkout is removed
- **WHEN** a landing succeeds and another fails on its preflight
- **THEN** after each, `git worktree list` shows only the clone

### Requirement: No command of the head runs before the refusals that need none
The `preflight` committed in the head is code of the pull request, run with the rights of whoever runs `land`. `land` SHALL decide every refusal that needs no command of the head before it runs the `preflight`: a pull request or branch `origin` does not give, a branch that moved or that a shallow clone cannot judge, a head already on the branch, a head that does not verify, a cache that is off and a missing required variable. The `preflight` SHALL be the first command of the head that runs.

#### Scenario: A head without the trailer
- **WHEN** the config sets a `preflight` that writes the file `ran`, and the head has no demanding trailer
- **THEN** it exits 1 and the file `ran` does not exist

#### Scenario: A branch that moved
- **WHEN** the config sets a `preflight` that writes the file `ran`, and the tip of `main` is not an ancestor of the head
- **THEN** it exits 1 and the file `ran` does not exist

#### Scenario: A head already on the branch
- **WHEN** the config sets a `preflight` that writes the file `ran`, and the head is the tip of `main`
- **THEN** it exits 0 and the file `ran` does not exist

#### Scenario: The cache is off or a variable is missing
- **WHEN** the config sets a `preflight` that writes the file `ran`, and sets `cache = false`, or names an unset variable in `require_env`
- **THEN** it exits 1 and the file `ran` does not exist

### Requirement: The head must verify
`land` SHALL push only a head that `prepush-ci verify` would verify, with the config committed in it: a demanding trailer, and not made by a server. Otherwise it SHALL push nothing, print a `not landed:` line with the reason `verify` gives, and exit 1.

#### Scenario: A head without the trailer
- **WHEN** the head has no demanding trailer and a result exists for its tree
- **THEN** it exits 1, the line says there is no trailer and nothing is pushed

#### Scenario: A head made by a server
- **WHEN** the head carries the trailer and its committer is `GitHub <noreply@github.com>`
- **THEN** it exits 1 and the line names `noreply@github.com`

### Requirement: The answer is one line
The standard output of `land` SHALL be exactly one line, `landed: …` or `not landed: …`; warnings SHALL go to standard error. The exit status SHALL be 0 only for a line that starts with `landed:` and 1 for every other outcome the command decides, with exit 2 reserved for the parser. A `not landed:` line SHALL never hold the content of a file.

#### Scenario: One line on success
- **WHEN** a landing succeeds, and `origin` warns about its url
- **THEN** standard output holds one line starting `landed:`

#### Scenario: One line on failure
- **WHEN** a landing fails for any of the reasons above
- **THEN** standard output holds one line starting `not landed:` and the exit status is 1

### Requirement: A refused push is reported, never forced
When `origin` refuses the push and the head is not on the branch (see *A head that landed meanwhile is landed*), `land` SHALL exit 1 and print `not landed: origin refused the push to <branch> (<reason>)`, where the reason is the text git shows for the refusal, and SHALL say that a branch a ruleset protects is moved by its bypass actors only. A branch that moved since the fetch gets the line of a moved branch. `land` SHALL NOT use `--force`, `--force-with-lease`, a `+` refspec or a deletion.

#### Scenario: A remote that declines
- **WHEN** a hook of `origin` declines every push to `main`
- **THEN** it exits 1, the line starts `not landed: origin refused the push to main`, holds `pre-receive hook declined` and mentions the ruleset, and `main` is unchanged

#### Scenario: The branch moves while landing
- **WHEN** `origin` advances `main` to a commit the head does not contain between the fetch and the push, and refuses the push
- **THEN** it exits 1 with the line of a moved branch and the other commit is still the tip

#### Scenario: A moved branch is never overwritten
- **WHEN** the tip of `main` is not an ancestor of the head
- **THEN** no push is attempted and `main` is unchanged

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

### Requirement: A head that landed meanwhile is landed
When `origin` refuses the push, `land` SHALL fetch the tip of the default branch it then lists. When the head is that tip or an ancestor of it, `land` SHALL print `landed: <sha> already on <branch>`, exit 0 and push nothing more, as for a head found on the branch before the push. A tip it cannot list or fetch, and a branch it no longer lists, SHALL NOT count as a landing: the answer of the refusal stands.

#### Scenario: Another run lands the same head
- **WHEN** a second `land` of the same head pushes to `main` while the first push is in flight, and `origin` refuses the second push because the first one moved `main` to the head
- **THEN** both exit 0, the loser prints `landed: <sha> already on main`, and `main` is the head

#### Scenario: The head landed under a later commit
- **WHEN** `origin` advances `main` to a commit that has the head as an ancestor between the fetch and the push, and refuses the push
- **THEN** it exits 0, prints `landed: <sha> already on main` and `main` is unchanged by `land`

#### Scenario: The branch is gone
- **WHEN** `origin` deletes `main` between the fetch and the push, and refuses the push
- **THEN** it exits 1 with a line starting `not landed:` and prints no `landed:` line

### Requirement: A shallow clone says what it cannot tell
In a shallow clone (`git rev-parse --is-shallow-repository` prints `true`), when the tip and the head as first fetched leave the tip not an ancestor of the head and the head not on the branch, `land` SHALL push nothing, fetch no more history and exit 1, printing one `not landed:` line that says the clone is shallow, that it cannot tell whether `<branch>` moved, and names `git fetch --unshallow` and `fetch-depth`. A refused push keeps the moved line.

#### Scenario: A head one commit above the tip, in a clone of depth 1
- **WHEN** the clone is a shallow clone of depth 1, the pull request head is one commit on top of the tip of `main` (fetched at depth 1, so its parent is missing), and `prepush-ci land 7` runs
- **THEN** it exits 1, prints one `not landed:` line that says the clone is shallow and names `git fetch --unshallow` and `fetch-depth`, does not say to rebase, and `main` of `origin` is unchanged

#### Scenario: The clone is deepened and lands
- **WHEN** the run above is repeated after `git fetch --unshallow origin`
- **THEN** it exits 0, prints `landed: <sha> on main` and `main` of `origin` is the head

#### Scenario: A branch that moved, in a shallow clone
- **WHEN** another commit landed on `main` after the head was made, and the clone is shallow with depth 1
- **THEN** it exits 1 with the shallow line, not the line of a moved branch, and pushes nothing

#### Scenario: A shallow clone that can see the tip lands
- **WHEN** the clone is shallow, the head was fetched with depth 2 so that the tip is its parent, and `prepush-ci land 7` runs
- **THEN** it exits 0, prints `landed: <sha> on main` and `main` of `origin` is the head

#### Scenario: A shallow clone and a head on the branch
- **WHEN** the clone is shallow and the head is the tip of `main`
- **THEN** it exits 0, prints `landed: <sha> already on main` and pushes nothing

#### Scenario: The branch moves while landing, in a shallow clone
- **WHEN** the clone is shallow, the head was fetched with depth 2 so that the tip is its parent, and `origin` advances `main` to a commit the head does not contain between the fetch and the push, and refuses the push
- **THEN** it exits 1 with the line of a moved branch, not the shallow line, and the other commit is still the tip

#### Scenario: The shallow refusal comes before the preflight
- **WHEN** the config sets a `preflight` that writes the file `ran`, and the clone is shallow with depth 1 and cannot see the tip below the head
- **THEN** it exits 1 with the shallow line and the file `ran` does not exist

#### Scenario: A complete clone is told that the branch moved
- **WHEN** the clone is complete and another commit landed on `main` after the head was made
- **THEN** it exits 1 with the line of a moved branch, as before
