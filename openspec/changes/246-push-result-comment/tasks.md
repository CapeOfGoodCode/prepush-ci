# Tasks

## 1. Recognize a push

- [x] 1.1 Add the pure logic in `core/`: the payload's command, and whether a command line pushes (quotes, separators, line breaks, `-C`/`-c`, environment assignments, `--dry-run`, `--delete`, other subcommands); verify with unit specs named after the scenarios of "A push is recognized from the command" and "A push that sends nothing or removes a ref is not one"

## 2. The command

- [x] 2.1 Add `prepush-ci hook post-push`: read standard input, stop silently unless there is a push that landed, a trailer commit with a recorded pass and an open pull request, exit 0 always; verify with integration specs against a real repository with a bare `origin` and a stub API for the scenarios of "The hook reads the payload and never fails", "The hook acts for a landed push", "The hook acts for a commit that demands the check", "Only a recorded pass is shown" and "The pull request of the branch"
- [x] 2.2 Find the comment by the marker, paginated, and update or create it through REST; send no update when the body is the same; send the token when there is one; verify with specs for "The comment is the Markdown of report", "One comment per check, found by its marker", "The comment is replaced, left alone or created", "Only the REST API is used", "The whole run is bounded", "The credentials are the token's, if there is one" and "A failure to post is one line"
- [x] 2.3 Name `hook post-push` in the reference of the README, run against the head

## 3. The skill proposes the hook

- [ ] 3.1 Add the step to `SKILL.md`: explain the hook, ask for the user's yes, add the group to `.claude/settings.json` and keep the `CLAUDE.md` rule as the fallback; the command runs the hook only where `prepush-ci` is installed, and the step tells the user that `uv tool install prepush-ci` turns it on; verify with specs that read the skill, run the command of the group in `sh -c` with and without the tool and with and without `uv` on the `PATH`, and with "Every command in the skill exists" passing
- [ ] 3.2 Give the new capability `post-push-hook` its Purpose when archiving, run `sh scripts/ci` and verify it passes
