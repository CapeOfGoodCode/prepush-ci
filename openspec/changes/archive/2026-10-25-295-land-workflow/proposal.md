Issue: #295

## Why

A person or an agent session should not need admin rights to land a pull request. With the ruleset of #294, only the app that `app setup --land` creates can move the default branch; a GitHub Actions workflow with that app's token can land an approved pull request whose tree passed, and tell the author to rebase when it did not. Without the workflow, only repository admins can land, by hand (owner's decision of 2026-10-25, #199, way 2).

## What Changes

- New example `docs/ci/land.yml` (`.github/` is reserved, so users copy it): on an approving review by someone who can write, for the head that was approved, of a pull request that is open, not a draft and based on the default branch, with the approval still standing, all read from the API when the job runs so that a re-run cannot land on a stale event, a job mints the app's installation token, checks out the default branch and runs `prepush-ci land <number>` with it. Landings are not queued: `land`'s fast-forward push orders them, and every approval gets a run.
- When `land` does not land, the job comments on the pull request: the `not landed:` line, and what to do for that kind of refusal (rebase and push, so that the pre-push hook checks the new tree, then ask for a new approval; or change the workflow).
- The README gets a step that says how to land with the workflow, how to switch CI on the default branch off, and that a private repository needs a paid plan for the ruleset. The README check names `docs/ci/land.yml` and the variable and secret it reads.

## Capabilities

### New Capabilities

- `land-workflow`: the landing workflow example, in a capability of its own so that it does not share a spec with `ci-gate` (the gate) or `land` (the command).

### Modified Capabilities

- `readme`: the README names the landing example and what it reads.

## Impact

`docs/ci/land.yml` (new), `README.md`, and the drift check of the README in `src/prepush_ci/` (`readme_check` or its equivalent). No new dependency, no change to `land`, `app setup` or `doctor`. Out of scope: switching this repository to it (#296, a human task: `.github/` is reserved), and a service with a queue (way 3 of #199).
