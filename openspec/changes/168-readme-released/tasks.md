# Tasks

## 1. The README

- [ ] 1.1 Cut from `README.md` the status box, the `uvx --from git+…` sentence of step 1 (keeping the plugin sentence) and the comment and `uv tool install git+…` line of step 2; verify with a test for each scenario of the added requirement
- [ ] 1.2 Replace `test_the_agent_step_has_a_form_that_runs_before_the_first_release` and its `PRE_RELEASE` constant with tests named after the new scenarios
- [ ] 1.3 Run `sh scripts/ci` and verify it passes

## 2. The classifier

- [ ] 2.1 Change the classifier in `pyproject.toml` to `Development Status :: 3 - Alpha`, in a `chore` commit of its own

## Workflow follow-up

- Archive the change (`openspec archive 168-readme-released`) before the pull request is marked ready.
