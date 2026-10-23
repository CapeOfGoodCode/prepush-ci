## Context

`report` reads `--junit` (JUnit XML, counted by case) and `--coverage` (the `coverage.json` of coverage.py, `totals.percent_covered_display`) and refuses a file that is missing or of another format ("Results are read from standard formats", "Input that cannot be trusted is refused"). `hook post-push` writes the comment of `report --markdown --result passed --tree <tree of HEAD>`, with no result files, and replaces the comment whose body starts with the marker ("The comment is the Markdown of report", "The comment is replaced, left alone or created"). The skill's step 8 instruction runs the same call by hand; step 9 proposes the hook.

## Verified with the tools

pytest 9.1.1 with pytest-cov 7.1.0, in a throwaway repository whose `.gitignore` holds `.prepush-ci/`:

```
$ pytest -q --junitxml=.prepush-ci/junit.xml -o junit_family=xunit1 --cov=pkg --cov-report=json:.prepush-ci/coverage.json
1 passed in 0.02s
$ git status --short            # prints nothing: the files are ignored
$ prepush-ci report --markdown --result passed --tree "$(git rev-parse 'HEAD^{tree}')" --junit .prepush-ci/junit.xml --coverage .prepush-ci/coverage.json
<!-- prepush-ci:prepush-ci / full -->
### prepush-ci / full: 1 passed, 0 failed, 0 skipped
…
| Tests | 1 passed, 0 failed, 0 skipped |
```

Both options create the directory `.prepush-ci/` themselves; `node --test --test-reporter-destination=.prepush-ci/junit.xml` does not, and on a fresh checkout (the directory is ignored, never committed) it exits 7 and turns a green check red. The `junit_family=xunit1` option makes pytest write `file` and `line` on each case, which the annotations of a failed case need.

The paths are relative to the directory the command runs in, for the option and for `report` (git 2.39.5, pytest 9.1.1, prepush-ci at `72f9245`; `backend/` holds the tests, the config is committed, `.prepush-ci/` is ignored):

```
$ sh -c 'cd backend && ../.venv/bin/python -m pytest -q --junitxml=.prepush-ci/junit.xml'
1 passed in 0.01s
$ find . -name junit.xml -not -path './.venv/*'
./backend/.prepush-ci/junit.xml           # not ./.prepush-ci/junit.xml
$ cd backend && prepush-ci report --markdown --result passed --tree "$(git rev-parse 'HEAD^{tree}')" --junit .prepush-ci/junit.xml
prepush-ci: cannot read .prepush-ci/junit.xml: No such file or directory      # exit 1, no comment
$ cd backend && prepush-ci report … --junit "$(git rev-parse --show-toplevel)/.prepush-ci/junit.xml"
| Tests | 1 passed, 0 failed, 0 skipped |
```

`git rev-parse --show-toplevel` gives the top from any subdirectory of the worktree. The Windows form of its output (`C:/…`, in Git Bash) was not run here.

## Decisions

