# ci-gate Specification

## Purpose
How pull request CI uses `prepush-ci verify` to skip its own run. `docs/ci/gate.sh` holds the rule and is the generic gate; `docs/ci/github-actions.yml` and `docs/ci/gitlab-ci.yml` wire it into two CI systems; `action.yml` is the optional GitHub Action. A gate skips only a pull or merge request from the same repository, whose source branch is not the default branch, whose head commit verifies. Every doubt means "do not skip".

## Requirements

### Requirement: The shell gate decides from its environment
`docs/ci/gate.sh` SHALL read `GATE_PULL_REQUEST`, `GATE_HEAD_SHA`, `GATE_HEAD_REPO`, `GATE_BASE_REPO`, `GATE_HEAD_BRANCH` and `GATE_DEFAULT_BRANCH` from the environment. It SHALL print exactly one line on standard output, `verified=true` or `verified=false`, give its reason on standard error, and exit 0 whatever it decides.

#### Scenario: One line on standard output
- **WHEN** the gate runs for a pull request whose head commit carries the trailer
- **THEN** standard output is exactly `verified=true` followed by a newline and the exit status is 0

#### Scenario: Reason on standard error
- **WHEN** the gate runs for a pull request whose head commit has no trailer
- **THEN** standard output is exactly `verified=false`, standard error holds the line `verify` printed, and the exit status is 0

### Requirement: Skip only on a verified pull request head
The shell gate SHALL print `verified=true` only when `GATE_PULL_REQUEST` is `true`, `GATE_HEAD_REPO` equals `GATE_BASE_REPO`, `GATE_HEAD_BRANCH` differs from `GATE_DEFAULT_BRANCH`, and `$PREPUSH_CI_CMD verify "$GATE_HEAD_SHA"` exits 0. `PREPUSH_CI_CMD` SHALL default to `uvx prepush-ci`.

#### Scenario: Pull request from the same repository
- **WHEN** all inputs describe a pull request whose head repository is the base repository and whose head commit verifies
- **THEN** it prints `verified=true`

#### Scenario: Default command
- **WHEN** `PREPUSH_CI_CMD` is unset, the request is eligible and a `uvx` program on `PATH` records its arguments and exits 0
- **THEN** the recorded arguments are `prepush-ci verify` followed by the head sha, and it prints `verified=true`

#### Scenario: Not a pull request
- **WHEN** `GATE_PULL_REQUEST` is `false` and the head commit verifies
- **THEN** it prints `verified=false`

#### Scenario: Pull request from a fork
- **WHEN** `GATE_HEAD_REPO` is `fork/repo`, `GATE_BASE_REPO` is `owner/repo` and the head commit verifies
- **THEN** it prints `verified=false`

#### Scenario: Source branch is the default branch
- **WHEN** `GATE_HEAD_BRANCH` and `GATE_DEFAULT_BRANCH` are both `main` and the head commit verifies
- **THEN** it prints `verified=false`

#### Scenario: Head commit does not verify
- **WHEN** the request is eligible and `verify` exits 1 for the head commit
- **THEN** it prints `verified=false`

#### Scenario: Server-made head commit
- **WHEN** the request is eligible and the head commit carries the trailer but its committer is `noreply@github.com`
- **THEN** it prints `verified=false`

### Requirement: A missing input never skips
The shell gate SHALL print `verified=false` when any of its six variables is unset or empty, or when the command in `PREPUSH_CI_CMD` cannot be started.

#### Scenario: Empty head repository
- **WHEN** `GATE_HEAD_REPO` is empty, as for a deleted fork, and the head commit verifies
- **THEN** it prints `verified=false`

#### Scenario: Unset head sha
- **WHEN** `GATE_HEAD_SHA` is unset
- **THEN** it prints `verified=false` and exits 0

#### Scenario: Empty default branch
- **WHEN** `GATE_DEFAULT_BRANCH` is empty, `GATE_HEAD_BRANCH` is `feature`, every other input describes an eligible request and the head commit verifies
- **THEN** it prints `verified=false`

#### Scenario: Both repositories empty
- **WHEN** `GATE_HEAD_REPO` and `GATE_BASE_REPO` are both empty, every other input describes an eligible request and the head commit verifies
- **THEN** it prints `verified=false`

#### Scenario: Missing command
- **WHEN** the request is eligible and `PREPUSH_CI_CMD` names a program that does not exist
- **THEN** it prints `verified=false` and exits 0

### Requirement: The GitHub Action
`action.yml` at the repository root SHALL define a composite action with an input `command` (default `pipx run prepush-ci`) and an output `verified`. Its one step SHALL run `docs/ci/gate.sh` from the action's own path and append the gate's output line to `$GITHUB_OUTPUT`.

#### Scenario: Output wired to the gate
- **WHEN** `action.yml` is read
- **THEN** it declares `using: composite`, an output `verified` whose value is the step's `verified`, and a step that runs `docs/ci/gate.sh` from `github.action_path` or `GITHUB_ACTION_PATH` and writes to `GITHUB_OUTPUT`

