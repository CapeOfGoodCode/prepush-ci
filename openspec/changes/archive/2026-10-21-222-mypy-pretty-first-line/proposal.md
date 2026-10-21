Issue: #222

## Why

`mypy --pretty` wraps a long message over several lines and only the first carries `error:`. `report` reads that first line, so the annotation and the listed failure hold a message cut mid-sentence. The file, line and column are right, and `--pretty` is not mypy's default. The owner decided (#222) to keep this small: say so in the spec and in the README, change no parser.

## What Changes

- The spec states that a `--mypy` message is the text after `error:` on that line alone; the lines that follow (the rest of a wrapped message, the source line, the caret line) yield nothing, so a wrapped message is cut at the end of its first line.
- The README, in the reference of `report`, advises running mypy without `--pretty` for `report`.
- No change to the parser. The behavior is already the head's; the change pins it with a test, as terminator found it.

## Capabilities

### Modified Capabilities

- `report`: one requirement is added; no existing requirement changes.

## Impact

- A test and one sentence in the README's reference of `report`. No code of the tool, no config key, no new dependency.
