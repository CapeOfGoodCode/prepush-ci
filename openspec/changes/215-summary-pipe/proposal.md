Issue: #215

## Why

The facts table of the check run summary is a Markdown table. GitHub reads every `|` as a cell separator, also inside a code span. A `check` such as `sh scripts/ci | tee ci.log` (a pipe is common in a check) ends its cell at the pipe, leaves a backtick unclosed and drops the rest of the command; the same happens to a `preflight` with a pipe and to a tool name with one. The summary then does not name what ran, which the `report` capability already requires.

## What Changes

- A `|` in any cell of the facts table is written `\|`, the escape GitHub's table syntax gives, so the cell shows the whole text.

## Capabilities

### Modified Capabilities

- `report`: a new requirement for the cells of the facts table. The requirement "The summary names what ran" stays as it is.

## Impact

- `src/prepush_ci/core/report.py` escapes the pipe where the rows are built.
- No change to the README: it does not describe the table.
