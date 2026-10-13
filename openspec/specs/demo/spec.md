# demo Specification

## Purpose
The terminal demo of the README: `scripts/record_demo.py` records the real CLI in a scratch repository into `docs/assets/demo.svg`, an animated SVG of 40 to 60 seconds with visible typing, and the README embeds it before its first section; the checks keep the commands real, the output unedited and free of machine paths, and the timeline within its range.

## Requirements

### Requirement: The demo is recorded from the real tool
`scripts/record_demo.py` SHALL make an empty scratch repository with a bare remote, run each step of its list of commands there with the real `prepush-ci`, and write the asset `docs/assets/demo.svg` from the output and exit status each command really had. It SHALL show no output that a command did not print, except cutting a step's output to its first 6 lines followed by one line `…` and replacing the scratch directory with `.`.

#### Scenario: Recording a scratch repository
- **WHEN** the script runs with an output path in a temporary directory
- **THEN** it exits 0 and writes an SVG there, and the repository of the checkout has no new file

#### Scenario: Output is the real output
- **WHEN** the recorded step for the failing push is read from the asset
- **THEN** its output contains the line that the check of the scratch repository printed and the line `prepush-ci: the check failed`

#### Scenario: Long output is cut
- **WHEN** the recorded step for `init` is read from the asset
- **THEN** it has at most 7 output lines and the last one is `…`

### Requirement: No machine path in the asset
The asset SHALL contain neither the scratch directory, nor the home directory, nor the path of the interpreter that runs the script. The script SHALL fail, and write no asset, when the output of a step still holds the home directory or the interpreter's path after the scratch directory is replaced.

#### Scenario: No machine path
- **WHEN** the asset is searched for the scratch directory, the home directory and the path of the interpreter
- **THEN** none of the three is found

#### Scenario: A path that leaks
- **WHEN** the output check of the script reads the output of a step that holds the home directory or the interpreter's path
- **THEN** it fails naming the step, and the script writes no asset

### Requirement: One command regenerates the asset
The asset SHALL be regenerated with `uv run python scripts/record_demo.py`, and `--help` of the script SHALL print that command.

#### Scenario: The help names the command
- **WHEN** the script runs with `--help`
- **THEN** it exits 0 and prints `uv run python scripts/record_demo.py`

### Requirement: The install step is typed, not run
The one step that is typed and not run SHALL be `uv tool install prepush-ci`, because it needs the network and a release; every other step SHALL run. In the asset, a step that runs SHALL carry `data-run="true"` and a `data-exit`; the step that is not run SHALL carry `data-run="false"`, no `data-exit` and no output lines.

#### Scenario: Only the install is not run
- **WHEN** the steps of the script are read
- **THEN** exactly one step is marked as not run, and its command is `uv tool install prepush-ci`

#### Scenario: The asset marks the install step
- **WHEN** the steps of the recorded asset are read
- **THEN** exactly one has `data-run="false"`, it is `uv tool install prepush-ci`, it has no `data-exit` and no output lines, and every other step has `data-run="true"` and a `data-exit`

### Requirement: The demo tells the story in order
The steps of the recording SHALL run in this order: install the tool, `init` in the scratch repository, a commit typed as `PREPUSH_CI=full git commit …` whose message then carries the trailer `Prepush-CI: full`, a push refused because the full check fails, a fix and a commit typed the same way, a push that goes through because the check passes, and `prepush-ci verify` accepting the pushed commit.

#### Scenario: The statuses of the story
- **WHEN** the steps of the recorded asset are read in order
- **THEN** the refused push has a non-zero `data-exit`, the passing push and `verify` have `data-exit` 0, and the refused push comes before the passing push, and `verify` is the last step with a `prepush-ci` command

#### Scenario: The opt-in is on screen
- **WHEN** the typed commands of the asset are read
- **THEN** each commit step's `data-command` starts with `PREPUSH_CI=full ` or holds ` PREPUSH_CI=full git commit`, so the opt-in is shown on the line that needs it, and no step relies on a variable the viewer cannot see

#### Scenario: The commit has the trailer
- **WHEN** the recorded output of the step that shows the last commit message is read
- **THEN** it contains the line `Prepush-CI: full`

### Requirement: The recording does not depend on the maintainer's environment
The script SHALL set up the environment of every step itself: it SHALL remove every `PREPUSH_CI` variable it inherits, so that the only opt-in is the one typed in a step, and it SHALL put the `prepush-ci` shim first on `PATH`.

