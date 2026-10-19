# Tasks

## 1. Failures as annotations

- [x] 1.1 Read `--ruff` and `--mypy` and the `file` and `line` of failed JUnit cases into failures, put a case on its JUnit `line` + 1, make their paths relative to the top of the worktree with `/` as separator (backslashes and drive letters included), refuse a path outside it, an untrusted file and a `passed` result that contradicts a file; verify with unit specs for the parsers and integration specs for each scenario of "Failures become annotations", "A failed case sits on its line plus one", "Ruff and mypy output is read", "Paths of failures are taken from the top of the worktree" and "Failure files that cannot be trusted are refused"
- [x] 1.2 Send the annotations in batches of 50 and list at most 20 failures first in the summary of a red run, each location and text as a code span, the text cut to its first message line and 200 characters; verify with the scenarios of "Annotations are sent in batches of 50" (exactly 50, 120, a rejected batch), "The summary of a red run lists the failures first", "A listed failure is one short line" and "A listed failure is shown as typed"

## 2. A run in progress

- [ ] 2.1 Add `--start`: an `in_progress` check run (or an updated `started_at`), a `pending` status without an app, the refusal of the flags of a result with exit 2, and `--start` or `--result` required; verify with the scenarios of "A run can be shown as in progress" and "A start takes no flag of a result"
- [ ] 2.2 Complete the run in progress on the final `report`: look it up, update the one with the highest id, create a run when there is none; verify with the scenarios of "The final report completes the run in progress"

## 3. Reference and archive

- [ ] 3.1 Name `--start`, `--ruff` and `--mypy` in the README's reference of `report`, with `-o junit_family=xunit1` for pytest locations only if a spec or a run on the head backs the sentence (design.md, "Run the tools"; pytest's paths follow its rootdir); verify with the `readme` drift specs
- [ ] 3.2 Run `sh scripts/ci` and verify it passes
