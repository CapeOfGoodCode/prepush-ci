## ADDED Requirements

### Requirement: A failed case has a label
The label of a failed JUnit case SHALL be its `name`, joined with a `.` to a prefix from its `classname`. The module is the `file` as for the annotation's `path`, without its extension and with a dot for each `/`. The prefix is the rest of the `classname` after the module and a dot, none when it equals the module, and in every other case (a case without a `file` too) the whole `classname`. A case without a `classname` has its `name` alone.

#### Scenario: A function
- **WHEN** a failed case has `classname="tests.a_spec"`, `name="test_split[three-ways]"` and `file="tests/a_spec.py"`
- **THEN** its label is `test_split[three-ways]`

#### Scenario: A method
- **WHEN** a failed case has `classname="tests.a_spec.TestK"`, `name="test_in_class"` and `file="tests/a_spec.py"`
- **THEN** its label is `TestK.test_in_class`

#### Scenario: A classname of another module
- **WHEN** a failed case has `classname="other.mod"`, `name="test_x"` and `file="tests/a_spec.py"`, or no `file`
- **THEN** its label is `other.mod.test_x`

#### Scenario: No classname
- **WHEN** a failed case has no `classname` and `name="test_x"`
- **THEN** its label is `test_x`

#### Scenario: A long label is cut
- **WHEN** the label of a failed case is 5000 characters long
- **THEN** the label in the summary and in the annotation's title is 200 characters long and ends with `…`

## MODIFIED Requirements

### Requirement: Failures become annotations
With an app and without `--markdown`, each failure SHALL become one annotation with the `path` of its file, `start_line` and `end_line` both its line, `annotation_level` `failure`, a `title` naming the tool (`ruff` or `mypy`, and for a failed case `pytest` and its label, see "The annotation of a failed case names the case") and a `message`. Without an app the failure files SHALL be read and checked, not posted.

#### Scenario: Without an app
- **WHEN** a ruff file with one error is given and `report --result failed` runs without an app
- **THEN** it exits 0, the commit status is created as without the file and no annotation is sent

### Requirement: A failed case sits on its line plus one
`--junit` SHALL yield one annotation per failed case that has a `file` and a `line` attribute, with the message of the case. The `line` of a case is 0-based, as pytest writes it, so the annotation's `start_line` and `end_line` SHALL be `line` + 1, unless the failure names a line of the file of the case (see "A failed case sits on the line its failure names").

#### Scenario: A failing test on its line
- **WHEN** a JUnit file holds a failed case with `name="test_a"`, `file="tests/a_spec.py"` and `line="117"`, whose failure text names no line, and `report --result failed` runs with an app
- **THEN** the check run has one annotation with `path` `tests/a_spec.py`, `start_line` 118, `end_line` 118, `annotation_level` `failure` and the title `pytest: test_a`

#### Scenario: A failing test without a location
- **WHEN** a JUnit file holds a failed case with no `line` attribute
- **THEN** the check run has no annotation for it and the counts still hold it as failed

### Requirement: The annotation of a failed case names the case
The `title` of the annotation of a failed case SHALL be `pytest: ` and the label of the case, and its `message` the message of the case alone, so that the annotations of the cases of a parametrized test differ in their titles.

#### Scenario: Two cases of a parametrized test
- **WHEN** a JUnit file holds two failed cases named `test_double[1]` and `test_double[2]` with the same `file` and `line` and the failure messages `assert 2 == 1` and `assert 4 == 2`
- **THEN** the check run has two annotations, whose titles are `pytest: test_double[1]` and `pytest: test_double[2]` and whose messages are `assert 2 == 1` and `assert 4 == 2`

#### Scenario: The summary keeps the message
- **WHEN** a failed case named `test_a` with a location has the message `AssertionError: assert a == b`
- **THEN** the summary lists the case with `test_a` and `AssertionError: assert a == b`, and its annotation title is `pytest: test_a`

### Requirement: A listed failure is one short line
A failure in the summary SHALL be one line with its tool, its location when known and its text: the first line of its message. A failed case SHALL show its label as a code span before the text, and a failed case without a location SHALL show the label alone. The text and the label SHALL each be at most 200 characters, cut with `…` as the 200th character when longer; the characters counted are those of the text or label, not of what wraps it (see "A listed failure is shown as typed").

#### Scenario: A message of several lines
- **WHEN** a JUnit file holds a failed case with a location whose message is `AssertionError: assert a == b` followed by a line break and more lines of a diff
- **THEN** the summary lists the case with `AssertionError: assert a == b` and none of the lines after the break

#### Scenario: A long message is cut
- **WHEN** a failure's message, or the name of a failed case, is 5000 characters long
- **THEN** its text in the summary is 200 characters long and ends with `…`

#### Scenario: A short message is whole
- **WHEN** a failure's message is exactly 200 characters long
- **THEN** its text in the summary is that message, with no `…`

#### Scenario: The cases of one parametrized test
- **WHEN** two failed cases `test_split[three-ways]` and `test_split[two]` of one function share a `file` and a `line`
- **THEN** the summary lists two lines with the same location, one with `test_split[three-ways]` and one with `test_split[two]`

#### Scenario: A case without a location is listed by its label
- **WHEN** a failed case has `classname="tests.a_spec.TestK"`, `name="test_a"`, `file="tests/a_spec.py"` and no `line`
- **THEN** the summary lists it with `TestK.test_a` as its only text
