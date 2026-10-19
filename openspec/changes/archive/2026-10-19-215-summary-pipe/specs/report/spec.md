## ADDED Requirements

### Requirement: A pipe in a value stays in its cell
Every `|` in a value of the facts table of the summary SHALL be written `\|`, so that GitHub shows the whole value in its cell, also when the value is a code span. A value without a `|` SHALL be written as before.

#### Scenario: Pipe in the check
- **WHEN** the config sets `check = "sh scripts/ci | tee ci.log"` and the check run is created
- **THEN** the row `Check` of the summary has the value `` ` sh scripts/ci \| tee ci.log ` `` and no `|` in it that is not preceded by a backslash

#### Scenario: Pipe in the preflight
- **WHEN** the config sets `preflight = "make lint | cat"` and the check run is created
- **THEN** the row `Preflight` of the summary has the value `` ` make lint \| cat ` ``

#### Scenario: Pipe in a tool name
- **WHEN** `report` runs with `--tool 'a|b=1.0'`
- **THEN** the row `Tools` of the summary has the value `a\|b 1.0`

#### Scenario: Backslash before a pipe in the check
- **WHEN** the config sets `check = 'echo \| cat'` and the check run is created
- **THEN** the row `Check` of the summary has the value `` ` echo \\| cat ` ``

#### Scenario: No pipe
- **WHEN** the config sets `check = "sh scripts/ci"` and the check run is created
- **THEN** the row `Check` of the summary has the value `` ` sh scripts/ci ` ``
