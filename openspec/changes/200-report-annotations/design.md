# Design

## Context

Amends the `report` spec that #197 added. The mockups in #197 ("Details of a red run", "Annotations in the pull request's diff") are the target for what a reviewer sees.

## Decisions

- **The run in progress is found by asking GitHub, not by a file on disk.** The final `report` looks up the check runs of the commit with `GET /repos/<owner>/<repo>/commits/<sha>/check-runs?check_name=<name>&status=in_progress&app_id=<id>` and updates one with `PATCH /repos/<owner>/<repo>/check-runs/<id>`. A session that ends and another that finishes the work still complete the run, and nothing is left in the repository or in the temporary directory. Cost: one more request, and the app must be allowed to read check runs, which `checks: write` includes.
- **At most one run in progress per commit, name and app.** `report --start` on a commit that already has one updates its `started_at` instead of creating another, so the final `report` never has to choose and an aborted session leaves one stale run, not many. The run a session aborted stays `in_progress` until the next `report` for that commit completes it (GitHub itself marks a run stale after 14 days).
- **`--start` takes `--tree`, `--commit` and `--name` and nothing else.** The tree check is the same as for a result: a run never shows on a state it did not check. `--result`, `--junit`, `--coverage`, `--ruff`, `--mypy`, `--duration` and `--tool` belong to a result, so combining them with `--start` is a mistake of the command line (exit 2), not a silent ignore.
- **Without an app, `--start` posts a `pending` commit status** with the same context as the final one, so the final `success` or `failure` replaces it on the commit. A status has no run to complete, and the pull request shows "pending" instead of nothing.
- **Failure formats: JUnit with a location, ruff JSON, mypy text.** Run on the tools (below): pytest writes `file` and `line` on a case only with `-o junit_family=xunit1`; `node --test --test-reporter=junit` writes none. pytest's `line` is 0-based (`_pytest/reports.py`: "The line number is 0-based"; on a run, `def test_a` on line 4 gives `line="3"`), so the annotation sits on `line` + 1; ruff's `row` and the line of mypy are 1-based. A failed case without both attributes counts and appears in the summary but has no line to sit on, so it gets no annotation. ruff's `--output-format json` gives path, row, code and message without parsing prose. mypy has no stable machine format in the versions this project supports, so its default output is read: `path:line: error: message [code]` (the `:column` part is optional). `note:` lines are context, not failures. A file that holds neither `Success: no issues found` nor `Found N error(s)` is not mypy output and is refused.
- **Paths are relative to the top of the worktree, and always use `/`.** ruff writes absolute paths; mypy writes the paths it was given; pytest writes `file` relative to its rootdir (a run from another directory with `--rootdir` gave `file="t_spec.py"`), so the rootdir, not the working directory, has to be the top of the worktree. A relative path is taken from the top of the worktree; an absolute path inside it is made relative; a path outside it makes `report` exit 1, because an annotation on a file that is not in the commit would sit on a file it did not check. On Windows the tools write `\` and mypy may write `C:\…`, whose first `:` belongs to the path; GitHub matches `path` against the repository's paths, so every `\` becomes `/`. Cost: the tools must run at the top of the worktree (rootdir for pytest), which `scripts/ci` style checks do anyway.
- **A `passed` result with a ruff or mypy error is refused**, as one with a failing test case already is. The check cannot have passed when its own output says otherwise.
- **The first request carries the first 50 annotations and each later request the next 50** (GitHub accepts 50 per request). The same title and summary go with each update. If a later request fails the run is left with the annotations that arrived and the command exits 1.
- **The summary lists at most 20 failures, then "and N more", one line each; the location and the text of a failure are code spans, the text at most 200 characters.** GitHub refuses an `output.summary` over 65535 characters with 422, and a pytest message is the whole assertion repr with line breaks, so an unbounded line could make the request fail and a red result never post. Each line holds the first line of the message (or the name of a case without location), cut at 200 with `…` as the 200th character; 20 lines stay far below the limit and the annotations carry the rest. The text is free text from a file, and GitHub changes what it shows (`2*3` turns into emphasis, `<built-in function len>` vanishes as a tag, `test_x[__init__]` turns bold), so it is wrapped like the other free values of the summary (`code_span()` in `core/report.py`); the 200 count the text, so the cut is made before the wrapping and the line ends with the closing backticks.
- **Annotation `title` is the tool (`pytest`, `ruff`, `mypy`) and `message` holds the code and the text**, as in the #197 mockup (`mypy · line 42`).

## Run the tools

pytest 8 (JUnit family and the attributes of a case):

```
$ pytest -q -o junit_family=xunit1 --junitxml=x1.xml t_spec.py
<testcase classname="t_spec" name="test_a" file="t_spec.py" line="2" time="0.001"><failure message="assert 1 == 2">…
$ pytest -q --junitxml=x2.xml t_spec.py
<testcase classname="t_spec" name="test_a" time="0.001"><failure message="assert 1 == 2">…
```

node 22.23 (`node --test --test-reporter=junit`): `<testcase name="bad" time="…" classname="test" failure="…">`, no `file` or `line`.

ruff (`ruff check --output-format json /tmp/fmt/t_spec.py`): a JSON array; each element holds `"filename": "/tmp/fmt/t_spec.py"` (absolute), `"location": {"column": 1, "row": 1}`, `"code": "F401"` and `"message"`.

mypy (`mypy --strict t_spec.py`):

```
/tmp/fmt/t_spec.py:2: error: Incompatible types in assignment (expression has type "str", variable has type "int")  [assignment]
/tmp/fmt/t_spec.py:3: note: Use "-> None" if function does not return a value
Found 3 errors in 1 file (checked 1 source file)
```
