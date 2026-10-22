# Tasks

## 1. The label

- [x] 1.1 Compute the label of a failed case in `core/report.py` (name, class part of the classname, the 200-character cut); verify with unit specs named after the scenarios of "A failed case has a label"
- [x] 1.2 Title the annotation `pytest: <label>` with the message of the case alone; verify with specs named after the scenarios of "The annotation of a failed case names the case" and "A failed case sits on its line plus one"
- [x] 1.3 List the label before the text in the summary and the Markdown; verify with specs named after the scenarios of "A listed failure is one short line"
- [x] 1.4 Run the README's sentences about the report against the head and change those the new title makes wrong

## 2. Archive

- [ ] 2.1 Run `sh scripts/ci` and verify it passes
