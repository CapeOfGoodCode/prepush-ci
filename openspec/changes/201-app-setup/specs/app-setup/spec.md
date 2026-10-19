# app-setup Specification

## Purpose
`prepush-ci app setup`: creates the GitHub App that `report` posts check runs as, through GitHub's manifest flow: one click in the browser, one permission, no server of ours. It saves the app's private key outside the repository and prints what `report` needs.

## ADDED Requirements

### Requirement: Setup serves one page on the loopback address
`prepush-ci app setup` SHALL listen on `127.0.0.1` on a free port, print the address of its page, and open the page with the user's browser (`BROWSER` decides, as in Python's `webbrowser`). The page SHALL post the manifest and a random `state` to `<server>/settings/apps/new`, or with `--org <login>` to `<server>/organizations/<login>/settings/apps/new`; `<server>` is `GITHUB_SERVER_URL` or `https://github.com`.

#### Scenario: Address printed and opened
- **WHEN** `app setup` runs with `BROWSER` set to a script that records its argument
- **THEN** standard output holds an address starting with `http://127.0.0.1:` and the script received that address

#### Scenario: The page posts to GitHub
- **WHEN** the page is fetched with `GITHUB_SERVER_URL` naming a local server
- **THEN** it holds a form whose method is POST, whose action is `<that server>/settings/apps/new?state=<state>` and whose field `manifest` is JSON

#### Scenario: For an organization
- **WHEN** `--org acme` is given
- **THEN** the form's action path is `/organizations/acme/settings/apps/new`

#### Scenario: Only this machine can reach it
- **WHEN** `app setup` is waiting
- **THEN** its listening socket is bound to `127.0.0.1`

