# post-push-hook Specification

## Purpose
What `prepush-ci hook post-push` does after an agent's command: recognizes a `git push` that landed a trailer commit with a recorded pass, and creates or updates the one comment of the check on the pull request of the branch, over the REST API only; when it stays silent, and why it exits 0 in every case.

## Requirements

### Requirement: The hook reads the payload and never fails
`prepush-ci hook post-push` SHALL read one JSON object from standard input, as a Claude Code `PostToolUse` hook gets it, and use its `tool_name`, `tool_input.command` and `cwd` (default: its own working directory). It SHALL do nothing, print nothing and send no request unless `tool_name` is `Bash` and the command is a string. It SHALL exit 0 in every case and write nothing to the repository.

#### Scenario: Not JSON
- **WHEN** standard input holds `not json`
- **THEN** it exits 0, prints nothing on either stream and sends no request

#### Scenario: Empty input
- **WHEN** standard input is empty
- **THEN** it exits 0, prints nothing on either stream and sends no request

#### Scenario: Another tool
- **WHEN** the payload has `tool_name` `Edit`, and the command it holds would be a push
- **THEN** it exits 0, prints nothing and sends no request

#### Scenario: The command is not a string
- **WHEN** the payload has `tool_name` `Bash` and a `tool_input.command` that is a number
- **THEN** it exits 0, prints nothing and sends no request

#### Scenario: Help
- **WHEN** `prepush-ci hook post-push --help` runs
- **THEN** it exits 0

### Requirement: A push is recognized from the command
A command line SHALL be split into commands at `;`, `&`, `&&`, `|`, `||`, `(`, `)`, backticks and line breaks, a quoted word staying whole, so that a separator inside quotes separates nothing. It SHALL count as a push when some command, once leading `NAME=value` words and the words that run another command are skipped, is `git`, then any of `-C <path>`, `-c <key=value>` and options that start with `--`, then `push`. A line that cannot be split (an unclosed quote) SHALL not count as a push.

#### Scenario: A plain push
- **WHEN** the command is `git push`
- **THEN** it counts as a push

#### Scenario: A push with arguments
- **WHEN** the command is `git push -u origin feat/x`
- **THEN** it counts as a push

#### Scenario: A push after another command
- **WHEN** the command is `cd sub && git push`, or `git commit -m x; git push`, or the two lines `git commit -m x` and `git push`
- **THEN** it counts as a push

#### Scenario: Options of git before the subcommand
- **WHEN** the command is `git -C sub push`, `git -c push.default=current push` or `git --no-pager push`
- **THEN** it counts as a push

#### Scenario: Variables before git
- **WHEN** the command is `GIT_SSH_COMMAND=ssh git push`
- **THEN** it counts as a push

#### Scenario: A push in a pipeline
- **WHEN** the command is `git push 2>&1 | tail -3`
- **THEN** it counts as a push

#### Scenario: A push in a subshell
- **WHEN** the command is `(git push)`, `(cd sub && git push) 2>&1 | tail -3` or `(time git push --force-with-lease) 2>&1 | tail -25`
- **THEN** it counts as a push

#### Scenario: A push in a command substitution
- **WHEN** the command is `echo $(git push)` or ``echo `git push` ``
- **THEN** it counts as a push

#### Scenario: Another git command
- **WHEN** the command is `git status`, `git stash push`, `git log --grep push` or `git pull`
- **THEN** it does not count as a push

#### Scenario: Words that only contain push
- **WHEN** the command is `echo git push`, `git pushall` or `git commit -m "fix; git push"`
- **THEN** it does not count as a push

#### Scenario: Parentheses inside quotes
- **WHEN** the command is `git commit -m "fix (git push)"`
- **THEN** it does not count as a push

#### Scenario: A command that cannot be read
- **WHEN** the command is `git push "origin`
- **THEN** it does not count as a push

### Requirement: A push that sends nothing or removes a ref is not one
A command that has `--dry-run`, `-n`, `--delete` or `-d` among its words after `push` SHALL not count as a push, whatever else that command holds; another command of the line can still be one.

#### Scenario: A dry run
- **WHEN** the command is `git push --dry-run`, or `git push -n origin main`
- **THEN** it does not count as a push

