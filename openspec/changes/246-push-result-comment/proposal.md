Issue: #246

## Why

The result of a session's check reaches the pull request only if the agent remembers, after every push, to run `report --markdown` and update the comment (#239): a rule in `CLAUDE.md` that a session can skip or get wrong, and in a Claude Code cloud session `gh pr comment` fails because the proxy blocks GraphQL. Git has no post-push hook; Claude Code has one (`PostToolUse`), which runs after every command of the agent, so the comment can follow every successful `git push` without anyone remembering it. The owner wants this before 0.2.0 (#227).

## What Changes

- A new command `prepush-ci hook post-push` reads the JSON that a Claude Code `PostToolUse` hook gets on standard input. When the command the agent ran was a `git push`, the commit at `HEAD` carries the trailer and a recorded pass of the check, the push landed on `origin` and the branch has an open pull request, it puts the result on that pull request: the Markdown of `report --markdown --result passed` in the one comment of the check, found by its marker, updated or created through the REST API only. In every other case it does nothing. It never fails: exit 0 always, within 15 seconds, and a failure to post costs one line on standard error.
- The setup skill proposes the hook: it explains it, adds it to `.claude/settings.json` with the user's yes, and keeps the `CLAUDE.md` rule of #239 as the fallback for agents without hooks.
- `report` is not changed.

## Capabilities

### New Capabilities

- `post-push-hook`: the command, how it recognizes a push, when it posts, and how it finds and writes the comment.

### Modified Capabilities

- `skill`: a requirement is added for the step that proposes the hook.

## Impact

- New `hook post-push` subparser in `cli.py`; pure logic (reading the payload, recognizing a push, finding the marker) in `core/`, the requests over `github_api.py`; the README reference names the command. No config key, no new dependency, no change to the pre-push hook or to `report`.
