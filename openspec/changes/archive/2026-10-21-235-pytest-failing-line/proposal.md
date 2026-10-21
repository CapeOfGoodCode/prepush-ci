Issue: #235

## Why

A reader of the check run is sent to the wrong line. pytest's xunit1 JUnit gives the line of the test function, which for a decorated test is its first decorator, while the failure text names the failing line (`test_demo.py:7: AssertionError`). The cases of a parametrized test get identical annotations, because nothing in an annotation names the case. Found in the trial of `main` before 0.2.0 (#232).

## What Changes

- A failed case whose failure text holds a line at the first column that begins `<file>:<n>:` for the file of the case is annotated on line `n` of the last such line (the deepest frame in that file, whichever traceback style pytest prints), not on the line of the test function. A case whose failure text has no such line (one that names only another file, for instance) keeps `line` + 1.
- The message of the annotation of a failed case begins with the name of the case (`test_double[1]`), so the cases of a parametrized test can be told apart. The title stays `pytest`.
- The README says so, in the reference of `report`.

## Capabilities

### Modified Capabilities

- `report`: "A failed case sits on its line plus one" gives way to the failing line when the failure text names one; one requirement is added for the failing line and one for the name of the case.

## Impact

- `junit_failures` and `annotation` in `core/report.py`, their tests, one sentence in the README. No config key, no new dependency.
