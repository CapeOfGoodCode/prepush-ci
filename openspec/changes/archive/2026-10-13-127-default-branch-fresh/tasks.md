# Tasks

## 1. The skill refreshes origin/HEAD

- [x] 1.1 Change the `<default branch>` step of `skills/prepush-ci-setup/SKILL.md` to run `git remote set-head origin --auto` before `git symbolic-ref refs/remotes/origin/HEAD` and to ask the user when either fails; verify with a test for every scenario of the two skill requirements

## 2. init refuses a default branch that origin lacks

- [x] 2.1 Make `init` refuse a flag or answer default branch for which `origin` has remote-tracking branches but not that one, when `origin` has the default fetch refspec and the up-to-date ref in effect is `origin/<branch>`, naming `default_branch`, the branch and `git fetch origin`; verify with a test for every scenario of the added requirement
- [x] 2.2 Run `sh scripts/ci` and verify it passes

## 3. The README follows

- [x] 3.1 Change the sentence in `README.md` on what the agent asks to name the same cases as the skill; verify with the `readme` spec for what the agent asks only sometimes

## Workflow follow-up

- Archive the change (`openspec archive 127-default-branch-fresh`) before the pull request is marked ready.
