# Tasks

## 1. The checks

- [ ] 1.1 Add the spec that reads `SKILL.md` and fails on a `prepush-ci` command or option the CLI does not have; verify with specs for the shipped file, an unknown command, an unknown option, a nested command (`hook pre-push`) and `verify` with a sha, with an option and without
- [ ] 1.2 Add the run of the skill's `init` invocation in a scratch repository with its placeholders filled; verify with specs for exit 0 and the files written

## 2. The skill

- [ ] 2.1 Let `init` write what it writes: remove the hand-written SessionStart script, settings entry and hook install; extend the script `init` wrote with dependencies, services and the manager's activation; replace `prepush-ci/gate@v1` with `CapeOfGoodCode/prepush-ci@<ref>`; verify with specs for each requirement of the `skill` capability about these points
- [ ] 2.2 Add the look at existing hooks and the pre-push question before `init`, with the answer-to-command mapping; verify with specs for the order, the three answers, the manager case, the committed block for pre-commit, husky and lefthook, the forks sentence, the action name and the rule that no hook file is changed without a yes
- [ ] 2.3 Use `doctor --mode full` in the proof step; verify with a spec

## 3. Finish

- [ ] 3.1 Run `sh scripts/ci` and verify it passes