#### Scenario: A deletion
- **WHEN** the command is `git push origin --delete old`, or `git push -d origin old`
- **THEN** it does not count as a push

#### Scenario: Another command of the line pushes
- **WHEN** the command is `git push --dry-run && git push`
- **THEN** it counts as a push

### Requirement: The hook acts for a landed push
When the command is a push, the hook SHALL act only if, in the worktree that contains `cwd`, a branch is checked out and `refs/remotes/origin/<branch>` is `HEAD`, which shows that a push to `origin` landed the commit. Otherwise it SHALL do nothing, print nothing and send no request.

#### Scenario: A pushed trailer commit
- **WHEN** a commit with the trailer was pushed with `git push origin main` and the payload's command is that push
- **THEN** the hook goes on to look for the pull request of `main`

#### Scenario: Not a push
- **WHEN** the command is `git status` in a repository where all the rest holds
- **THEN** it prints nothing and sends no request

#### Scenario: Detached HEAD
- **WHEN** the command is a push and `HEAD` is detached
- **THEN** it prints nothing and sends no request

#### Scenario: The push did not land
- **WHEN** the command is `git push origin main || true`, the push was refused and `refs/remotes/origin/main` is not `HEAD`
- **THEN** it prints nothing and sends no request

#### Scenario: Pushed under another name
- **WHEN** the command is `git push origin HEAD:other`, so that `refs/remotes/origin/<branch>` is not `HEAD`
- **THEN** it prints nothing and sends no request

#### Scenario: Run from a subdirectory or another worktree
- **WHEN** the payload's `cwd` is a subdirectory of the worktree, or the root of a linked worktree whose branch was pushed
- **THEN** the hook acts on that worktree's `HEAD` as from its root

#### Scenario: Outside a worktree
- **WHEN** `cwd` is not inside a git worktree
- **THEN** it prints nothing and sends no request

### Requirement: The hook acts for a commit that demands the check
The hook SHALL act only if `HEAD` demands the check, that is, it carries a trailer that "A tip demands the check when it carries the trailer" and "Which config decides the demand" of the `pre-push-hook` capability count, and the config committed in `HEAD` is valid. Otherwise it SHALL do nothing, print nothing and send no request.

#### Scenario: A commit without the trailer
- **WHEN** the command is a push and the commit at `HEAD` has no trailer
- **THEN** it prints nothing and sends no request

#### Scenario: A configured key
- **WHEN** the config sets `trailer = { key = "Full-Check", value = "yes" }` and the pushed `HEAD` carries `Full-Check: yes`
- **THEN** the hook goes on to look for the pull request

#### Scenario: A legacy key
- **WHEN** the config sets `legacy_keys = ["Full-Pre-Push"]` and the pushed `HEAD` carries `Full-Pre-Push: required`
- **THEN** the hook goes on to look for the pull request

#### Scenario: No config in the commit
- **WHEN** `HEAD` holds neither `.prepush-ci.toml` nor a `[tool.prepush-ci]` table in `pyproject.toml`
- **THEN** it prints nothing and sends no request

#### Scenario: Config in pyproject.toml
- **WHEN** `HEAD` holds a `[tool.prepush-ci]` table and no `.prepush-ci.toml`, and the rest holds
- **THEN** the hook goes on to look for the pull request

#### Scenario: Invalid config in the commit
- **WHEN** the config committed in `HEAD` contains an unknown key
- **THEN** it prints nothing and sends no request

### Requirement: Only a recorded pass is shown
The hook SHALL act only when the run cache holds a pass for the tree of `HEAD`: a ref under `refs/prepush-ci/results/` whose name starts with that tree's hash and `-` (the key of the `run-cache` capability, less the preflight's output, which the hook does not run). Otherwise it SHALL do nothing, print nothing and send no request. A push that skipped the pre-push hook leaves no such ref, and with `cache = false` none is ever recorded, so nothing is shown for either.

#### Scenario: The hook recorded a pass
- **WHEN** `git push origin main` passed the check in the pre-push hook and the payload's command is that push
- **THEN** the hook goes on to look for the pull request

#### Scenario: The hook was bypassed
- **WHEN** a trailer commit was pushed with `git push --no-verify origin main` and no result ref exists for its tree
- **THEN** it prints nothing and sends no request

