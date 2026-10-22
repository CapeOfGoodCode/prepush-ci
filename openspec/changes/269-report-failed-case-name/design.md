## Context

`junit_failures` reads a failed case's `name`, `file`, `line` and text. The name begins the message of the annotation (#235, "The annotation of a failed case names the case") and is listed in the summary only for a case without a location. The annotation's title is the tool, `pytest`.

## Verified with the tools

pytest 9.1.1, `--junitxml`, one parametrized function and one method in `tests/a_spec.py`:

```
<testcase classname="tests.a_spec" name="test_split[three-ways]" …>
<testcase classname="tests.a_spec" name="test_split[two]" …/>
<testcase classname="tests.a_spec.TestK" name="test_in_class" …>
```

For a function the `classname` is the module of the file in dots, so it only repeats the `file` that the annotation sits on; for a method it ends with the class. (The `file` and `line` attributes come with `junit_family=xunit1`; the default writes neither.)

## Decisions

- **The label is the name with the class part of the classname.** The module part of the `classname` is the `file` again, which the line already shows; keeping it would make every label start with `tests.unit.` and push the case out of a 200-character line. A `classname` that does not start with the module of the file (or a case with no file) is kept whole in front of the name, so nothing it says is lost.
- **The title carries the label, the message does not repeat it.** The annotation shows title and message together; with the name in both, every annotation would read twice. The old reason for the name in the message (cases of one parametrized test differ) holds for the title.
- **The label is cut like the text.** At most 200 characters with `…` as the 200th, in the summary and the title, so a title is at most 208 characters and far inside GitHub's 255.
- **A failed case with a location shows label and text.** A case without one shows the label alone, as it showed the name; its text would repeat it.