### Requirement: The app asks for one permission
The manifest SHALL set `default_permissions` to `checks: write` and nothing else, `default_events` to none and `public` to false, SHALL set `url` (the app's homepage, which GitHub requires) to `https://github.com/CapeOfGoodCode/prepush-ci`, SHALL leave out `hook_attributes`, and SHALL set `redirect_url` to the callback of the page. Its `name` SHALL be `--name`, or `prepush-ci (<owner>)` with the owner of the remote `origin`, read in the forms of "Where the result is posted" in `report`.

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

### Requirement: Names GitHub would refuse are refused first
`app setup` SHALL refuse an empty `--name` and a `--name` of more than 34 characters with exit 2, and a default name of more than 34 characters with exit 1, naming `--name`, before it serves a page or opens a browser.

#### Scenario: Empty name
- **WHEN** `--name ""` is given
- **THEN** it exits 2, the reason names `--name` and no page is served

#### Scenario: Name too long
- **WHEN** `--name` is 35 characters long
- **THEN** it exits 2 and the reason names `--name`

#### Scenario: Owner too long for the default name
- **WHEN** no `--name` is given and the owner of `origin` makes the default name 35 characters long
- **THEN** it exits 1, the reason names `--name` and no page is served

### Requirement: GitHub's answer completes the setup
When GitHub redirects the browser to the callback with the `state` of this run and a `code`, `app setup` SHALL exchange the code with `POST /app-manifests/<code>/conversions` on `GITHUB_API_URL` (default `https://api.github.com`), sending no credential, answer the browser with a page that says to return to the terminal, and stop listening. A callback with another `state` or without a `code` SHALL be answered 400, start no exchange and leave the command waiting.

#### Scenario: Code exchanged
- **WHEN** the callback arrives with the right `state` and the code `c0de`
- **THEN** the API receives `POST /app-manifests/c0de/conversions` without an `Authorization` header and the browser gets a 200 page

#### Scenario: Wrong state
- **WHEN** a callback arrives with another `state` and then one with the right `state`
- **THEN** the first is answered 400, the API receives one conversion request, for the second, and the command exits 0

#### Scenario: Callback without a code
- **WHEN** a callback arrives with the right `state` and no `code`
- **THEN** it is answered 400 and the API receives no request

#### Scenario: Listening stops
- **WHEN** the setup has completed
- **THEN** the port the command printed accepts no connection

#### Scenario: GitHub refuses the code
- **WHEN** the conversion answers 404 with a message
- **THEN** it exits 1, the error names `404` and the message and no key file is written

#### Scenario: The answer is not an app
- **WHEN** the conversion answers 201 with a body that holds no `id`, `slug` or `pem`
- **THEN** it exits 1, the error says the answer is incomplete and no key file is written

### Requirement: The wait ends
`app setup` SHALL stop waiting after `--timeout` seconds (a whole number of 1 or more, default 300), exit 1, say that no answer came from GitHub and write no key file. A `--timeout` that is not a whole number of 1 or more SHALL exit 2 and name the flag before a page is served.

#### Scenario: No callback
- **WHEN** `--timeout 1` is given and no callback arrives
- **THEN** it exits 1 after about a second, the reason says GitHub did not answer and the port accepts no connection

#### Scenario: Malformed timeout
- **WHEN** `--timeout 0` or `--timeout soon` is given
- **THEN** it exits 2, the reason names `--timeout` and no page is served

### Requirement: The key is saved outside the repository
`app setup` SHALL write the app's private key to `<config>/prepush-ci/apps/<id>.pem`, where `<config>` is `XDG_CONFIG_HOME` when it is set and not empty, else `~/.config`. It SHALL create the directories as needed, give the file mode 0600 and its directory mode 0700 where modes exist, and never overwrite a file. When that directory lies inside the worktree of the current directory it SHALL exit 1 before it serves a page.

#### Scenario: Key saved
- **WHEN** the conversion answers app `5401187` with a key
- **THEN** the file `<config>/prepush-ci/apps/5401187.pem` holds that key and, on a system with file modes, has mode 0600

#### Scenario: Default location
- **WHEN** `XDG_CONFIG_HOME` is unset and `HOME` is a temporary directory
- **THEN** the key is saved under that directory's `.config/prepush-ci/apps/`

#### Scenario: Not in the repository
- **WHEN** the setup has completed in a repository
- **THEN** no file in the worktree or its git directory holds the key

#### Scenario: Location inside the worktree
- **WHEN** `XDG_CONFIG_HOME` names a directory inside the worktree
- **THEN** it exits 1, the reason says the key would be saved in the repository and no page is served

#### Scenario: Existing file kept
- **WHEN** `<id>.pem` already exists
- **THEN** it exits 1, the file is unchanged and the reason says the app was created but its key was not saved

### Requirement: Secrets stay out of the output
Neither standard output nor standard error of `app setup` SHALL hold the private key, the `client_secret` or the `webhook_secret` of the answer, and the command SHALL keep the two secrets nowhere.

#### Scenario: Nothing secret printed
- **WHEN** the conversion answers with a key and both secrets and the setup completes, or fails after the answer
- **THEN** none of the three values appears in either output stream

#### Scenario: The secrets are not stored
- **WHEN** the setup has completed
- **THEN** no file under the config directory, the worktree or the temporary directory holds the `client_secret` or the `webhook_secret`

### Requirement: The result names what report needs
After the key is saved `app setup` SHALL exit 0 and print the app's id, the address `<server>/apps/<slug>/installations/new`, the path of the key file and the names `PREPUSH_CI_APP_ID` and `PREPUSH_CI_APP_KEY`. `report` run with that id and the saved key SHALL post a check run.

#### Scenario: What is printed
- **WHEN** the conversion answers app `5401187`, slug `prepush-ci-acme`
- **THEN** standard output holds `5401187`, `/apps/prepush-ci-acme/installations/new`, the key's path, `PREPUSH_CI_APP_ID` and `PREPUSH_CI_APP_KEY`

#### Scenario: Report uses the printed values
- **WHEN** the conversion answers a generated RSA key and then `prepush-ci report --result passed` runs with `PREPUSH_CI_APP_ID` set to the id and `PREPUSH_CI_APP_KEY` to the text of the saved file, against a local API that holds the public key
- **THEN** the API receives a bearer token whose signature verifies and a check run is created

### Requirement: The exit status says whether the app was created
`app setup` SHALL exit 0 when the app was created and its key saved, 2 when the command line is rejected (an unknown flag, a malformed value) and 1 in every other case; a rejected command line SHALL serve no page.

#### Scenario: Unknown flag
- **WHEN** `prepush-ci app setup --frob` runs
- **THEN** it exits 2, names the flag and serves no page

#### Scenario: Help
- **WHEN** `prepush-ci app setup --help` runs
- **THEN** it exits 0 and lists `--org`, `--name` and `--timeout`

#### Scenario: No subcommand
- **WHEN** `prepush-ci app` runs
- **THEN** it exits 2 and names `setup`
