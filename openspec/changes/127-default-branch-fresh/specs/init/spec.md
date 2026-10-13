## ADDED Requirements

### Requirement: A default branch that origin lacks
`init` SHALL refuse a default branch, given with `--default-branch` or typed as the answer, when the remote-tracking branches of `origin` (any `refs/remotes/origin/*` other than `HEAD`) exist and none is the named one, unless the next requirement says it is not checked. It SHALL exit 1 with one message naming `default_branch`, the branch and the command `git fetch origin`, and write no file.

#### Scenario: A branch the remote renamed away
- **WHEN** a clone with the default fetch refspec has the remote-tracking branch `origin/main` only and `init --non-interactive --check scripts/ci --default-branch master` runs
- **THEN** it exits 1, the message names `default_branch`, `master` and `git fetch origin`, and no file was created

#### Scenario: A stale default accepted interactively
- **WHEN** a clone with the default fetch refspec has `origin/HEAD` naming `origin/master`, the remote-tracking branch `origin/main` only, and `init --check scripts/ci` runs with an empty line for `default_branch`
- **THEN** it exits 1, the message names `default_branch` and `master`, and no file was created

#### Scenario: A branch origin has
- **WHEN** a clone with the default fetch refspec has the remote-tracking branches `origin/main` and `origin/trunk` and `init --non-interactive --check scripts/ci --default-branch trunk` runs
- **THEN** it exits 0 and the loaded config has default branch `trunk`

### Requirement: When the default branch is not checked
`init` SHALL NOT check the default branch against `origin` when the repository holds no remote-tracking branch of `origin` (no remote, an empty remote, a remote never fetched), when no value of `remote.origin.fetch` is the default `+refs/heads/*:refs/remotes/origin/*` (a single-branch or shallow clone, a narrowed fetch: the remote-tracking branches then say nothing about what `origin` has), or when the up-to-date ref in effect is not `origin/<branch>`.

#### Scenario: No remote-tracking branches
- **WHEN** the repository has no remote, or a remote `origin` whose branches were never fetched, and `init --non-interactive --check scripts/ci --default-branch trunk` runs
- **THEN** it exits 0 and the loaded config has default branch `trunk`

#### Scenario: A single-branch clone
- **WHEN** a clone made with `--single-branch -b feature` holds the remote-tracking branch `origin/feature` only, with the fetch refspec `+refs/heads/feature:refs/remotes/origin/feature`, and `init --non-interactive --check scripts/ci --default-branch main` runs
- **THEN** it exits 0 and the loaded config has default branch `main`

#### Scenario: Another up-to-date ref
- **WHEN** a clone with the default fetch refspec has the remote-tracking branch `origin/main` only and `init --non-interactive --check scripts/ci --default-branch trunk --require-up-to-date upstream/trunk` runs
- **THEN** it exits 0 and the loaded config has default branch `trunk`
