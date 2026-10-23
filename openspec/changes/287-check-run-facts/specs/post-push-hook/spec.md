## MODIFIED Requirements

### Requirement: The comment is the Markdown of report
The body of the comment SHALL begin with what `prepush-ci report --markdown --result passed --tree <the tree of HEAD>` prints for `HEAD`: no result files and the default name. When the recorded pass holds facts (see the `run-cache` capability), the body SHALL go on with a blank line and the block of facts defined in "The facts are one line and a collapsed block"; otherwise it SHALL end there.

#### Scenario: The text is the markdown of report
- **WHEN** the hook creates a comment for a commit whose recorded pass holds no facts
- **THEN** the body equals the standard output of `prepush-ci report --markdown --result passed --tree <the tree of HEAD>` run in that worktree

#### Scenario: The commit is named
- **WHEN** the hook creates a comment
- **THEN** the body holds the 40-hex sha of `HEAD`

#### Scenario: The facts follow the markdown
- **WHEN** the hook creates a comment for a commit whose recorded pass holds facts
- **THEN** the body starts with the standard output of `prepush-ci report --markdown --result passed --tree <the tree of HEAD>`, and the block of facts comes after a blank line

## ADDED Requirements

### Requirement: The facts are one line and a collapsed block
The block of facts SHALL start with one visible line, `Facts of the run: ` followed by the entries that the facts hold, in this order and joined by `; `: `<n> passed, <n> failed, <n> skipped`, `coverage <n>%` and `duration <d>` (the form `report` shows a duration in, such as `8m 12s`). When the facts hold more than the duration, a collapsed block SHALL follow (see "The details are collapsed"). Nothing but the facts SHALL be in the block.

#### Scenario: The visible line
- **WHEN** the facts hold 812 passed, 0 failed and 3 skipped, coverage 94.5 and 492 seconds
- **THEN** the body holds the line `Facts of the run: 812 passed, 0 failed, 3 skipped; coverage 94.5%; duration 8m 12s`

#### Scenario: Only the duration
- **WHEN** the facts hold only 492 seconds
- **THEN** the line is `Facts of the run: duration 8m 12s` and the body holds no `<details>`

#### Scenario: An older pass without facts
- **WHEN** the recorded pass has no facts
- **THEN** the body holds neither `Facts of the run` nor `<details>`

#### Scenario: Nothing of the check's output
- **WHEN** the check printed `TOKEN=abc123` and passed
- **THEN** the comment does not hold `abc123`

### Requirement: The details are collapsed
The collapsed block SHALL be a `<details>` element with the `<summary>` `Details`, holding a table of the tools (tests, coverage, ruff and mypy, each only when the facts hold it) and, when the facts hold per-file counts, a table of the test files with their passed, failed and skipped numbers, each file name as a Markdown code span. The visible line SHALL NOT be inside it.

#### Scenario: The details are collapsed
- **WHEN** the facts hold test counts, coverage, one ruff error count, and the counts of two test files
- **THEN** the body holds `<details>` after the visible line, its summary is `Details`, it holds a row for tests, coverage and ruff, and a row for each of the two files, and the visible line is not inside it

### Requirement: The facts say which run they come from
The line after the visible line of the facts SHALL say `Checked on this commit.` when the commit the facts name is `HEAD`, and otherwise `Reused from the run on <the first twelve characters of that commit>, same tree.`

#### Scenario: This commit
- **WHEN** the facts name `HEAD` as the commit that was checked
- **THEN** the second line of the block is `Checked on this commit.`

#### Scenario: An amended commit
- **WHEN** the pass was recorded for a commit that was then amended with a new message (same tree) and the amended commit was pushed with `--no-verify`
- **THEN** the second line of the block is `Reused from the run on <the first twelve characters of the earlier commit>, same tree.`

#### Scenario: A pass that skipped the check
- **WHEN** a commit was pushed twice and the second push skipped the check because the pass was cached
- **THEN** the comment still holds the facts of the first run and says `Checked on this commit.`
