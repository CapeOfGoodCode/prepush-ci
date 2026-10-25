## MODIFIED Requirements

### Requirement: The Markdown is the check run's summary under a marker
The Markdown SHALL be three consecutive lines, a blank line, and the summary of the check run unchanged (so that the failures come first in it as for a red check run). The lines are `<!-- prepush-ci:<name> -->`, `<name>` being `--name` or `prepush-ci / full`; a title line `### <name>: <text>`, `<text>` being the test counts, or `Passed` or `Failed` when there are none, and `Failed (<counts>)` for a failed result with counts; and a line that names the full sha of the commit it reports.

#### Scenario: Default marker
- **WHEN** `report --markdown` runs without `--name`
- **THEN** the first line is `<!-- prepush-ci:prepush-ci / full -->`

#### Scenario: Chosen name
- **WHEN** `--name "prepush-ci / unit"` is given
- **THEN** the first line is `<!-- prepush-ci:prepush-ci / unit -->` and the title line holds `prepush-ci / unit`

#### Scenario: The commit is named
- **WHEN** `report --markdown --commit <an earlier commit>` runs with that commit's tree
- **THEN** the third line holds the 40-hex sha of that commit and not the sha of `HEAD`

#### Scenario: The summary is the check run's
- **WHEN** `report --markdown --result passed` runs with a JUnit file of 3 passing cases and a coverage file of 94.5%
- **THEN** the Markdown holds the summary that the check run of the same inputs would hold, with `3 passed` in the title line and `94.5%` in it

#### Scenario: Failures first
- **WHEN** `report --markdown --result failed` runs with a mypy file with one error
- **THEN** the mypy error comes before the row `Check` of the table

#### Scenario: A failed result with counts says so
- **WHEN** `report --markdown --result failed` runs with a JUnit file of 3 passing cases
- **THEN** the title line is `### prepush-ci / full: Failed (3 passed, 0 failed, 0 skipped)` and the title of the check run, unchanged, is `3 passed, 0 failed, 0 skipped`