#### Scenario: Another hooks path
- **WHEN** a trailer commit was pushed with `git -c core.hooksPath=/dev/null push origin main` and no result ref exists for its tree
- **THEN** it prints nothing and sends no request

#### Scenario: The cache is off
- **WHEN** the config sets `cache = false` and a trailer commit was pushed
- **THEN** it prints nothing and sends no request

#### Scenario: A pass for another tree
- **WHEN** the only result ref is for the tree of an earlier commit
- **THEN** it prints nothing and sends no request

#### Scenario: A pass for the same tree
- **WHEN** a pass was recorded for a commit, the commit was amended with a new message (the tree is unchanged) and pushed with `--no-verify`
- **THEN** the hook goes on to look for the pull request

### Requirement: The pull request of the branch
The hook SHALL find the repository and the API address as `report` does (its requirements "Where the result is posted", "The repository from the environment" and "The API address"); when it cannot, it SHALL do nothing, silently. It SHALL ask `GET /repos/<owner>/<repo>/pulls?state=open&head=<owner>:<branch>&per_page=100`, `<owner>` being the owner of the repository, and use the first pull request answered. With none, it SHALL do nothing, print nothing and send no further request.

#### Scenario: A pull request exists
- **WHEN** the push landed on branch `feat/x`, `origin` is `https://github.com/acme/widgets.git` and the stub API answers the pulls request with one pull request, number 7
- **THEN** the request was `GET /repos/acme/widgets/pulls` with `state=open` and `head=acme:feat/x`, and the hook goes on to the comments of issue 7

#### Scenario: No pull request
- **WHEN** the stub API answers the pulls request with an empty list
- **THEN** it exits 0, prints nothing and sends no request to any comments endpoint

#### Scenario: A remote that is not on GitHub
- **WHEN** `origin` is a local path, `GITHUB_REPOSITORY` and `GITHUB_API_URL` are unset
- **THEN** it exits 0, prints nothing and sends no request

#### Scenario: The repository from the environment
- **WHEN** `origin` is a local path, `GITHUB_REPOSITORY` is `acme/widgets` and `GITHUB_API_URL` names the stub
- **THEN** the pulls request goes to the stub for `/repos/acme/widgets/pulls`

### Requirement: The comment is the Markdown of report
The body of the comment SHALL be what `prepush-ci report --markdown --result passed --tree <the tree of HEAD>` prints for `HEAD`: no result files and the default name.

#### Scenario: The text is the markdown of report
- **WHEN** the hook creates a comment for a commit
- **THEN** the body equals the standard output of `prepush-ci report --markdown --result passed --tree <the tree of HEAD>` run in that worktree

#### Scenario: The commit is named
- **WHEN** the hook creates a comment
- **THEN** the body holds the 40-hex sha of `HEAD`

### Requirement: One comment per check, found by its marker
The hook SHALL list the comments of the pull request (`GET /repos/<owner>/<repo>/issues/<number>/comments?per_page=100&page=<n>`, from page 1 while a page holds 100 comments) and take as the check's comment the first whose body starts with the first line of the new body, the marker.

#### Scenario: Another comment that mentions the marker
- **WHEN** a comment holds the marker line in the middle of its body and the check's comment comes after it
- **THEN** the comment whose body starts with the marker is the one found

#### Scenario: The comment is past the first page
- **WHEN** the first page of comments holds 100 comments without the marker and the second holds the comment with it
- **THEN** that comment is the one found

#### Scenario: Another check's comment
- **WHEN** the only comment starts with `<!-- prepush-ci:prepush-ci / unit -->`
- **THEN** it is not the one found

### Requirement: The comment is replaced, left alone or created
The hook SHALL replace the body of the comment found with `PATCH /repos/<owner>/<repo>/issues/comments/<id>`, send no write when that body is the same as the new one, and create the comment with `POST /repos/<owner>/<repo>/issues/<number>/comments` when none was found.

#### Scenario: No comment yet
- **WHEN** the pull request has two comments that do not start with the marker
- **THEN** one `POST` creates a comment whose body starts with `<!-- prepush-ci:prepush-ci / full -->` and no `PATCH` is sent

