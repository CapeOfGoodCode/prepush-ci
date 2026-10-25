## Purpose
`docs/ci/land.yml`: the example of a GitHub Actions workflow that lands an approved pull request with `prepush-ci land` and the installation token of the app from `app setup --land`, and tells the author on the pull request when it did not land. Users copy it to `.github/workflows/`; it is the second way to land of #199, beside `land` by hand.

## ADDED Requirements

### Requirement: The workflow runs when a review is submitted
`docs/ci/land.yml` SHALL run on `pull_request_review` of type `submitted` and on no other event. It SHALL have one job, `land`, that runs only when the review's state is `approved` and the head repository of the pull request is the repository itself, and its top-level `permissions` SHALL be empty, so that every job names what it needs.

#### Scenario: One event
- **WHEN** the file is parsed
- **THEN** its triggers are `pull_request_review` with `types: [submitted]` and nothing else, and its only job is `land`

#### Scenario: Approved, from this repository
- **WHEN** the file is parsed
- **THEN** the `if:` of `land` holds `github.event.review.state == 'approved'` and compares `github.event.pull_request.head.repo.full_name` with `github.repository`

#### Scenario: No default permissions
- **WHEN** the file is parsed
- **THEN** the top-level `permissions` is empty and the `permissions` of `land` are `contents: read` and `pull-requests: write`

### Requirement: A step decides whether to land
The step `decide` SHALL write `land=true` or `land=false` to `GITHUB_OUTPUT`, exit 0 whatever it decides, and post no comment. Every other step of `land` SHALL run only when the output is `true`, so that a review that does not qualify ends the job without a trace.

#### Scenario: Later steps wait for the decision
- **WHEN** the file is parsed
- **THEN** every step of `land` after `decide` has an `if:` that holds `steps.decide.outputs.land == 'true'`

#### Scenario: A call cannot be read
- **WHEN** a call to `gh` fails, whether the one for the permission, the one for the pull request or the one for the review
- **THEN** `decide` writes `land=false` and exits 0

### Requirement: The pull request is read when the job runs
`decide` SHALL read the pull request from the API when it runs, with `GET /repos/<repository>/pulls/<number>` and the job's own token, and take its head sha, base branch, draft flag and state from that answer, none from the event payload, which is a copy from the time of the review that a re-run of the job reuses. The payload SHALL give `decide` only what cannot change: the number, the reviewer, the id and the commit of the review, and the default branch.

#### Scenario: The event's copy is not read
- **WHEN** the file is parsed
- **THEN** the `env:` of `decide` holds none of `github.event.pull_request.head.sha`, `github.event.pull_request.base.ref`, `github.event.pull_request.draft` and `github.event.pull_request.state`

### Requirement: Only an open pull request that is not a draft lands
`decide` SHALL write `land=true` only when the `state` in the answer for the pull request is `open` and its `draft` is `false`.

#### Scenario: Closed since the review
- **WHEN** the permission is `write`, the review commit equals the head sha of the answer and the `state` of the answer is `closed` (as for a pull request that was merged, which is closed with `merged: true`)
- **THEN** `decide` writes `land=false`

#### Scenario: A draft since the review
- **WHEN** the permission is `write`, the review commit equals the head sha of the answer and the answer has `draft: true`
- **THEN** `decide` writes `land=false`

### Requirement: Only a review that still approves lands
`decide` SHALL read the review with `GET /repos/<repository>/pulls/<number>/reviews/<review id>` and the job's own token, and SHALL write `land=true` only when its `state` is `APPROVED`, so that an approval dismissed after the event is not landed by a re-run, which reuses the payload's `approved`.

#### Scenario: Dismissed after the event
- **WHEN** the permission is `write`, the answer for the pull request qualifies, the event's copy of the state (still set in the environment) is `approved` and the answer for the review has `state` `DISMISSED`
- **THEN** `decide` writes `land=false`