- **Fixed paths: `.prepush-ci/junit.xml` and `.prepush-ci/coverage.json`.** One directory is one `.gitignore` line, and nothing in the tool writes there, and a project may already use `reports/`. The pre-push hook refuses a dirty worktree, and an untracked file that is not ignored is dirty, so the ignore line is not optional when a file is written, and not wanted when none is.
- **Only what the check already has: no new dependency, no new measurement.** JUnit goes through `pytest --junitxml`, which adds the file and takes nothing from the console output (pytest prints a line that names the written file, and that is allowed). vitest, jest and `node --test` get no JUnit file: a reporter named on the command line (`--reporter=junit`, `--reporters=jest-junit`) replaces the reporters the runner chooses itself, and it chooses them from the environment (vitest 5: `minimal` under an agent, `default` otherwise, plus `github-actions` in GitHub Actions; jest 30: `agent` under an agent, `default` otherwise), so no list of reporters in the skill equals what the check ran before, and the pre-push hook (under the agent that pushes) and CI (in GitHub Actions) would both print something else; the `reporters` of a project's own configuration are replaced the same way. The skill does not guess them: it tells the user that the comment will show no counts for that check. Coverage goes in only when the check already measures it with coverage.py. Adding `--cov` to a check that has none would start measurement, and a `fail_under` in the project's coverage configuration would then fail a check that passed: a change to what the check checks. A runner that cannot write coverage.py's JSON gets a JUnit file and no coverage file; `report` reads no other coverage format and would exit 1 on one.
- **The check's own output stays.** `--cov-report=json:` replaces the default `term` report of pytest-cov, so a check with `--cov` and no `--cov-report` would lose the table of uncovered lines that an agent reads after a push; the skill adds `--cov-report=term` beside the JSON report in that case only (a `--cov-report` on the command line or in `addopts` keeps its own terminal report). A later `--junitxml` or `--cov-report=json` also beats the project's own (`addopts = --junitxml=reports/junit.xml`), so a check that already writes such a file gets no option for it: the file is left out, the user is told, and the comment shows no counts for it.
- **The options go only where the skill can show them.** Step 1 usually ends in an entry point, and options added to `scripts/ci` or `make ci` never reach the test runner. Three forms of the check: the check is a command line (a runner call or a chain), and the options go to the test command inside it, with `init` storing the changed line; the check is a `scripts/ci` the skill wrote in this run, and the options go to its test line, with `init` storing `scripts/ci` unchanged; any other entry point (the project's script, a Makefile or justfile target, a package script, a tox or nox session) gets no files and an explanation. The same holds one level down: the options go only after a direct call of the runner (`pytest`, also behind `uv run`; a call of `vitest`, `jest` or `node --test` gets no JUnit file, above); a test command that is itself an entry point (`make test`, `npm test`, `tox -e py`, in the line or in the skill's `scripts/ci`) gets no files and an explanation, since an appended `--junitxml` would not reach the runner or would be an unknown option. Rationale: the skill edits no file of the project beyond the ones it creates, and it adds the `.gitignore` line only when it writes a file, so the cases that write nothing change nothing, a `--` pass-through reaches only the last command of a package script, and a rule that says where the change goes for every project's build file cannot be tested. The agent reads the test commands inside the command line or the script to apply the several-commands rule; for the third form it need not, since it writes nothing. A follow-up can widen the third form.
- **A `cd` before the test command: no files.** The paths of the option are relative, so a test command that starts in `backend/` writes `backend/.prepush-ci/junit.xml`, where the instruction does not look, and the call fails with exit 1 and no comment. Anchoring the option (`--junitxml="$(git rev-parse --show-toplevel)/…"`) would put a shell substitution into the stored check, and the shell that runs the check differs between hosts. The skill edits only what it can show and test, as above, so a check that changes directory first gets no files and an explanation; a follow-up can anchor it. The rule is about the directory in which the test command starts: a `cd` in a subshell that ended before it does not count.
- **The instruction anchors its paths.** The agent often works in a subdirectory, and `report` reads a relative path from the current directory. `"$(git rev-parse --show-toplevel)/.prepush-ci/junit.xml"` is the same text from any directory, needs no `cd` (the shell of an agent keeps its directory between commands), and uses the command the call already uses for the tree. `report` resolving the path against the top itself would change the tool, which is out of this slice.
- **The agent asks once, with the change shown.** The user sees the changed command line, or the changed line of the script, before it is made; a "no" stores the confirmed check unchanged, leaves the script without options and drops `--junit` and `--coverage` from the step 8 call; the question comes after the check is confirmed (step 1, item 4), so no step is renumbered.
- **A pass that skipped the check shows no facts.** When the push said the check passed earlier (the hook printed that it skipped the check; "A cached pass skips the check in the hook"), the files on disk may belong to another tree, and `report` cannot tell. The instruction leaves the files out; the comment then holds the short text, which is true.
- **The hook's short comment comes first.** The hook writes it right after the push; the agent's call replaces the same comment (same marker), so a later push resets it to the short text until the agent updates it again. The instruction says so, so the agent does not read the reset as an error.
- **The README needs no spec change.** The `readme` capability checks drift, not prose. Its two new sentences are pinned elsewhere: "the post-push hook writes the short comment and the agent's call updates the same comment" by "The comment is the Markdown of report" and "The comment is replaced, left alone or created"; "`report --markdown` shows test counts and coverage from the files it is given" by "The summary is the check run's". The builder runs both sentences against the head, as `AGENTS.md` asks.

## Out of scope

Ruff and mypy files (`--ruff`, `--mypy`), config keys that name result files, and the hook reading result files itself: those are #287.
