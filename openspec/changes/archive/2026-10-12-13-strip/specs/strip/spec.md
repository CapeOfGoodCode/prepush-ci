## ADDED Requirements

### Requirement: Strip removes the demanding trailer
`prepush-ci strip [<base>]` SHALL remove from the message of every commit in `<base>..HEAD` each line of the trailer block whose key equals `trailer.key` or one of `legacy_keys`, compared case-insensitively, whatever the value. The trailer block SHALL be the one `git log` reads (`%(trailers:only,unfold)`). Everything else in the message SHALL stay byte for byte. When the removal leaves the trailer block empty, the blank line that separated it from the body SHALL go with it.

#### Scenario: Commit with the trailer
- **WHEN** `HEAD` was committed with `PREPUSH_CI=full` and `prepush-ci strip` runs
- **THEN** the message of `HEAD` has no `Prepush-CI` trailer

#### Scenario: Message made by the commit-msg hook is restored
- **WHEN** `git commit -m "add x"` ran with `PREPUSH_CI=full` and `prepush-ci strip` runs
- **THEN** the message of `HEAD` is exactly `add x` followed by a newline

#### Scenario: Other trailers stay
- **WHEN** the commit's trailer block holds `Prepush-CI: full` and `Co-Authored-By: A <a@example.com>`
- **THEN** after `strip` the block holds only `Co-Authored-By: A <a@example.com>` and the rest of the message is unchanged

#### Scenario: Configured key
- **WHEN** the config sets `trailer = { key = "Full-Check", value = "yes" }` and a commit carries `Full-Check: yes` and `Prepush-CI: full`
- **THEN** `strip` removes `Full-Check: yes` and leaves `Prepush-CI: full`

#### Scenario: Legacy key
- **WHEN** the config sets `legacy_keys = ["Full-Pre-Push"]` and a commit carries `Full-Pre-Push: required`
- **THEN** `strip` removes that trailer

#### Scenario: Key in another case and any value
- **WHEN** commits carry `prepush-ci: full` and `Prepush-CI: off`
- **THEN** `strip` removes both trailers

#### Scenario: Several matching lines
- **WHEN** one commit's trailer block holds `Prepush-CI: full` twice
- **THEN** `strip` removes both lines

#### Scenario: Divider line in the body
- **WHEN** a commit's message is `subject`, a blank line, `body`, `---`, `more`, a blank line and `Prepush-CI: full`
- **THEN** after `strip` the message keeps `body`, `---` and `more` in order and has no trailer

#### Scenario: Trailer text in the body
- **WHEN** a commit's message has `Prepush-CI: full` in its body but not in its last paragraph
- **THEN** `strip` leaves that commit's message unchanged

### Requirement: A removed trailer takes its continuation lines
The lines that follow a removed trailer in the block and begin with whitespace belong to its value, so `strip` SHALL remove them with it. No other trailer's value SHALL change.

#### Scenario: Folded trailer
- **WHEN** a commit's trailer block is `Co-Authored-By: A <a@example.com>`, `Prepush-CI: full` and, indented, `because the db changed`
- **THEN** after `strip` the block holds only `Co-Authored-By: A <a@example.com>`, and `git log -1 --format='%(trailers:only,unfold)'` shows exactly that value, unchanged

### Requirement: Strip runs no hooks and never re-adds the trailer
`strip` SHALL NOT run any git hook, and no commit it writes SHALL carry a demanding trailer, whatever `PREPUSH_CI` is.

#### Scenario: Strip with PREPUSH_CI=full set
- **WHEN** the `commit-msg` hook is installed, `PREPUSH_CI=full` is set and `prepush-ci strip` runs on a branch of commits made with the trailer
- **THEN** the rewritten commits have no demanding trailer

#### Scenario: No hook runs
- **WHEN** `commit-msg`, `pre-commit`, `post-commit` and `post-rewrite` hooks that each write a marker file are installed and `prepush-ci strip` rewrites commits
- **THEN** none of the marker files exists afterwards

### Requirement: The rest of the history stays
A rewritten commit SHALL keep its tree, author and committer (name, e-mail and date) and message encoding. A merge commit in the range SHALL stay a merge of the same shape: its parents are the rewritten counterparts of its old parents. The commit at `<base>` and everything before it SHALL NOT change.

#### Scenario: Tree, author and committer kept
- **WHEN** `strip` rewrites a commit whose author and committer differ and whose dates are not the current time
- **THEN** the rewritten commit has the same tree, author name, e-mail and date, and committer name, e-mail and date

