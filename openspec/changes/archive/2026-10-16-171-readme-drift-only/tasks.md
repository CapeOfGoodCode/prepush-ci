# Tasks

## 1. The spec and its tests

- [x] 1.1 Delete from `tests/integration/readme_spec.py` the tests of the scenarios of the seven removed requirements (and the helpers only they use: `STEPS`, `step_problems`, `usage`, `PRE_RELEASE_PHRASES`, `PRE_RELEASE_ADDRESS`, `pre_release_wording`), keeping `steps`, `agent_step`, `agent_prompt` and `spans`, which the kept checks use
- [x] 1.2 Delete the tests of the scenarios "The agent step comes first" and "A prompt to hand over", whose requirement is replaced by the narrower one, and keep "The prompt's command exists" and "No link to the skill on GitHub" unchanged; the requirement "The agent step names the Claude Code plugin" and its tests are untouched
- [x] 1.3 Update the module docstring of `tests/integration/readme_spec.py`: it no longer walks the usage steps in order
- [x] 1.4 Add the test of the scenario "The agent step exists" (the helper `agent_step` reports a problem, not `StopIteration`, when no step names the agent)
- [x] 1.5 Replace the Purpose paragraph of `openspec/specs/readme/spec.md` with the one in `design.md`, word for word
- [x] 1.6 Verify that every scenario left in `openspec/specs/readme/spec.md` has a test of the same name and that the tests of the other requirements are untouched, then run `sh scripts/ci`

## Workflow follow-up

- The archive commit only moves the change. Archive the change (`openspec archive 171-readme-drift-only`) before the pull request is marked ready.
