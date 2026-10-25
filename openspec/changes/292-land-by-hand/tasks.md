## 1. The pure logic

- [x] 1.1 Add `core/land.py`: the decisions (ancestry, already on the branch, which reason), the answer lines and the reading of git's refusal; verify with unit specs named after the scenarios of "Only a head on top of the tip lands", "The answer is one line" and "A refused push is reported, never forced"

## 2. The command

- [x] 2.1 Add `land_command.py` and the subcommand in `cli.py`: fetch the head and the default branch, the conditions of "The head and the branch come from origin", the refusals before the preflight, `require_env`, the key and the lookup of "The tree must have a pass", the hook-free preflight checkout, the head's verdict, the push; verify with integration specs against real temporary repositories with a bare `origin`, named after the scenarios of the requirements of the `land` capability
- [x] 2.2 Say in the pull request's proof that no landing on a real GitHub repository was tried (the builder has no bypass right); the first real landing is the owner's (#296)

## 3. The README

- [x] 3.1 Add the `land` entry to the command reference and keep the README check green (the `readme` requirements)

## 4. Archive

- [ ] 4.1 Run `sh scripts/ci` and verify it passes
