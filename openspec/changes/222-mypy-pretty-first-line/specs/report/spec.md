## ADDED Requirements

### Requirement: A mypy message is read from its first line
The message of a `--mypy` error SHALL be the text after `error:` on that line alone. The lines that follow it (the rest of a message that `mypy --pretty` wrapped, the source line, the caret line) SHALL yield no annotation and no part of the message. The README SHALL advise running mypy without `--pretty` for `report`.

#### Scenario: A wrapped message
- **WHEN** a mypy file holds `src/m.py:1:10: error: Incompatible types in assignment (expression has type`, the line `"str", variable has type "int")  [assignment]`, a source line, a caret line and `Found 1 error in 1 file (checked 1 source file)`
- **THEN** the check run has exactly one annotation, on line 1 of `src/m.py`, whose message is `Incompatible types in assignment (expression has type` and holds nothing of the following lines

#### Scenario: The README advises it
- **WHEN** the reference of `report` in the README is read
- **THEN** it advises running mypy without `--pretty` for `report`
