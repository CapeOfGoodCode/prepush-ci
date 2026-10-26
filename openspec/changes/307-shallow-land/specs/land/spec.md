## MODIFIED Requirements

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

## ADDED Requirements

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
