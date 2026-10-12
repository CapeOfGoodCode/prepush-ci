Issue: #11

## Why

`verify` (#6) only answers a question. Pull request CI saves money when its gate asks it, and a gate that is easy to get wrong (skipping on the default branch, or for a fork's pull request) costs a missed check. Teams on GitHub, GitLab or any other CI need a gate to copy and a rule to trust (#1 section 5.1).

## What Changes

- New `docs/ci/` with three gate examples: `github-actions.yml`, `gitlab-ci.yml` and `gate.sh` (a generic shell gate).
- New `action.yml` at the repository root: an optional composite GitHub Action that runs the shell gate and outputs `verified`.
- One rule in all of them: skip only on a pull or merge request from the same repository whose source branch is not the default branch, and only when `prepush-ci verify` exits 0 on the request's head commit. Every doubt means "do not skip".
- Each example mentions the optional one full run per pull request as a mitigation for missing local hooks.

## Capabilities

### New Capabilities

- `ci-gate`: when a CI gate may skip, the shell gate's interface, the action, and what the examples must say.

### Modified Capabilities

None.

## Impact

- New: `docs/ci/gate.sh`, `docs/ci/github-actions.yml`, `docs/ci/gitlab-ci.yml`, `action.yml`; no change to the Python package.
- Builds on `verify` (#6), which settles server-made commits; this change settles the pipeline side.
- Not here: `init` printing or writing a gate snippet (#12), the README and `SKILL.md` text about the gate (#15).