#### Scenario: The comment is updated
- **WHEN** the pull request has a comment whose body starts with `<!-- prepush-ci:prepush-ci / full -->` and names an earlier commit
- **THEN** one `PATCH` replaces that comment's body with the new text and no comment is created

#### Scenario: The same text is not written again
- **WHEN** the comment with the marker already holds exactly the new body
- **THEN** no `POST` and no `PATCH` is sent

#### Scenario: The updated comment is the one that was found
- **WHEN** a comment holds the marker line in the middle of its body and the check's comment comes after it
- **THEN** only the comment whose body starts with the marker is updated

#### Scenario: Another check's comment is not changed
- **WHEN** the only comment starts with `<!-- prepush-ci:prepush-ci / unit -->`
- **THEN** a new comment is created and that one is not changed

### Requirement: Only the REST API is used
Every request of the hook SHALL go to a REST endpoint of the API address; none SHALL go to `/graphql`. A successful run SHALL print nothing on standard output.

#### Scenario: Only REST
- **WHEN** the hook runs a whole round against the stub, once creating and once updating a comment
- **THEN** no request went to `/graphql` and standard output is empty

### Requirement: The credentials are the token's, if there is one
The hook SHALL send `Authorization: Bearer <token>` with the value of `GITHUB_TOKEN`, or of `GH_TOKEN` when `GITHUB_TOKEN` is unset or empty, and no `Authorization` header when neither holds a value: a Claude Code cloud session's proxy supplies the credentials for `api.github.com`.

#### Scenario: The token is sent
- **WHEN** `GITHUB_TOKEN` is `t0k` and the hook sends its requests to the stub
- **THEN** every request carries `Authorization: Bearer t0k`

#### Scenario: Token from GH_TOKEN
- **WHEN** `GITHUB_TOKEN` is empty and `GH_TOKEN` is `g0k`
- **THEN** every request carries `Authorization: Bearer g0k`

#### Scenario: No token
- **WHEN** neither variable is set
- **THEN** the requests are sent without an `Authorization` header

### Requirement: The whole run is bounded
The hook SHALL finish within 15 seconds of its start however slow the API is: a request SHALL wait no longer than the time left. When the time runs out it SHALL stop, print one line on standard error that begins with `prepush-ci:` and says it gave up, and exit 0.

#### Scenario: A server that never answers
- **WHEN** the stub accepts the connection of the pulls request and never answers
- **THEN** the hook exits 0 within 20 seconds and standard error holds one line that begins with `prepush-ci:` and says it gave up

#### Scenario: Slow but in time
- **WHEN** the stub answers each request after one second and the round takes three requests
- **THEN** the comment is created and standard error is empty

### Requirement: A failure to post is one line
A request that is answered with a status of 300 or more (a redirect is not followed) or cannot be sent SHALL stop the hook. It SHALL print exactly one line on standard error that begins with `prepush-ci:` and names the status and the message GitHub gave, or the reason the request could not be sent, and still exit 0. The token SHALL appear on neither stream.

#### Scenario: A refused write
- **WHEN** the stub answers the comment's `POST` with 403 and the message `Resource not accessible`
- **THEN** it exits 0 and standard error holds one line that begins with `prepush-ci:` and holds `403` and `Resource not accessible`

#### Scenario: A refused lookup
- **WHEN** the stub answers the pulls request with 401
- **THEN** it exits 0, standard error holds one line with `401` and no comment request is sent

#### Scenario: Server unreachable
- **WHEN** `GITHUB_API_URL` names a port nobody listens on
- **THEN** it exits 0 and standard error holds one line that says the request could not be sent

#### Scenario: A redirect is refused
- **WHEN** the stub answers the pulls request with 301 and a `Location` naming another server
- **THEN** it exits 0, standard error holds one line with `301` and the other server receives no request

#### Scenario: The token stays out of the output
- **WHEN** the stub answers 401 with a body that quotes the bearer token
- **THEN** the token appears on neither standard output nor standard error

### Requirement: A wrapper does not hide a push
The words `time`, `command`, `exec`, `nohup`, `env` and `timeout` SHALL be skipped at the start of a command, each with the options that follow it (words that start with `-`). `env` SHALL also skip its `NAME=value` words and the value of `-u` and `-C`; `timeout` SHALL also skip the value of `-k` and `-s` and then its duration word.

