Issue: #239

## Why

`report` cannot post from a Claude Code cloud session, the place the check is meant to run: the session's proxy refuses writes to commit statuses and replaces the app's token exchange (#232, #233). The pull request then never shows what the session checked. A comment reaches the pull request with the tools every agent session has, and it is what a reviewer needs to see; the machine-readable gate stays the trailer, which `verify` reads (#239, wanted before 0.2.0, #227).

## What Changes

- `report --markdown` prints the summary that `report` posts today as Markdown on standard output and posts nothing. It needs no token, no app, no `origin` and no network. It takes the inputs of `report --result`.
- The text starts with a hidden marker that names the check (`<!-- prepush-ci:<name> -->`) and a line that names the commit it reports, so that whoever posts it can find and update one comment per check, and a reader sees when it is stale.
- The skill puts into the section it has the agent add to `CLAUDE.md`, which every later session reads, the instruction: after a push of a commit with the trailer to a branch with a pull request: run that command and create or update the pull request's comment, found by the marker.
- The check run and the commit status stay as they are.

## Capabilities

### Modified Capabilities

- `report`: requirements are added for the Markdown output, its marker and head line, and its refusals; the eleven existing requirements that speak of posting, requests, credentials or annotations are limited to a run without `--markdown`.
- `skill`: a requirement is added for the step that posts the comment.

## Impact

- `cli.py`: the flag `--markdown`; `report_command.py` and `core/report.py`: a path that builds the same summary and returns it instead of posting. README: the reference of `report` names the flag. No config key, no new dependency, no change to the pre-push hook.