#### Scenario: Still approved
- **WHEN** the permission is `write`, the answer for the pull request qualifies and the answer for the review has `state` `APPROVED`
- **THEN** `decide` writes `land=true`

### Requirement: Only a reviewer who can write lands
`decide` SHALL write `land=true` only when the permission of the reviewer on the repository is `admin` or `write`, read with `GET /repos/<repository>/collaborators/<reviewer>/permission` and the job's own token. Any other permission, and an answer that cannot be read, SHALL give `land=false`.

#### Scenario: A writer approves the current head
- **WHEN** `decide` runs with the permission `write` (or `admin`) and an answer for the pull request that is open, not a draft, with the head sha equal to the review commit and the base branch equal to the default branch, and an answer for the review with `state` `APPROVED`
- **THEN** it writes `land=true`

#### Scenario: A reader approves
- **WHEN** the permission is `read` or `none`, and the review commit equals the head sha
- **THEN** it writes `land=false`

### Requirement: Only the approved head lands
`decide` SHALL write `land=true` only when the commit the review was made on (`github.event.review.commit_id`) is the head sha in the answer of the API, so that a push after the approval is not landed on its strength, however long after, and also when the job is run again.

#### Scenario: The head moved after the approval
- **WHEN** the permission is `admin` and the review commit differs from the head sha of the answer
- **THEN** `decide` writes `land=false`

#### Scenario: The head moved after the event, in a re-run
- **WHEN** the permission is `write`, the event's copy of the head sha (still set in the environment, as a re-run has it) equals the review commit, and the answer of the API gives another head sha
- **THEN** `decide` writes `land=false`

### Requirement: Only a pull request against the default branch lands
`decide` SHALL write `land=true` only when the base branch in the answer of the API is the default branch of the repository (`github.event.repository.default_branch`; a default branch renamed since the event gives `land=false`, never a landing), so that the commits of a pull request that is based on another branch are not landed with it.

#### Scenario: Based on another branch
- **WHEN** the permission is `write`, the review commit equals the head sha, the base branch of the answer is `feature` and the default branch is `main`
- **THEN** `decide` writes `land=false`

#### Scenario: Retargeted after the event, in a re-run
- **WHEN** the permission is `write`, the review commit equals the head sha, the event's copy of the base branch (still set in the environment) is `main` and the answer of the API gives `feature`
- **THEN** `decide` writes `land=false`

#### Scenario: Based on the default branch
- **WHEN** the permission is `write`, the review commit equals the head sha and the base branch of the answer is `main`, the default branch
- **THEN** `decide` writes `land=true`

### Requirement: Every approval is handled
The workflow SHALL have no `concurrency` key, at the top or in the job, so that every approval gets a run to its end. The order of landings SHALL be the one `land`'s fast-forward push gives: a head that reaches `origin` second is told by the job's comment that the branch moved.

#### Scenario: No concurrency group
- **WHEN** the file is parsed
- **THEN** neither the workflow nor any of its jobs has a `concurrency` key

#### Scenario: The second of two landings is told
- **WHEN** `land` prints the line of a moved branch and exits 1
- **THEN** the job comments that line with the rebase instruction, as for any refusal, and the run stays green

### Requirement: Land runs with the token of the app
The job SHALL create an installation token with `actions/create-github-app-token`, pinned to a full commit sha, from the variable `PREPUSH_CI_APP_ID` and the secret `PREPUSH_CI_APP_KEY`; SHALL check out the default branch with full history and that token; and SHALL run `land` with the pull request number and the token as `GITHUB_TOKEN`. No `run:` SHALL contain `${{`: values reach it through `env:`.

#### Scenario: The token is made from the app's variables
- **WHEN** the file is parsed
- **THEN** a step uses `actions/create-github-app-token@<40 hex>` with `app-id` from `vars.PREPUSH_CI_APP_ID` and `private-key` from `secrets.PREPUSH_CI_APP_KEY`

