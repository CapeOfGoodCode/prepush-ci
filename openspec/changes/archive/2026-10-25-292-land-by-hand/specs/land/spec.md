## ADDED Requirements

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
`land` SHALL push only when the tip of the default branch of `origin` is an ancestor of the head. Otherwise it SHALL push nothing, print a `not landed:` line that says the branch moved and to rebase onto `<branch>` and push again, and exit 1. A head that is the tip, or an ancestor of it, is already on the branch: `land` SHALL push nothing, print `landed: <sha> already on <branch>` and exit 0.

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
`land` SHALL push only when it finds a pass for the head's tree, under the key the pre-push hook would compute on that commit (the config committed in the head and the output of its `preflight`): in the clone first, then on `origin`, as a push finds it. It SHALL NOT run the check. Without a pass it SHALL push nothing and print a `not landed:` line that names the first twelve characters of the tree and says no pass was found; with `cache = false` the line SHALL say the cache is off.

#### Scenario: A result in the clone
- **WHEN** the clone holds the result ref of the head's tree and key
- **THEN** it lands

#### Scenario: A result only on origin
- **WHEN** a fresh clone holds no result and `origin` holds the ref of the head's tree and key
- **THEN** it lands

#### Scenario: No result
- **WHEN** neither the clone nor `origin` holds a result for the head's tree
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
The `preflight` committed in the head is code of the pull request, run with the rights of whoever runs `land`. `land` SHALL therefore decide every refusal that needs no command of the head before it runs the `preflight`: a pull request or branch `origin` does not give, a branch that moved, a head already on the branch, a head that does not verify, a cache that is off and a missing required variable. The `preflight` SHALL be the first command committed in the head that runs.

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
When `origin` refuses the push, `land` SHALL exit 1 and print `not landed: origin refused the push to <branch> (<reason>)`, where the reason is the text git shows for the refusal, and SHALL say that a branch a ruleset protects is moved by its bypass actors only. When the branch moved since the fetch, the line SHALL be the one of a moved branch. `land` SHALL NOT use `--force`, `--force-with-lease`, a `+` refspec or a deletion.

#### Scenario: A remote that declines
- **WHEN** a hook of `origin` declines every push to `main`
- **THEN** it exits 1, the line starts `not landed: origin refused the push to main`, holds `pre-receive hook declined` and mentions the ruleset, and `main` is unchanged

#### Scenario: The branch moves while landing
- **WHEN** `origin` advances `main` to a commit the head does not contain between the fetch and the push, and refuses the push
- **THEN** it exits 1 with the line of a moved branch and the other commit is still the tip

#### Scenario: A moved branch is never overwritten
- **WHEN** the tip of `main` is not an ancestor of the head
- **THEN** no push is attempted and `main` is unchanged
