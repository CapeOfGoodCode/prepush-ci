## MODIFIED Requirements

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

## ADDED Requirements

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