#### Scenario: Server committer kept
- **WHEN** `strip` rewrites a commit whose committer is `GitHub <noreply@github.com>`
- **THEN** the rewritten commit's committer is still `noreply@github.com`

#### Scenario: Merge commit in the range
- **WHEN** the range holds a merge commit with the trailer, made from a side branch whose commits also carry the trailer
- **THEN** after `strip` the merge has two parents, both rewritten, none of the commits in the range has the trailer, and the trees are unchanged

#### Scenario: Base commit untouched
- **WHEN** the commit at `<base>` carries the trailer
- **THEN** after `strip` it is unchanged and keeps its SHA

### Requirement: No needless rewrites
A commit SHALL keep its SHA when its message needs no change and none of its parents changed. A commit whose parent changed SHALL get a new SHA and keep its message. When no commit in the range changes, `strip` SHALL leave the branch where it is.

#### Scenario: Commits before the first trailer keep their SHA
- **WHEN** the range holds commits A (no trailer), B (trailer) and C (no trailer)
- **THEN** after `strip` A has the same SHA, B and C have new SHAs, and C's message is unchanged

#### Scenario: Nothing to strip
- **WHEN** no commit in the range carries the trailer
- **THEN** `HEAD` has the same SHA after `strip` and the report says 0 commits were rewritten

### Requirement: Which commits are in range
`<base>` SHALL be any revision git resolves to a commit that is an ancestor of `HEAD`. Without `<base>`, the base SHALL be the merge base of `HEAD` and `origin/<default_branch>`, or when that ref does not exist, of `HEAD` and the local `<default_branch>`. When neither ref exists and no `<base>` is given, or when the ref exists but `HEAD` and it have no merge base, `strip` SHALL refuse, say that `<base>` is needed, and change nothing. It SHALL NOT fall back to the whole history.

#### Scenario: Default base is the merge base with the remote default branch
- **WHEN** `origin/main` holds a commit with the trailer, the branch forked from it and holds two more commits with the trailer, and `prepush-ci strip` runs
- **THEN** the two branch commits lose the trailer and the commit on `origin/main` is unchanged

#### Scenario: Default base falls back to the local default branch
- **WHEN** the repository has no remote, a local `main` and a branch of two commits with the trailer
- **THEN** `prepush-ci strip` rewrites those two commits

#### Scenario: Configured default branch
- **WHEN** the config sets `default_branch = "trunk"` and `origin/trunk` is the fork point
- **THEN** the range starts at the merge base with `origin/trunk`

#### Scenario: Explicit base
- **WHEN** `prepush-ci strip HEAD~1` runs and the last two commits carry the trailer
- **THEN** only `HEAD` is rewritten

#### Scenario: No default branch and no base
- **WHEN** the repository has neither `origin/main` nor `main`, and `prepush-ci strip` runs without `<base>`
- **THEN** it exits 1, says `<base>` is needed, and changes nothing

#### Scenario: Default branch without a common history
- **WHEN** `origin/main` exists and shares no commit with `HEAD` (for example a branch created with `git checkout --orphan`), and `prepush-ci strip` runs without `<base>`
- **THEN** it exits 1, says `<base>` is needed, and changes nothing

#### Scenario: Explicit base without a common history
- **WHEN** the same repository is given `<base>` that is an ancestor of `HEAD`
- **THEN** `strip` rewrites the commits in `<base>..HEAD`

#### Scenario: Unknown base
- **WHEN** `prepush-ci strip nonsense` runs
- **THEN** it exits 1, names `nonsense`, and changes nothing

#### Scenario: Base that is not an ancestor
- **WHEN** `<base>` is a commit of another branch that is not an ancestor of `HEAD`
- **THEN** it exits 1, says the base is not an ancestor of `HEAD`, and changes nothing

### Requirement: Strip refuses states in which a rewrite could lose work
`strip` SHALL exit 1 without changing any ref or file, and print a reason, when the worktree is not clean (staged or unstaged changes to tracked files, or untracked files that are not ignored), when a rebase, merge, cherry-pick, revert, `git am` or bisect is in progress, or when `HEAD` is detached.

#### Scenario: Unstaged change
- **WHEN** a tracked file has an unstaged change and `prepush-ci strip` runs
- **THEN** it exits 1, lists the file, and `HEAD` is unchanged