#### Scenario: An inherited opt-out
- **WHEN** the script runs with `PREPUSH_CI=off` in its environment
- **THEN** it exits 0 and the recorded story has the same statuses as with no such variable

### Requirement: The recording runs on POSIX shells
Every step SHALL run through `sh -c` and the `prepush-ci` shim SHALL be a `#!/bin/sh` script, because the steps are shell lines (`printf`, `&&`, redirects). The recording is made on a POSIX system; on Windows the specs that record are skipped with a reason that says so, and the specs that read the steps or the asset (the command check, the duration, the embed) run on every platform.

#### Scenario: Steps run through sh
- **WHEN** the script's runner and shim are read
- **THEN** each step is started as `sh -c <command>` and the shim's first line is `#!/bin/sh`

### Requirement: The recording fails on a wrong status
The recording SHALL fail, and write no asset, when a step that runs does not end with the exit status the story needs: 0 for every such step except the first push, which SHALL exit non-zero. The step that is not run has no status and is not checked.

#### Scenario: A step with the wrong status
- **WHEN** a step of the story ends with a status the story does not allow, for example the first push exits 0
- **THEN** the script exits non-zero, names the step and its status, and the asset is not written

### Requirement: Every command of the demo exists
Every `prepush-ci` invocation among the commands of the steps SHALL pass the check of the `skill` capability: it names a command of the CLI and uses only options that command accepts.

#### Scenario: The shipped steps pass
- **WHEN** the check reads the commands of the steps of `scripts/record_demo.py`
- **THEN** it finds no unknown command and no unknown option

#### Scenario: An option the CLI lacks
- **WHEN** the check reads a step whose command is ``prepush-ci run --fast``
- **THEN** it reports `--fast` as unknown to `run`

### Requirement: The asset shows the typing
In the asset, each typed command SHALL be revealed one character at a time, in as many steps as the command has characters (`data-chars`), in a monospace font; its output lines SHALL start only after its typing has ended, one after the other.

#### Scenario: One step per character
- **WHEN** a step of the asset is read
- **THEN** its `data-chars` equals the length of its `data-command`, and the reveal animation of the command has that number of steps

#### Scenario: Output follows the typing
- **WHEN** the output lines of a step are read from the asset
- **THEN** each starts at or after the end of the typing of the command, and not before the line above it

### Requirement: The animation lasts between 40 and 60 seconds
The animation SHALL run between 40 and 60 seconds from its first frame to its last, slow enough to follow the typing and read each output. The asset SHALL carry its timeline as attributes: the root `data-duration`, equal to the `animation-duration` of the cycle, and the `data-start` and `data-end` of each step, and the check SHALL measure the duration from them: it fails when `data-duration` is below 40 or above 60, when a step ends after `data-duration`, or when the two durations differ.

#### Scenario: The shipped asset is paced to be followed
- **WHEN** the check reads `docs/assets/demo.svg`
- **THEN** its `data-duration` is at least 40 and at most 60, its last step ends at or before it, and it equals the CSS `animation-duration`

#### Scenario: A recording of any speed fits
- **WHEN** the script records twice, once with `--check-delay 0` and once with `--check-delay 2` (seconds the fixture's check sleeps before it answers)
- **THEN** both assets have the same `data-duration`

#### Scenario: A long asset
- **WHEN** the check reads an asset with `data-duration` 61
- **THEN** it reports the duration as above 60 seconds

#### Scenario: A rushed asset
- **WHEN** the check reads an asset with `data-duration` 39
- **THEN** it reports the duration as below 40 seconds

#### Scenario: A step past the end
- **WHEN** the check reads an asset whose last step has a `data-end` above its `data-duration`
- **THEN** it reports that step

### Requirement: The README shows the demo near the top
`README.md` SHALL embed `docs/assets/demo.svg` as an image before its first `##` heading, through the absolute address `https://raw.githubusercontent.com/CapeOfGoodCode/prepush-ci/main/docs/assets/demo.svg` (the PyPI long description cannot resolve a relative path), with a non-empty text alternative that names the story. The file SHALL exist in the repository, and it SHALL be an SVG that parses as XML.

#### Scenario: The embed
- **WHEN** the check reads `README.md`
- **THEN** an `<img>` or image link with that address comes before the first `##` heading, and its alternative text is not empty

#### Scenario: The file exists
- **WHEN** the check resolves the address to a path in the checkout
- **THEN** the file `docs/assets/demo.svg` exists and parses as XML with an `svg` root

#### Scenario: The alternative text
- **WHEN** a reader cannot see the animation
- **THEN** the alternative text names the setup, the refused push and the passing push
