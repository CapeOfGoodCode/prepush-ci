Issue: #294

## Why

Landing only protects the default branch if nothing else can move it. A ruleset that lets only one bypass actor update the branch makes "checked, then landed" the only way in (owner's decision of 2026-10-25, #199; the experiment T1–T8 in its comments shows what holds). Today every repository has to build that ruleset by hand in the settings, and nothing tells it when the ruleset is missing or lets someone else in.

## What Changes

- New command `prepush-ci app ruleset (--admin | --app <id>)`: creates the ruleset `prepush-ci landing` on the default branch with the rules `update`, `non_fast_forward` and `deletion` and no `pull_request` rule. The only bypass actor is the repository-admin role (`--admin`, for `land` by hand) or the given app (`--app`, for the landing workflow of #295). It uses the token the user gives it (`GITHUB_TOKEN` or `GH_TOKEN`); `app setup` never sees a credential.
- `app setup --land` asks for the permissions an app needs to move the branch: `checks: write`, `contents: write`, `pull_requests: read` and `workflows: write` (GitHub refuses a push that changes a workflow file without the last). Without the flag the app keeps its one permission, `checks: write`. With the flag the command also prints the next step, the `app ruleset --app` command with the new app's id.
- `doctor --ruleset` adds a seventh check, `ruleset`: the ruleset exists, is active, has those rules and lists one bypass actor, the admin role or one app. Without the flag `doctor` is unchanged.
- The help of `app ruleset` and its refusal on a private repository say that rulesets need a paid plan there.

## Capabilities

### Modified Capabilities

- `app-setup`: the `--land` permissions and the `app ruleset` command.
- `doctor`: the `--ruleset` check and the count in the closing line.

## Impact

`src/prepush_ci/`: pure logic in `core/` (the manifest permissions, the ruleset body, the reading of a ruleset), `app_setup_command.py`, a new `app_ruleset_command.py`, `doctor_command.py`, three requests in `github_api.py`, `cli.py`. No new dependency. The README and the skill are not touched. Out of scope: the landing workflow (#295), switching this repository (#296). The issue called the ruleset part of `app setup`; it is a second command, for the reasons in `design.md`.
