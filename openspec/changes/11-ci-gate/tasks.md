# Tasks

## 1. The shell gate

- [ ] 1.1 Add `docs/ci/gate.sh` with the interface of the design: decide from the environment, call `$PREPUSH_CI_CMD verify` only when the request is eligible, print one `verified=` line, explain on standard error, exit 0; verify with integration specs that run it with `sh` against real temporary repositories, one per scenario

## 2. The action

- [ ] 2.1 Add `action.yml`: composite, input `command`, output `verified`, one step that maps the event to the gate's variables and appends the gate's line to `$GITHUB_OUTPUT`; verify with a spec that reads the file
- [ ] 2.2 Add `docs/ci/github-actions.yml`: a workflow that checks out the head sha, runs the action and lets the other jobs wait on its output; verify with a spec that reads the file

## 3. GitLab and the mitigation

- [ ] 3.1 Add `docs/ci/gitlab-ci.yml` with the generated child pipeline of the design; verify with a spec that reads the file
- [ ] 3.2 Put the mention of the optional full run per pull request into all three examples; verify with a spec per file
- [ ] 3.3 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 11-ci-gate`) before the pull request is marked ready.
