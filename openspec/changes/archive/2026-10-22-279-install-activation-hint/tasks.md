# Tasks

## 1. The hint follows the hooks

- [x] 1.1 Give `manager_report` the facts about the hook files of `commit-msg` and `pre-push` and print the `next:` line only when one of them is not active by the rule of `doctor`, reusing that rule in `core/`; verify with unit specs named after the scenarios of "The manager report"
- [x] 1.2 Add integration specs: `install` after `pre-commit install` prints no activation command, `install` in a repository without the hooks prints it, for lefthook likewise
- [x] 1.3 Run the sentences of the README and `SKILL.md` that say what `install` prints against the head and correct a sentence that says it always prints the step

## 2. Archive

- [x] 2.1 Run `sh scripts/ci` and verify it passes
