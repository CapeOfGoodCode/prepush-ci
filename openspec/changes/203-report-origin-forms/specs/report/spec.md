## MODIFIED Requirements

### Requirement: Where the result is posted
`report` SHALL post to the GitHub repository named by the URL of the remote `origin` as `git remote get-url origin` prints it, in the forms `https://[<userinfo>@]<host>/<owner>/<repo>[.git]`, `ssh://[<user>@]<host>[:<port>]/<owner>/<repo>[.git]` and `git@<host>:<owner>/<repo>[.git]`, with `github.com` or `ssh.github.com` as `<host>`; the userinfo SHALL be ignored. When no repository can be read from `origin`, the environment SHALL name it (next requirement).

#### Scenario: HTTPS remote
- **WHEN** `origin` is `https://github.com/acme/widgets.git`
- **THEN** the request path holds `/repos/acme/widgets/`

#### Scenario: SSH remote without the suffix
- **WHEN** `origin` is `git@github.com:acme/widgets`
- **THEN** the request path holds `/repos/acme/widgets/`

#### Scenario: Remote with credentials
- **WHEN** `origin` is `https://x-access-token:s3cret@github.com/acme/widgets.git`
- **THEN** the request path holds `/repos/acme/widgets/`

#### Scenario: SSH URL form
- **WHEN** `origin` is `ssh://git@github.com/acme/widgets.git`
- **THEN** the request path holds `/repos/acme/widgets/`

#### Scenario: Repository from the environment
- **WHEN** `origin` is a local path and `GITHUB_REPOSITORY` is `acme/widgets`
- **THEN** the request path holds `/repos/acme/widgets/`

#### Scenario: No origin
- **WHEN** the repository has no remote `origin` and `GITHUB_REPOSITORY` is unset
- **THEN** it exits 1, the reason says no repository could be read from `origin` and no request is sent

#### Scenario: SSH over the HTTPS port
- **WHEN** `origin` is `ssh://git@ssh.github.com:443/acme/widgets.git`, `GITHUB_API_URL` is unset and `GITHUB_REPOSITORY` is unset
- **THEN** the request goes to `https://api.github.com` for `/repos/acme/widgets/`

#### Scenario: A short alias of origin
- **WHEN** the config sets `url.https://github.com/acme/.insteadOf` to `gh:`, `origin` is `gh:widgets`, `GITHUB_API_URL` is unset and `GITHUB_REPOSITORY` is unset
- **THEN** the request goes to `https://api.github.com` for `/repos/acme/widgets/`

#### Scenario: A push-only rewrite is ignored
- **WHEN** `origin` is `https://github.com/acme/widgets.git` and the config sets `url.https://github.com/fork/.pushInsteadOf` to `https://github.com/acme/`
- **THEN** the request path holds `/repos/acme/widgets/` and not `/repos/fork/`

#### Scenario: An ssh host alias
- **WHEN** `origin` is `git@github.com-work:acme/widgets.git`, `GITHUB_API_URL` is unset and `GITHUB_REPOSITORY` is unset
- **THEN** it exits 1, the reason says no repository could be read from `origin` and no request is sent

#### Scenario: An ssh host alias with a repository name
- **WHEN** `origin` is `git@github.com-work:acme/widgets.git`, `GITHUB_API_URL` is unset and `GITHUB_REPOSITORY` is `acme/widgets`
- **THEN** the request goes to `https://api.github.com` for `/repos/acme/widgets/`

#### Scenario: A host that only starts like GitHub's
- **WHEN** `origin` is `https://ssh.github.com.example.test/acme/widgets.git`, `GITHUB_API_URL` is unset and `GITHUB_REPOSITORY` is unset
- **THEN** it exits 1 and no request is sent

### Requirement: The API address
`report` SHALL send its requests to the address in `GITHUB_API_URL` or, when it is unset or empty, to `https://api.github.com`. A host other than `github.com` or `ssh.github.com` in the URL of `origin` SHALL count only when `GITHUB_API_URL` is set and non-empty.

#### Scenario: Another API address
- **WHEN** `GITHUB_API_URL` is the address of a local server and `origin` is `https://git.example.test/acme/widgets.git`
- **THEN** the request goes to that server for `/repos/acme/widgets/`

#### Scenario: A host without an API address
- **WHEN** `origin` is `https://git.example.test/acme/widgets.git`, `GITHUB_API_URL` is unset and `GITHUB_REPOSITORY` is unset
- **THEN** it exits 1 and no request is sent

#### Scenario: Empty API address
- **WHEN** `GITHUB_API_URL` is empty, `GITHUB_REPOSITORY` is unset and `origin` is `https://git.example.test/acme/widgets.git`
- **THEN** it exits 1 and no request is sent
