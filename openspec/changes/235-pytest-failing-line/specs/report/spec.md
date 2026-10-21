## MODIFIED Requirements

### Requirement: A failed case sits on its line plus one
`--junit` SHALL yield one annotation per failed case that has a `file` and a `line` attribute, with the message of the case, after its name (see "The annotation of a failed case names the case"). The `line` of a case is 0-based, as pytest writes it, so the annotation's `start_line` and `end_line` SHALL be `line` + 1, unless the failure names a line of the file of the case (see "A failed case sits on the line its failure names").

#### Scenario: A failing test on its line
- **WHEN** a JUnit file holds a failed case with `file="tests/a_spec.py"` and `line="117"`, whose failure text names no line, and `report --result failed` runs with an app
- **THEN** the check run has one annotation with `path` `tests/a_spec.py`, `start_line` 118, `end_line` 118, `annotation_level` `failure` and the title `pytest`

#### Scenario: A failing test without a location
- **WHEN** a JUnit file holds a failed case with no `line` attribute
- **THEN** the check run has no annotation for it and the counts still hold it as failed

## ADDED Requirements

### Requirement: A failed case sits on the line its failure names
When the failure text of a failed case with a `file` and a `line` attribute holds lines that begin, at their first column, with the `file` of the case, `:`, a line number and `:`, the annotation SHALL sit on the number of the last of them, as `start_line` and `end_line`, instead of on `line` + 1. A line number is one to nine digits and not 0; any other number makes the line no such line. Text after the second colon makes no difference. With no such line the annotation SHALL stay on `line` + 1.

#### Scenario: A decorated test
- **WHEN** a failed case has `file="test_demo.py"` and `line="3"`, and its failure text ends in the line `test_demo.py:7: AssertionError`
- **THEN** its annotation has `start_line` 7 and `end_line` 7

#### Scenario: The failure is raised by a helper in the same file
- **WHEN** a failed case has `file="test_demo.py"` and `line="13"`, and its failure text holds the lines `test_demo.py:15: ` and `test_demo.py:11: ValueError`, in that order
- **THEN** its annotation has `start_line` 11, whatever text follows the colon of `test_demo.py:15: `

#### Scenario: A call into another file, from a helper of the case's file
- **WHEN** a failed case has `file="test_demo.py"` and `line="7"`, and its failure text holds, in this order, the lines `test_demo.py:9: `, `test_demo.py:5: in helper` and `helpers.py:2: ValueError`
- **THEN** its annotation has `start_line` 5 and `end_line` 5, the line of the deepest frame in `test_demo.py`

#### Scenario: Every frame prints in the short style
- **WHEN** a failed case has `file="test_demo.py"` and `line="7"`, and its failure text holds, in this order, the lines `test_demo.py:9: in test_chain`, `test_demo.py:5: in helper` and `helpers.py:2: in boom`
- **THEN** its annotation has `start_line` 5, as under the long and the default styles

#### Scenario: The failure names only another file
- **WHEN** a failed case has `file="test_demo.py"` and `line="13"`, and its failure text ends in the line `helpers.py:4: ValueError` and holds no other line of the form
- **THEN** its annotation is on `test_demo.py`, `start_line` 14

#### Scenario: A line number of ten digits is no frame
- **WHEN** a failed case has `file="test_demo.py"` and `line="7"`, and its failure text holds, in this order, the lines `test_demo.py:5: in helper` and `test_demo.py:1234567890: boom`
- **THEN** its annotation has `start_line` 5, the last line whose number is of one to nine digits

#### Scenario: A line number of 0 is no frame
- **WHEN** a failed case has `file="test_demo.py"` and `line="7"`, and its failure text holds, in this order, the lines `test_demo.py:5: in helper` and `test_demo.py:0: boom`
- **THEN** its annotation has `start_line` 5

#### Scenario: The only frame has the line number 0
- **WHEN** a failed case has `file="test_demo.py"` and `line="7"`, and the only line of its failure text of the form is `test_demo.py:0: boom`
- **THEN** its annotation has `start_line` 8

#### Scenario: A line of code that only looks like one
- **WHEN** a failed case has `file="test_demo.py"` and `line="3"`, and the only line of its failure text that holds `test_demo.py:9: ` is indented by four spaces
- **THEN** its annotation has `start_line` 4

### Requirement: The annotation of a failed case names the case
The `message` of the annotation of a failed case SHALL begin with the `name` of the case, followed by a line break and the message of the case, so that the annotations of the cases of a parametrized test differ. Its title SHALL stay `pytest`.

#### Scenario: Two cases of a parametrized test
- **WHEN** a JUnit file holds two failed cases named `test_double[1]` and `test_double[2]` with the same `file` and `line` and the failure messages `assert 2 == 1` and `assert 4 == 2`
- **THEN** the check run has two annotations, whose messages are `test_double[1]` and `assert 2 == 1` on a second line, and `test_double[2]` and `assert 4 == 2` on a second line, and whose titles are `pytest`

#### Scenario: The summary keeps the message
- **WHEN** a failed case named `test_a` with a location has the message `AssertionError: assert a == b`
- **THEN** the summary lists the case with `AssertionError: assert a == b`, and its annotation message begins with `test_a`
