## MODIFIED Requirements

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

## ADDED Requirements

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