#### Scenario: time
- **WHEN** the command is `time git push` or `time -p git push`
- **THEN** it counts as a push

#### Scenario: env
- **WHEN** the command is `env GIT_SSH_COMMAND=ssh git push`, `env -u HTTP_PROXY git push` or `env -i A=1 git push`
- **THEN** it counts as a push

#### Scenario: timeout
- **WHEN** the command is `timeout 60 git push` or `timeout -k 5 -s INT 60 git push`
- **THEN** it counts as a push

#### Scenario: command, exec and nohup
- **WHEN** the command is `command git push`, `exec git push` or `nohup git push`
- **THEN** it counts as a push

#### Scenario: Wrappers together
- **WHEN** the command is `time env A=1 timeout 60 git push`
- **THEN** it counts as a push

#### Scenario: A wrapper before something else
- **WHEN** the command is `time git status`, `env A=1 git pull` or `timeout 60 echo git push`
- **THEN** it does not count as a push

### Requirement: A shell keyword does not hide a push
The words `!`, `{`, `if`, `elif`, `while`, `until`, `then`, `else` and `do` SHALL be skipped at the start of a command.

#### Scenario: A push after a keyword
- **WHEN** the command is `if git push; then echo ok; fi`, `{ git push; }`, `! git push` or `for b in a b; do git push origin $b; done`
- **THEN** it counts as a push

#### Scenario: A keyword inside a command
- **WHEN** the command is `echo then git push`
- **THEN** it does not count as a push

### Requirement: A shell started with -c is read
A command whose first word, after the skipped words, is `sh`, `bash` or `zsh` SHALL be read through its script: the word after the first option made of one `-` and letters that holds `c`, every option before it starting with `-`. The script SHALL be read as a command line of its own, and the command counts as a push when the script does.

#### Scenario: A script with a push
- **WHEN** the command is `bash -c "git push"`, `sh -c 'cd sub && git push'` or `zsh -c "bash -c 'git push'"`
- **THEN** it counts as a push

#### Scenario: Options before the script
- **WHEN** the command is `bash -lc "git push"` or `bash -e -c "git push"`
- **THEN** it counts as a push

#### Scenario: A script that only mentions push
- **WHEN** the command is `sh -c "echo git push"` or `bash -c "git status"`
- **THEN** it does not count as a push

#### Scenario: A shell without a script
- **WHEN** the command is `bash script.sh git push` or `bash -c`
- **THEN** it does not count as a push

### Requirement: Forms that are not recognized
A push SHALL not be recognized when it is inside a command substitution within double quotes, or run through `eval`, `xargs`, `sudo`, `ssh`, an alias or function defined outside the command line, or a script. The README of `hook post-push` SHALL name the forms recognized and these.

#### Scenario: Not recognized
- **WHEN** the command is `echo "$(git push)"`, `eval "git push"`, `sudo git push`, `echo origin | xargs git push`, `p` (an alias of `git push` defined earlier) or `./push.sh`
- **THEN** it does not count as a push

#### Scenario: A function defined on the line
- **WHEN** the command is `f() { git push; }; f` or `f() ( git push ); f`
- **THEN** it counts as a push

#### Scenario: The README names them
- **WHEN** the README section of `hook post-push` is read
- **THEN** it names `time`, `env`, `bash -c` and a subshell as recognized, and `eval`, `xargs`, `sudo` and an alias or function defined outside the command line as not

### Requirement: A wrapped push updates the comment
A push that is recognized from a wrapped command SHALL be handled like a plain one: the landing, the trailer, the recorded pass and the comment are decided by the other requirements.

#### Scenario: A wrapped push updates the comment
- **WHEN** an amended trailer commit with a recorded pass was force-pushed, the payload's command is `(time git push --force-with-lease) 2>&1 | tail -25`, and the comment of the check names the earlier commit
- **THEN** one `PATCH` replaces that comment's body with the text for the new `HEAD`

#### Scenario: A wrapped push that did not land
- **WHEN** the payload's command is `(time git push origin main) 2>&1 | tail` and `refs/remotes/origin/main` is not `HEAD`
- **THEN** it prints nothing and sends no request