#### Scenario: Command input
- **WHEN** `action.yml` is read
- **THEN** its input `command` defaults to `pipx run prepush-ci` and reaches the gate as `PREPUSH_CI_CMD`

### Requirement: The action skips only a pull request from the same repository
`action.yml` SHALL set `GATE_PULL_REQUEST` to `true` only for the `pull_request` event, and SHALL take the head sha, head repository, head branch, base repository and default branch from the event, so that push events, the default branch and fork pull requests print `verified=false`. The step SHALL pass these values and `command` in its `env:`; its `run:` SHALL contain no `${{ }}` expression.

#### Scenario: Event mapping
- **WHEN** `action.yml` is read
- **THEN** `GATE_PULL_REQUEST` is `${{ github.event_name == 'pull_request' }}`, `GATE_HEAD_SHA` is `github.event.pull_request.head.sha`, `GATE_HEAD_REPO` is `github.event.pull_request.head.repo.full_name`, `GATE_BASE_REPO` is `github.repository`, `GATE_HEAD_BRANCH` is `github.head_ref` and `GATE_DEFAULT_BRANCH` is `github.event.repository.default_branch`

#### Scenario: Values reach the script through the environment
- **WHEN** `action.yml` is read
- **THEN** the step's `run:` contains no `${{`, and `github.head_ref` and `inputs.command` appear only under the step's `env:`

#### Scenario: Not the pull_request_target event
- **WHEN** `action.yml` is read
- **THEN** it does not mention `pull_request_target`

### Requirement: The GitHub Actions example
`docs/ci/github-actions.yml` SHALL run on `pull_request` and on `push` to the default branch, check out `github.event.pull_request.head.sha` for the gate, run the action in a `gate` job that outputs `verified`, and give every other job `needs: gate` and an `if:` with the status function `!cancelled()` that holds unless the gate's output is `true`, so the job also runs when the gate job failed.

#### Scenario: Head commit checked out
- **WHEN** the example is read
- **THEN** its gate job checks out `${{ github.event.pull_request.head.sha }}` and its default-branch push trigger leaves the gate's output `false`

#### Scenario: Other jobs wait for the gate
- **WHEN** the example is read
- **THEN** its other jobs have `needs: gate` and an `if:` that combines `!cancelled()` with the gate's `verified` output not being `true`

#### Scenario: A failed gate does not skip the jobs
- **WHEN** the example is read
- **THEN** no job that needs `gate` has an `if:` without a status function, because GitHub skips such a job when the gate failed, and a skipped job reports success

### Requirement: The GitLab CI example
`docs/ci/gitlab-ci.yml` SHALL gate only merge request pipelines, SHALL call `prepush-ci verify` on `CI_MERGE_REQUEST_SOURCE_BRANCH_SHA`, falling back to `CI_COMMIT_SHA`, and SHALL NOT skip when the source project differs from the project, when the source branch is the default branch, or in a pipeline on the default branch.

#### Scenario: Verify on the source head
- **WHEN** the example is read
- **THEN** it runs `prepush-ci verify` with `CI_MERGE_REQUEST_SOURCE_BRANCH_SHA` and falls back to `CI_COMMIT_SHA`

#### Scenario: Forks and default branch
- **WHEN** the example is read
- **THEN** it compares `CI_MERGE_REQUEST_SOURCE_PROJECT_PATH` with `CI_PROJECT_PATH`, compares `CI_MERGE_REQUEST_SOURCE_BRANCH_NAME` with `CI_DEFAULT_BRANCH`, and runs the full pipeline for `CI_COMMIT_BRANCH` equal to `CI_DEFAULT_BRANCH`

#### Scenario: Rebase button warning
- **WHEN** the example is read
- **THEN** a comment says not to use the merge request's Rebase button when the pipeline relies on skipping

### Requirement: The examples name the optional full run
Each of the three files in `docs/ci/` SHALL carry a comment that names the option of one full run per pull request anyway, as a mitigation for missing local hooks, with `ready_for_review` or another trigger as an example, and says that it is off.

#### Scenario: Mention in every example
- **WHEN** each of `gate.sh`, `github-actions.yml` and `gitlab-ci.yml` is read
- **THEN** each contains the phrase `one full run per pull request`

### Requirement: The shell gate example calls verify
`docs/ci/gate.sh` SHALL be written in POSIX `sh`, SHALL run `verify` through `$PREPUSH_CI_CMD` and no other way, and its header comment SHALL list the variables a CI maps and say how to read its output.

#### Scenario: POSIX shell
- **WHEN** `gate.sh` is read
- **THEN** its first line is `#!/bin/sh` and it uses no `[[`

#### Scenario: Header lists the variables
- **WHEN** `gate.sh` is read
- **THEN** its leading comment names the six `GATE_` variables and `PREPUSH_CI_CMD`
