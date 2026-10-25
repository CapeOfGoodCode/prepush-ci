## MODIFIED Requirements

### Requirement: The report
`prepush-ci doctor` SHALL run six checks in this order and print one line for each: `config`, `commit-msg`, `pre-push`, `preflight`, `PREPUSH_CI`, `up-to-date`; with `--ruleset` it SHALL run a seventh, `ruleset`, after them ("The ruleset check reads the ruleset"). A line SHALL start with `ok`, `fail` or `skip`, then the check's name and a colon. A failed check SHALL NOT stop the later ones.

#### Scenario: Everything is set up
- **WHEN** the config is valid, `install` ran, `PREPUSH_CI` is `full` and the remote `origin` has the branch `main`
- **THEN** `doctor` exits 0, prints six lines that start with `ok` in the order above and a last line saying all checks passed

#### Scenario: Nothing is set up
- **WHEN** `doctor` runs in a repository without config or hooks
- **THEN** it exits 1 and prints six lines in the order above, the `config`, `commit-msg` and `pre-push` lines starting with `fail`

#### Scenario: A failure does not stop the later checks
- **WHEN** the config is invalid and the hooks are installed
- **THEN** the `config` line starts with `fail`, the `commit-msg` and `pre-push` lines start with `ok` and the exit status is 1

#### Scenario: Seven checks
- **WHEN** `--ruleset` is given
- **THEN** the output holds seven check lines, the seventh named `ruleset` after `up-to-date`, and without the flag the output holds six

### Requirement: The closing line and the exit status
The last line SHALL say that all checks passed or how many of the checks it ran (six, or seven with `--ruleset`) did not, counting every line that does not start with `ok`, `skip` included. The exit status SHALL be 0 only when every line starts with `ok`, otherwise 1.

#### Scenario: The last line counts
- **WHEN** the hooks are installed, the config is valid, `PREPUSH_CI` is `foo` and the remote `origin` is unreachable
- **THEN** the last line says that 2 of 6 checks did not pass

## ADDED Requirements

### Requirement: The ruleset check reads the ruleset
With `--ruleset`, `doctor` SHALL read the repository as `app ruleset` does ("The token and the repository": `origin`, then `GITHUB_REPOSITORY`) and send `GET /repos/<owner>/<repo>/rulesets` and then `GET` of the ruleset named `prepush-ci landing`, with the token and API address of `app ruleset`, and no other request. When it cannot read the ruleset, the line SHALL start with `fail` and say why; a missing ruleset has the fix `prepush-ci app ruleset`.

#### Scenario: Missing
- **WHEN** the listing holds no ruleset named `prepush-ci landing`
- **THEN** the line starts with `fail`, says the ruleset is missing and the fix contains `prepush-ci app ruleset`

#### Scenario: A token that cannot see the actors
- **WHEN** the answer for the ruleset has no `bypass_actors`
- **THEN** the line starts with `fail`, says the token needs administration rights to read the bypass actors and the check does not pass

#### Scenario: No token
- **WHEN** no token is set and `origin` names a repository
- **THEN** the line starts with `fail`, names `GITHUB_TOKEN` and no request is sent

#### Scenario: No repository
- **WHEN** `origin` names no repository and `GITHUB_REPOSITORY` is unset
- **THEN** the line starts with `fail`, says no repository could be read from `origin` and no request is sent

#### Scenario: Repository from the environment
- **WHEN** `origin` is a local path and `GITHUB_REPOSITORY` is `acme/widgets`
- **THEN** the first request is for `/repos/acme/widgets/rulesets`

#### Scenario: GitHub refuses
- **WHEN** the listing is answered 403 or 404
- **THEN** the line starts with `fail` and holds the status

#### Scenario: Nothing is changed
- **WHEN** the check runs
- **THEN** the API received only `GET` requests and no file of the repository changed

