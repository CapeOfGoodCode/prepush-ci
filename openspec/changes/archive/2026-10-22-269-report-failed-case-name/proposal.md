Issue: #269

## Why

`report --markdown` lists a failed test as its file, line and message only. With parametrized cases on one line, a reader cannot tell which case failed without opening the log. The check run's annotation has the same gap in its title: it says `pytest`, and the case is named only in the first line of the message. Found in the final trial of `f815b8d`; the owner wants it fixed before 0.2.0 (#227).

## What Changes

- A failed JUnit case gets a label: its `name`, preceded by the class part of its `classname` (`test_split[three-ways]`, `TestK.test_in_class`).
- The summary, and so the Markdown comment, shows the label as a code span before the text of each listed failed case.
- The title of the annotation of a failed case is `pytest: <label>`, and its message is the message of the case alone (the name no longer starts it).
- Ruff and mypy failures, the counts and the check run's own title are not changed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `report`: a requirement for the label is added; "Failures become annotations", "A failed case sits on its line plus one", "The annotation of a failed case names the case" and "A listed failure is one short line" are modified.

## Impact

- `junit_failures`, `annotation` and `_failure_line` in `core/report.py` (the `Failure` record gets the label instead of the name); the README only if it describes the annotation. No flag, no config key, no new dependency.
