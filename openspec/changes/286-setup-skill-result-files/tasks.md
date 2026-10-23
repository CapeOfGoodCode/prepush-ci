# Tasks

## 1. The check writes its result files

- [x] 1.1 Add the item to step 1 of `skills/prepush-ci-setup/SKILL.md`: ask, write `.prepush-ci/junit.xml` (and `.prepush-ci/coverage.json` for coverage.py's JSON), add `.prepush-ci/` to `.gitignore` only when a file is written, change nothing the check checks; the rules of no new dependency, no new measurement, several test commands, where the options go (command line, `scripts/ci` of this run, other entry points get none; a test command that is not a direct runner call gets none) and a "no"; the console output stays (`--cov-report=term` beside the JSON report when the check names no `--cov-report`), a file the check already writes is left alone, and a runner that chooses its reporters from the environment (vitest, jest, `node --test`) gets no JUnit file; verify with specs named after the scenarios of the requirements
- [x] 1.2 Check the `pytest` form against the head in a throwaway repository, with the commands and output of the design

## 2. The instruction passes them

- [x] 2.1 Change the step 8 instruction: the call with `--junit` and `--coverage`, the rule for a file the push did not write, the hook and the call sharing the comment; verify with specs named after the scenarios of the three requirements for the instruction of the documentation step
- [x] 2.2 Add one sentence each under `hook post-push` and `report` in `README.md`; run both against the head and keep the README check green

## 3. Paths anchored at the top of the worktree

- [x] 3.1 Add the rule of the directory to step 1, item 6 of `SKILL.md`: a `cd` (or `pushd`, `uv run --directory`, `make -C`) before the test command, in the line or the skill's `scripts/ci`, gets no files; extend the "no file, no ignore line" list; verify with specs named after the two new scenarios
- [x] 3.2 Anchor the paths of the step 8 instruction at `"$(git rev-parse --show-toplevel)/…"`; change the spec that pins the old form and add one for the new scenario
- [x] 3.3 Run the step 8 call from a subdirectory of a throwaway repository, with the paths as written in the instruction, and keep the output

## 4. Archive

- [ ] 4.1 Run `sh scripts/ci` and verify it passes
