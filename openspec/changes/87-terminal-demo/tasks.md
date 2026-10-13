# Tasks

## 1. The recording

- [ ] 1.1 Add `scripts/record_demo.py`: the fixture repository and bare remote, the shim, the list of steps, running the steps and capturing output and status, refusing a wrong status or a leaked machine path without writing, removing an inherited `PREPUSH_CI`, `--check-delay`; verify with integration specs that record into a temporary directory (statuses, trailer, the opt-in on the commit lines, real output, the cut, no machine path, the install step and its markers, `--help`), skipped on Windows with a reason
- [ ] 1.2 Write the SVG from the recording: typing as `steps(n)` reveal, output lines after the typing, the timeline attributes (`data-run`; `data-exit` only on steps that run), clearing between acts; verify with specs for `data-chars`, the order of the timeline and equal durations for `--check-delay 0` and `2`
- [ ] 1.3 Check the commands: run the steps' `prepush-ci` invocations through the check of the `skill` capability; verify with the shipped steps and an unknown option

## 2. The asset and the README

- [ ] 2.1 Record `docs/assets/demo.svg` and pace it at about 45 seconds, typing and the pause after each output slower than the first recording, and keep it between 40 and 60 seconds; verify with the duration check on the file and on crafted assets (61 seconds, 39 seconds, a step past the end)
- [ ] 2.2 Embed it in `README.md` before the first `##` heading with the absolute address and a text alternative; verify with the embed specs, and show the animation playing on the branch (raw URL at the head commit) in the pull request

## 3. Close

- [ ] 3.1 Archive the change
