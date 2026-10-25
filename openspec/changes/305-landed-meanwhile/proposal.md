Issue: #305

## Why

Two runs of `land` can land the same head at the same time: two reviewers approve in the same second under the workflow of #295, or two people run `land`. The run that loses the push finds `origin` refused it and sees that the tip moved, so it prints `not landed: ... rebase onto main and push again` and exits 1, though the head is the new tip. The author reads that advice on a pull request that has merged. The spec says a branch that moved gets the moved line, and nothing says a head that is on the branch by then is a landing.

## What Changes

- After `origin` refuses the push, `land` fetches the tip it then lists. When the head is the tip, or an ancestor of it, the landing is done: `landed: <sha> already on <branch>`, exit 0, the line of a head found on the branch before the push.
- A tip that does not contain the head, a refusal with the tip unchanged, and a tip or branch `land` cannot read or fetch keep the `not landed:` lines they have, with exit 1: `land` never claims a landing it did not see.
- "A refused push is reported, never forced" makes its exit status and line depend on the head not being on the branch, and names the new requirement.

## Capabilities

### Modified Capabilities

- `land`: "A refused push is reported, never forced" excepts a head already on the branch; a new requirement says what such a refusal answers.

## Impact

`src/prepush_ci/land_command.py` (the check after a refused push) and `core/land.py`. No README change: its sentence about the answer lines says nothing of this case. Out of scope: how the workflow of #295 reports a run (it prints what `land` prints).
