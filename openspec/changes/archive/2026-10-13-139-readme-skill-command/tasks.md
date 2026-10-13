# Tasks

## 1. The agent step

- [x] 1.1 Change usage step 1 of `README.md`: the prompt asks the agent to run `uvx prepush-ci skill` and follow it, the pre-release form and the plugin commands follow as code spans, and the project skill is kept with `prepush-ci skill --write`; verify with a test for every scenario of the two requirements
- [x] 1.2 Replace the tests of the link (`test_the_link_to_the_skill_is_absolute_…`, `test_the_agent_step_has_a_prompt_with_the_link_…`, `test_the_agent_step_names_the_skill_folder_…`) with tests named after the new scenarios
- [x] 1.3 Run `sh scripts/ci` and verify it passes

## Workflow follow-up

- Archive the change (`openspec archive 139-readme-skill-command`) before the pull request is marked ready.
