## Decisions

- **Escape in the table, not in `code_span()`.** `|` is special to the table, not to a code span, so the rows are escaped where they are joined into the table. One rule then covers every cell, the check, the preflight and the tools, and a cell that is not a code span (`Tools`).
- **`\|`, nothing else.** GitHub's table syntax unescapes `\|` to `|` before it reads the cell, also inside a code span, so the code span shows the pipe. An entity (`&#124;`) would be shown as typed inside a code span.
- **Known limit.** A backslash right before a pipe is kept as typed and the pipe is escaped after it (`echo \| cat` is written `echo \\| cat`). In a code span (`Check`, `Preflight`) GitHub shows `echo \| cat`, backslash kept. Only in `Tools`, which is not a code span, GitHub shows `a|b 1.0` for `a\|b`, the backslash lost; the cell stays whole and nothing after it is lost. The spec does not try to show that backslash.