#### Scenario: Checkout of the default branch
- **WHEN** the file is parsed
- **THEN** the checkout step has `ref` of `github.event.repository.default_branch`, `fetch-depth: 0` and the app token as `token`

#### Scenario: Land gets the number and the token
- **WHEN** the step `land` runs with a stub command that records its arguments and the variable `GITHUB_TOKEN`
- **THEN** the arguments are `land` and the number, and `GITHUB_TOKEN` holds the app token

#### Scenario: Nothing is interpolated into a script
- **WHEN** the file is parsed
- **THEN** no `run:` holds `${{`

### Requirement: The line of land is kept
The step `land` SHALL write the first line of the standard output of `land` to `GITHUB_OUTPUT` as `line`, SHALL have the exit status of `land`, and SHALL have `continue-on-error: true`, so that the run stays green when `land` refuses.

#### Scenario: The line is kept
- **WHEN** `land` runs with a stub that prints `not landed: the branch moved` and exits 1
- **THEN** `GITHUB_OUTPUT` holds `line=not landed: the branch moved` and the step exits 1

#### Scenario: A refusal does not fail the job
- **WHEN** the file is parsed
- **THEN** the step `land` has `continue-on-error: true`

### Requirement: A refusal is told on the pull request
When the step `land` fails, the step `comment` SHALL post one comment on the pull request, with the job's own token and not the app's, that holds the line without backticks in a code block, says what to do for each kind of refusal (rebase onto the default branch and push so that the pre-push hook checks the new tree in the session, then ask for a new approval; or, for a missing variable or tool, change the workflow), and gives the link of the run. A landing SHALL post no comment.

#### Scenario: A refusal is commented
- **WHEN** `comment` runs with the line `not landed: the branch moved` and the branch `main`, and a stub `gh`
- **THEN** the stub received `pr comment <number>` and a body that holds the line, `main`, `rebase`, `pre-push` and `approval`

#### Scenario: A refusal a rebase cannot fix
- **WHEN** `comment` runs with the line `not landed: missing A_URL`
- **THEN** the body holds the line, `workflow` and `env`, so that its text does not leave the author with a rebase as the only answer

#### Scenario: A backtick cannot break out
- **WHEN** the line holds three backticks
- **THEN** the body holds none of them

#### Scenario: Only a failed landing is commented
- **WHEN** the file is parsed
- **THEN** the `if:` of `comment` holds `steps.land.outcome == 'failure'` besides the decision, and the token it uses is `github.token`, never the output of the token step

#### Scenario: A landing is not commented
- **WHEN** the stub of `land` prints `landed: <sha> on main` and exits 0
- **THEN** the step `land` exits 0 and `comment` does not run

### Requirement: The example says what it needs
The leading comment of `docs/ci/land.yml` SHALL say that the file is copied to `.github/workflows/` and that it needs the app of `prepush-ci app setup --land` installed on the repository, the variable `PREPUSH_CI_APP_ID`, the secret `PREPUSH_CI_APP_KEY` and the ruleset of `prepush-ci app ruleset --app`; and that the `land` step needs the `require_env` variables of the config in its `env:` and the job whatever the `preflight` runs.

#### Scenario: What it names
- **WHEN** the leading comment of the file is read
- **THEN** it holds `.github/workflows`, `app setup --land`, `app ruleset --app`, `PREPUSH_CI_APP_ID`, `PREPUSH_CI_APP_KEY` and `require_env`

### Requirement: The example says what it costs
The leading comment of `docs/ci/land.yml` SHALL say that `land` runs the `preflight` of the pull request with the app's token, so that an approval is a decision about that code too, and that anyone who can push to the repository can read the secret and change this workflow, so that the ruleset and the checks of the workflow bind only those who cannot write.

#### Scenario: What it warns of
- **WHEN** the leading comment of the file is read
- **THEN** it holds `preflight` and `anyone who can push`
