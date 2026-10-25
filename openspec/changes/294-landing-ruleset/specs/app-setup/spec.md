## REMOVED Requirements

### Requirement: The app asks for one permission
**Reason**: With `--land` the app asks for four permissions, and its name is a rule of its own; both go to new requirements so each stays short.
**Migration**: "The app asks for its permissions" holds the manifest rules and their scenarios; "The app's name" holds the name rules and their scenarios.

## ADDED Requirements

### Requirement: The app asks for its permissions
The manifest SHALL set `default_permissions` to `checks: write` and nothing else, or with `--land` to the four permissions of "The landing app", `default_events` to none and `public` to false, SHALL set `url` (the app's homepage, which GitHub requires) to `https://github.com/CapeOfGoodCode/prepush-ci`, SHALL leave out `hook_attributes`, and SHALL set `redirect_url` to the callback of the page.

#### Scenario: One permission
- **WHEN** the manifest is read from the page
- **THEN** `default_permissions` equals `{"checks": "write"}` exactly

#### Scenario: A homepage
- **WHEN** the manifest is read from the page
- **THEN** `url` is `https://github.com/CapeOfGoodCode/prepush-ci`

#### Scenario: No webhook, no events, not public
- **WHEN** the manifest is read from the page
- **THEN** the manifest has no `hook_attributes`, `default_events` is empty and `public` is false

#### Scenario: Redirect to the page's own server
- **WHEN** the manifest is read from the page
- **THEN** `redirect_url` is an address on the `127.0.0.1` port the command printed

### Requirement: The app's name
The manifest `name` SHALL be `--name`, or `prepush-ci (<owner>)` with the owner of the remote `origin`, read in the forms of "Where the result is posted" in `report`.

#### Scenario: Default name
- **WHEN** `origin` is `https://github.com/acme/widgets.git` and no `--name` is given
- **THEN** the manifest's `name` is `prepush-ci (acme)`

#### Scenario: Default name from an ssh remote
- **WHEN** `origin` is `git@github.com:acme/widgets.git` and no `--name` is given
- **THEN** the manifest's `name` is `prepush-ci (acme)`

#### Scenario: A name with characters HTML treats specially
- **WHEN** `--name 'A "b" <c> & d'` is given and the page is fetched
- **THEN** the form's `manifest` field, read as JSON, has the `name` `A "b" <c> & d`

#### Scenario: Chosen name
- **WHEN** `--name "Acme checks"` is given
- **THEN** the manifest's `name` is `Acme checks`

#### Scenario: No owner to name the app after
- **WHEN** the repository has no `origin` that names an owner and `--name` is not given
- **THEN** it exits 1, the reason names `--name` and no page is served


### Requirement: The landing app
`app setup --land` SHALL set `default_permissions` to `checks: write`, `contents: write`, `pull_requests: read` and `workflows: write` and nothing else (`workflows: write` because GitHub refuses an app's push of a change under `.github/workflows/` without it).

#### Scenario: More permissions with the flag
- **WHEN** `--land` is given and the manifest is read from the page
- **THEN** `default_permissions` equals `{"checks": "write", "contents": "write", "pull_requests": "read", "workflows": "write"}` exactly and `public` is false

### Requirement: The landing app names the next step
After the lines of "The result names what report needs", `app setup --land` SHALL print the command `prepush-ci app ruleset --app <id>` with the id of the new app and say it works once the app is installed on the repository. Without `--land` the output SHALL hold no such command.

#### Scenario: The next step is printed
- **WHEN** `--land` is given and the conversion answers app `5401187`
- **THEN** standard output holds `prepush-ci app ruleset --app 5401187` and the word `installed`

#### Scenario: No next step without the flag
- **WHEN** `app setup` completes without `--land`
- **THEN** standard output holds no `app ruleset`

### Requirement: The ruleset command takes one bypass actor
`prepush-ci app ruleset` SHALL require exactly one of `--admin` (the repository-admin role may bypass) and `--app <id>` (the app with that id may bypass; `<id>` a whole number of 1 or more), and SHALL otherwise exit 2, name the flags and send no request. Its `--help` SHALL list both flags and say that a private repository needs a paid plan for rulesets.

#### Scenario: Neither flag
- **WHEN** `app ruleset` runs without a flag
- **THEN** it exits 2, the reason names `--admin` and `--app` and the API receives no request

#### Scenario: Both flags
- **WHEN** `--admin --app 5401187` is given
- **THEN** it exits 2 and the API receives no request

#### Scenario: A malformed id
- **WHEN** `--app 0` or `--app slug` is given
- **THEN** it exits 2, the reason names `--app` and the API receives no request

#### Scenario: Help
- **WHEN** `prepush-ci app ruleset --help` runs
- **THEN** it exits 0, lists `--admin` and `--app` and mentions a paid plan for a private repository

### Requirement: The token and the repository
`app ruleset` SHALL send the value of `GITHUB_TOKEN`, or of `GH_TOKEN` when that is unset or empty, as a bearer token to `GITHUB_API_URL` (default `https://api.github.com`), and SHALL name the repository as `report` does ("Where the result is posted"): from `origin`, or from `GITHUB_REPOSITORY` when `origin` names none. Without a token, or without a repository from either, it SHALL exit 1 and send no request.

#### Scenario: Token from the environment
- **WHEN** `GITHUB_TOKEN` is `t0k`, `origin` is `https://github.com/acme/widgets.git` and `GITHUB_REPOSITORY` is unset
- **THEN** the API receives its requests for `/repos/acme/widgets/rulesets` with `Authorization: Bearer t0k`

#### Scenario: Token from GH_TOKEN
- **WHEN** `GITHUB_TOKEN` is unset and `GH_TOKEN` is `t0k`
- **THEN** the requests carry `Bearer t0k`

#### Scenario: No token
- **WHEN** neither variable is set and `origin` names a repository
- **THEN** it exits 1, the reason names `GITHUB_TOKEN` and `GH_TOKEN` and the API receives no request

#### Scenario: No repository
- **WHEN** the repository has no `origin` and `GITHUB_REPOSITORY` is unset
- **THEN** it exits 1 and the API receives no request

#### Scenario: Repository from the environment
- **WHEN** `origin` is a local path and `GITHUB_REPOSITORY` is `acme/widgets`
- **THEN** the API receives its requests for `/repos/acme/widgets/rulesets`

#### Scenario: Origin wins
- **WHEN** `origin` is `https://github.com/acme/widgets.git` and `GITHUB_REPOSITORY` is `other/thing`
- **THEN** the API receives its requests for `/repos/acme/widgets/rulesets`

### Requirement: The ruleset
`app ruleset` SHALL create one branch ruleset with `POST /repos/<owner>/<repo>/rulesets`, named `prepush-ci landing`, with `enforcement` `active`, the condition `ref_name` that includes `~DEFAULT_BRANCH` and excludes nothing, and exactly the rules `update`, `non_fast_forward` and `deletion`, each without parameters.

#### Scenario: No pull request rule
- **WHEN** the request is read
- **THEN** the name is `prepush-ci landing`, `enforcement` is `active`, the rules are exactly the three, and none has the type `pull_request`, `required_status_checks` or `creation`

### Requirement: The bypass actor
The `bypass_actors` of the ruleset SHALL hold exactly one entry with `bypass_mode` `always`: `{"actor_id": 5, "actor_type": "RepositoryRole"}` for `--admin`, `{"actor_id": <id>, "actor_type": "Integration"}` for `--app <id>`.

#### Scenario: The admin role
- **WHEN** `--admin` is given and the API has no ruleset
- **THEN** the API receives one `POST` whose body has the name `prepush-ci landing`, the three rules and one bypass actor, `RepositoryRole` 5

#### Scenario: An app
- **WHEN** `--app 5401187` is given
- **THEN** the body's only bypass actor is `Integration` 5401187 and the rules are the same three

### Requirement: A ruleset that exists is kept
Before it creates the ruleset `app ruleset` SHALL list the rulesets of the repository, and when one is named `prepush-ci landing` it SHALL exit 1, create nothing, change nothing and say to delete that ruleset in the repository's settings and run the command again.

#### Scenario: Already there
- **WHEN** the listing holds a ruleset named `prepush-ci landing`
- **THEN** it exits 1, the API receives no `POST`, no `PUT` and no `DELETE`, and the reason names the ruleset

#### Scenario: Another ruleset is no obstacle
- **WHEN** the listing holds only a ruleset named `main`
- **THEN** the ruleset is created

### Requirement: What the command prints
After GitHub answers 201 `app ruleset` SHALL exit 0 and print the ruleset's `id` and the address of its page (the `html` link of the answer), say which bypass actor it lists, and name `prepush-ci doctor --ruleset` as the way to check it later. It SHALL print the token nowhere.

#### Scenario: Printed
- **WHEN** the API answers 201 with id `24893178` for `--admin`
- **THEN** standard output holds `24893178`, the address of the page, the words `admin` and `doctor --ruleset`

#### Scenario: The token stays out
- **WHEN** the command succeeds or fails after the answer
- **THEN** the token appears in neither output stream

### Requirement: GitHub's refusal is reported
When the listing or the creation is not answered with success, `app ruleset` SHALL exit 1 and print the status and GitHub's message. After a 403 it SHALL also say that a private repository needs a paid plan for rulesets and that the token needs administration rights on the repository. It SHALL NOT retry.

#### Scenario: Not allowed
- **WHEN** the creation is answered 403 with the message `Upgrade to GitHub Pro or make this repository public to enable this feature.`
- **THEN** it exits 1, the error holds `403` and that message, and names a paid plan and administration rights

#### Scenario: Not found
- **WHEN** the listing is answered 404
- **THEN** it exits 1, the error holds `404` and the API received no `POST`

### Requirement: The exit status of the ruleset command
`app ruleset` SHALL exit 0 when the ruleset was created, 2 when the command line is rejected and 1 in every other case; a rejected command line SHALL send no request.

#### Scenario: Created
- **WHEN** the API answers 201
- **THEN** it exits 0

#### Scenario: Unknown flag
- **WHEN** `app ruleset --frob` runs
- **THEN** it exits 2, names the flag and sends no request
