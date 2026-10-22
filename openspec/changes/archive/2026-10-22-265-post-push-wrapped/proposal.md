Issue: #265

## Why

An agent often wraps its push: `(time git push --force-with-lease) 2>&1 | tail -25`, `env GIT_SSH_COMMAND=… git push`, `bash -c "git push"`. The post-push hook (#246) does not recognize those, stays silent, and the pull request comment keeps showing the result of the previous commit, so a reviewer reads a pass for code that is no longer the head. Found in the final trial of `f815b8d` in a Claude Code cloud session; the owner wants it fixed before 0.2.0 (#227).

## What Changes

- A command line is also split at `(`, `)` and backticks, so a subshell and a command substitution outside quotes no longer hide a push.
- The words that run another command are read through: `time`, `command`, `exec`, `nohup`, `env` and `timeout` with their options, the keywords `!`, `{`, `if`, `elif`, `while`, `until`, `then`, `else` and `do`, and `sh`, `bash` or `zsh` with `-c`, whose script is read as a command line of its own.
- What is still not recognized is stated: a substitution inside double quotes, `eval`, `xargs`, `sudo`, an alias or a function defined outside the command line, or a script that pushes. The README of `hook post-push` names the forms recognized and these.
- Nothing else of the hook changes: not the landing check, the trailer, the recorded pass or the comment.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `post-push-hook`: "A push is recognized from the command" splits at more characters; three requirements are added for wrappers, keywords and `-c`, and one for what is not recognized.

## Impact

- `core/post_push.py` only (`_commands`, `_pushes`, `is_push`); the README reference of `hook post-push`. No config key, no new dependency.
