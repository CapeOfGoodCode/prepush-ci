Issue: #87

## Why

The first thing a reader of the README should see is the tool working: how a repository is set up on the command line, what a refused push looks like and what a passing one looks like. Prose and a command reference make a reader assemble that picture; the maintainer asked for an animation with the typing visible, as in a real terminal (#1, the README), and then, on seeing the first recording at 29 seconds, for a slower pace even if it runs longer, about 45 seconds (PR #143).

## What Changes

- A script, `scripts/record_demo.py`, records the demo: it makes an empty scratch repository with a bare remote, then types and runs a fixed list of commands there with the real `prepush-ci`, and writes `docs/assets/demo.svg` from what the commands really printed. One command regenerates the asset: `uv run python scripts/record_demo.py`.
- The story, in order: install the tool, set the repository up with `init`, commit typed as `PREPUSH_CI=full git commit …` so the opt-in is on screen and the trailer is written, push with a failing full check (the push is refused), fix and push again with a passing check (the push goes through), then `verify` accepts the pushed commit.
- The asset is one animated SVG: commands appear character by character, output lines follow, and the whole cycle lasts between 40 and 60 seconds, slow enough to follow the typing and read each output. SVG plays inline in a GitHub README through `<img>` and in the PyPI long description.
- `README.md` embeds the SVG before its first section, with a text alternative.
- The recording is made on POSIX shells (steps run through `sh -c`); the checks that read the asset or the steps run on every platform.
- Specs keep the demo true: the commands of the script exist in the CLI (the check of the `skill` capability), the asset is recorded from real runs, and its duration, between 40 and 60 seconds, is measured from the asset.

## Capabilities

### New Capabilities

- `demo`: the recording script, the asset and the README embed.

### Modified Capabilities

None. The embed requirement lives in `demo`, not in `readme`, so this change and #139 (a change to `readme`) do not both modify one spec.

## Impact

- New: `scripts/record_demo.py`, `docs/assets/demo.svg`, `tests/integration/demo_spec.py`.
- `README.md`: one image near the top.
- No runtime dependencies and no recording tool to install: the script uses only the standard library and git, and the tool under recording.
