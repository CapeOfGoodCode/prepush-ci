## Decisions

- **The failing line is the last line at the first column that begins `<file of the case>:<n>:`, with or without text after the colon.** pytest prints one such line per frame: `<path>:<n>:` under `--tb=long`; `<path>:<n>: in <func>` for the frames above the last under `--tb=auto` (the default) and for all of them under `--tb=short`; `<path>:<n>: <ErrorName>` for the raising frame under `long` and `auto`. The last one in the case's own file is the deepest frame there, and the raising line when it is there: the same line under the three styles (see "Run against the head").
- **A frame's line number is one to nine digits and not 0.** The number is read from text a runner writes, so it needs a bound before it is made an integer (Python refuses past 4300 digits); nine digits holds any real file, and a line 0 does not exist. A line with another number is skipped like a line of another file: the last valid frame still wins, and with none the annotation keeps `line` + 1.
- **Only the file of the case.** A frame in another file (a helper module) is never taken: the annotation's `path` is the file of the case, and comparing two spellings of another path would be a guess. A failure that names only another file keeps `line` + 1 of the test.
- **No traceback line, no change.** A case whose failure text has no such line (an empty text, another runner such as `node --test`) keeps `line` + 1 and its message as it is, apart from the name below.
- **The name goes in the message, not the title.** "Failures become annotations" fixes the title as the name of the tool. The message of the annotation of a failed case begins with the name of the case on its own line, then the message of the case. The list of failures in the summary is not changed: its text is still the message of the case.

## Run against the head

pytest 9.1.1 with `-o junit_family=xunit1`, a test `test_double` parametrized over `[1, 2]` whose decorator is on line 4 and whose `assert` is on line 7, and a `test_helper` that calls a `helper()` raising on line 11 of the same file:

- Both parametrized cases have `line="3"` (0-based, so line 4 is the decorator) and a failure text that ends in `test_demo.py:7: AssertionError`.
- `test_helper` has `line="13"` and a failure text that holds `test_demo.py:15: ` (the call, nothing after the colon) and ends in `test_demo.py:11: ValueError`.
- At `4a7ed61`, `report --result failed` sends both parametrized annotations on line 4 with the messages `assert 2 == 1` and `assert 4 == 2`, neither naming its case.
- With a test at line 9 of `test_demo.py` that calls `helper()` (line 5, same file), which calls `helpers.boom()` (raising at `helpers.py:2`): `--tb=auto` prints `test_demo.py:9: `, `test_demo.py:5: in helper` and `helpers.py:2: ValueError`; `--tb=short` prints `test_demo.py:9: in test_chain`, `test_demo.py:5: in helper` and `helpers.py:2: in boom`; `--tb=long` prints `test_demo.py:9:`, `test_demo.py:5:` and `helpers.py:2: ValueError`. The rule gives line 5 under all three.
