## Decisions

- **First line only, not continuation lines.** The owner chose it in #222: only the message text is cut, the file, line, column and the failure itself are right. Reading continuation lines (up to the next `error:`, `note:` or source-and-caret block) is left until a wrapped message bothers someone.
- **A new requirement, not a change to "Ruff and mypy output is read".** That requirement's text stays true; the new one adds the limit, so no scenario of the old one is touched.

## Run against the head

mypy 2.4.0 (`uvx mypy --pretty --show-column-numbers src/m.py`, `src/m.py` = `x: int = "a"`):

```
src/m.py:1:10: error: Incompatible types in assignment (expression has type
"str", variable has type "int")  [assignment]
    x: int = "a"
             ^~~
Found 1 error in 1 file (checked 1 source file)
```

`prepush-ci report --markdown --result failed --tree <tree> --mypy m.txt` on that file at `07ad0e7` lists one failure, ``mypy `src/m.py:1` `Incompatible types in assignment (expression has type` ``. One annotation, the first line of the message, as the requirement says. The `Found 1 error` line keeps the file valid.
