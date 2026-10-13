# Tasks

## 1. The checks

- [x] 1.1 Move the invocation checker of `tests/integration/skill_spec.py` to one shared place, with no second copy; verify that the specs of the `skill` capability still pass unchanged
- [x] 1.2 Add the spec that reads `README.md` with that checker and fails on an unknown command or option; verify with specs for the shipped file, an unknown option and an unknown command
- [x] 1.3 Add the completeness checks: every command and flag of the CLI is in the reference, every config key the config accepts is in the README and none else, every default equals what the config loads; verify with specs for the shipped file and for a README text with a command, a flag, a key left out and a wrong default
- [x] 1.4 Add the specs for the `skill` requirements that the user confirms the check, the agent works on a branch and opens a pull request, finds or writes the one check command and sets up services so that a missing service fails the check; verify with specs for the four scenarios (`SKILL.md` already says all four)

## 2. The README

- [x] 2.1 Add the usage section; verify with specs for the steps and their order
- [x] 2.2 Add the command reference with purpose, synopsis, example and exit codes; verify with specs for each command's entry
- [x] 2.3 Add `PREPUSH_CI` and the config keys; verify with specs for the values and the keys, and that `readme_links_spec.py` still passes (absolute links only)
- [x] 2.4 Add the agent setup step at the head of the usage section; verify with specs for its place before the install step, the prompt, the link to the skill resolving to a file of the repository, what the agent always asks and what it asks only sometimes, the pull request it opens, and the manual core with what the skill does on top

## 3. Finish

- [x] 3.1 Run `sh scripts/ci` and verify it passes
