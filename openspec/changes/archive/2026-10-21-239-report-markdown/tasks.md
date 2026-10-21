# Tasks

## 1. Print the result as Markdown

- [x] 1.1 Add `report --markdown`: the summary of the check run on standard output behind the marker and the commit line, nothing posted, no token, app, `origin` or network needed; verify with specs for the marker with the default and a chosen name, the commit line, the failures first, a green and a red run, no request to a stub API, no credentials, no `origin`, the refusals (`--start`, a name with `--` or a line break, a tree that is not the commit's) and the help listing the flag
- [x] 1.2 Name `--markdown` in the reference of `report` in the README, run against the head, and reword the Purpose of `openspec/specs/report/spec.md` (it says `report` posts) when archiving

## 2. Tell the agent to post it

- [x] 2.1 Add the instruction to the list of the documentation step of `SKILL.md` (the section later sessions read), with the command written as an agent runs it, the marker and the ban of `--edit-last`; verify with specs that read the skill, and with "Every command in the skill exists" passing
- [x] 2.2 Run `sh scripts/ci` and verify it passes
