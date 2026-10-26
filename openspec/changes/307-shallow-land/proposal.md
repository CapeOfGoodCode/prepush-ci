Issue: #307

## Why

In a shallow clone, `prepush-ci land 7` on a head that is one commit on top of `main` prints `not landed: main of origin has commits that the head does not contain: rebase onto main and push again` and exits 1. `main` has not moved. The clone holds too little history to show that the tip is the head's parent, and `land` reads "git cannot show it" as "the tip has commits the head lacks". The advice cannot help: the author rebases, pushes, and gets the same line. In a complete clone the same pull request lands. The spec says a tip that is not an ancestor of the head is a moved branch, and nothing says what a clone that cannot tell does.

## What Changes

- When the clone is shallow and the tip is neither an ancestor of the head nor a descendant of it, `land` pushes nothing and prints a `not landed:` line that says the clone is shallow, that it cannot tell whether the branch moved, and how to get the history (`git fetch --unshallow`, or `fetch-depth: 0` in a checkout action). Exit 1.
- Every answer a shallow clone can give stays: the tip is an ancestor of the head (lands), the head is on the branch (`already on`). A complete clone keeps the line of a moved branch.
- "Only a head on top of the tip lands" names the exception, and "No command of the head runs before the refusals that need none" lists it among the refusals decided before the `preflight`. A refused push keeps the moved line.

## Capabilities

### Modified Capabilities

- `land`: "Only a head on top of the tip lands" excepts a shallow clone that cannot tell, and "No command of the head runs before the refusals that need none" lists it; a new requirement says what it answers.

## Impact

`src/prepush_ci/land_command.py` (`_position`) and `core/land.py`. No README change: its sentences about the answer lines say nothing of shallow clones, and `docs/ci/land.yml` checks out with `fetch-depth: 0`. Out of scope: deepening the clone for the user (see the design).