### Requirement: The ruleset check passes only for the landing ruleset
The `ruleset` check SHALL pass only when the ruleset is active, targets branches, includes `~DEFAULT_BRANCH` and excludes nothing, and has exactly the rules `update`, `non_fast_forward` and `deletion`; `update` has no parameters or `update_allows_fetch_and_merge` `false`, the others no parameters. A failure SHALL say which of these does not hold, and its fix SHALL name the settings address of the ruleset.

#### Scenario: Not active
- **WHEN** the ruleset's `enforcement` is `evaluate` or `disabled`
- **THEN** the line starts with `fail` and names the enforcement

#### Scenario: Not a branch ruleset
- **WHEN** the ruleset's `target` is `tag`
- **THEN** the line starts with `fail` and names the target

#### Scenario: The default branch is not included
- **WHEN** `ref_name.include` holds only `refs/heads/dev`
- **THEN** the line starts with `fail` and names `~DEFAULT_BRANCH`

#### Scenario: A branch is excluded
- **WHEN** `ref_name.exclude` holds `refs/heads/main` or `~DEFAULT_BRANCH`
- **THEN** the line starts with `fail` and names the excluded ref

#### Scenario: A rule too many or too few
- **WHEN** the ruleset also has the rule `pull_request`, or lacks `deletion`
- **THEN** the line starts with `fail` and names that rule

#### Scenario: A rule with parameters
- **WHEN** the rule `update` carries `{"update_allows_fetch_and_merge": true}`
- **THEN** the line starts with `fail` and names `update`

#### Scenario: A parameter that changes nothing
- **WHEN** the rule `update` carries `{"update_allows_fetch_and_merge": false}` and the rest is as `app ruleset` creates it
- **THEN** the line starts with `ok`

### Requirement: The ruleset check passes only for one bypass actor that can push
The `ruleset` check SHALL also pass only when the ruleset lists exactly one bypass actor, with `bypass_mode` `always` (an actor without `bypass_mode` counts as `always`, GitHub's default): the role `RepositoryRole` 5 or one `Integration`, which SHALL be the app `PREPUSH_CI_APP_ID` names when that is set and not empty. A failure SHALL say which of these does not hold, and its fix SHALL name the settings address of the ruleset.

#### Scenario: Admin role
- **WHEN** the ruleset is as `app ruleset --admin` creates it
- **THEN** the `ruleset` line starts with `ok` and names the admin role

#### Scenario: The app
- **WHEN** the ruleset is as `app ruleset --app 5401187` creates it and `PREPUSH_CI_APP_ID` is `5401187`
- **THEN** the line starts with `ok` and names `5401187`

#### Scenario: An app with the variable unset
- **WHEN** the ruleset is as `app ruleset --app 5401187` creates it and `PREPUSH_CI_APP_ID` is unset
- **THEN** the line starts with `ok` and names `5401187`

#### Scenario: Another app
- **WHEN** the only bypass actor is the `Integration` 99 and `PREPUSH_CI_APP_ID` is `5401187`
- **THEN** the line starts with `fail` and names `99` and `5401187`

#### Scenario: Another bypass actor
- **WHEN** the ruleset lists the admin role and a `Team`
- **THEN** the line starts with `fail`, names the `Team` and the fix names the settings address

#### Scenario: An actor without a bypass mode
- **WHEN** the one bypass actor has no `bypass_mode` and the rest is as `app ruleset --admin` creates it
- **THEN** the line starts with `ok`

#### Scenario: The actor can only bypass by pull request
- **WHEN** the one bypass actor has `bypass_mode` `pull_request`
- **THEN** the line starts with `fail` and names `always`

#### Scenario: An actor exempt from the audit
- **WHEN** the one bypass actor has `bypass_mode` `exempt`
- **THEN** the line starts with `fail` and names `always`

### Requirement: The flag is the only way to the ruleset check
Without `--ruleset`, `doctor` SHALL send no request to the GitHub API and print no `ruleset` line. A command line `doctor` does not know SHALL exit 2 as before.

#### Scenario: No request without the flag
- **WHEN** `doctor` runs against a local API
- **THEN** the API receives no request and the output has no `ruleset` line