#### Scenario: Staged change
- **WHEN** a tracked file has a staged change
- **THEN** it exits 1, lists the file, and `HEAD` is unchanged

#### Scenario: Untracked file
- **WHEN** an untracked file that is not ignored exists
- **THEN** it exits 1, lists the file, and `HEAD` is unchanged

#### Scenario: Ignored file
- **WHEN** only an ignored file exists besides the tracked ones
- **THEN** `strip` runs

#### Scenario: Rebase in progress
- **WHEN** an interactive rebase stopped on a conflict or an edit
- **THEN** it exits 1, says a rebase is in progress, and the rebase state is unchanged

#### Scenario: Merge in progress
- **WHEN** a merge stopped on a conflict
- **THEN** it exits 1 and says a merge is in progress

#### Scenario: Cherry-pick or revert in progress
- **WHEN** a cherry-pick or a revert stopped on a conflict
- **THEN** it exits 1 and names the operation

#### Scenario: Mailbox apply in progress
- **WHEN** `git am` stopped on a patch that does not apply
- **THEN** it exits 1 and says `git am` is in progress

#### Scenario: Bisect in progress
- **WHEN** `git bisect start --no-checkout` ran, so `HEAD` is still on its branch
- **THEN** it exits 1 and says a bisect is in progress

#### Scenario: Detached HEAD
- **WHEN** `HEAD` is detached
- **THEN** it exits 1 and says that a checked-out branch is needed

### Requirement: Strip moves only the current branch
`strip` SHALL move only the branch that `HEAD` points to, to the rewritten tip, and the worktree SHALL match it. It SHALL NOT change any other ref, any remote, or push.

#### Scenario: Other refs stay
- **WHEN** a tag and another branch point at commits that `strip` rewrites on the current branch
- **THEN** the tag and the other branch still point at their old commits

#### Scenario: Old tip stays reachable
- **WHEN** `strip` rewrites the branch
- **THEN** the old tip printed in the report is still a commit in the repository, and `git reset --hard <old tip>` restores the branch

#### Scenario: Worktree matches the new tip
- **WHEN** `strip` rewrites the branch
- **THEN** `git status` shows a clean worktree and the files equal those of the old tip

### Requirement: Strip reports what it did
`strip` SHALL print a line starting with `strip:` that holds the number of commits rewritten, the number of commits in the range, and the full old and new tip. When at least one commit was rewritten it SHALL also print that the next push needs `git push --force-with-lease`. When none was, it SHALL say that nothing needs pushing again and SHALL NOT print the force hint. It SHALL exit 0.

#### Scenario: Report after a rewrite
- **WHEN** `strip` rewrites 2 of 3 commits in the range
- **THEN** it exits 0, the `strip:` line holds `2`, `3` and both tips, and a line says the next push needs `--force-with-lease`

#### Scenario: Report with nothing to rewrite
- **WHEN** no commit in the range has the trailer
- **THEN** it exits 0, the `strip:` line holds `0`, and no line mentions `--force-with-lease`

### Requirement: Strip needs a valid config
`strip` SHALL read the config as the `config` capability specifies and refuse with exit 1, changing nothing, when it is missing or invalid. A misused command line (more than one argument) SHALL also exit 1 and change nothing.

#### Scenario: No config
- **WHEN** the repository has no config and `prepush-ci strip` runs
- **THEN** it exits 1 with the missing-config error and `HEAD` is unchanged

#### Scenario: Invalid config
- **WHEN** the config contains an unknown key
- **THEN** it exits 1, names the key, and `HEAD` is unchanged

#### Scenario: Extra argument
- **WHEN** `prepush-ci strip HEAD~1 HEAD~2` runs
- **THEN** it exits 1 and `HEAD` is unchanged

### Requirement: A stripped branch pushes without a check
After `strip`, no commit in `<base>..HEAD` SHALL demand the check, so the pre-push hook SHALL let the push through without running it when `PREPUSH_CI` is unset.

#### Scenario: Push after strip
- **WHEN** the pre-push hook is installed, the branch has two commits made with `PREPUSH_CI=full`, `prepush-ci strip` ran, and `git push --force-with-lease origin HEAD` runs with `PREPUSH_CI` unset
- **THEN** the push succeeds and the check does not run

#### Scenario: Push before strip
- **WHEN** the same branch is pushed with `PREPUSH_CI` unset before `strip`
- **THEN** the hook runs the check
