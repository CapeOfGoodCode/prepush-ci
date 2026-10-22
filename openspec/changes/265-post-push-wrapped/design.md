## Context

`is_push` splits a command line at separators and looks at the first words of each command. For `(time git push) 2>&1 | tail` the command is `(time git push)`: its first word is `(time`, not `git`, so it is not read as a push (#265).

## Verified with the tools

GNU bash 5.2.15 and coreutils 9.1 (`env`, `timeout`), with a stub `git` on the `PATH` that prints `GIT RAN: <arguments>`; every line below makes the shell run `git push`:

```
$ bash -c '(time git push --force-with-lease) 2>&1 | tail -25'   -> GIT RAN: push --force-with-lease
$ bash -c 'env A=1 git push'                                      -> GIT RAN: push
$ bash -c 'timeout -k 5 60 git push'                              -> GIT RAN: push
$ bash -c 'bash -c "git push"'                                    -> GIT RAN: push
$ bash -c 'echo $(git push)'                                      -> GIT RAN: push
$ bash -c 'echo `git push`'                                       -> GIT RAN: push
$ bash -c 'echo "$(git push)"'                                    -> GIT RAN: push
$ bash -c 'nohup git push'  'command git push'  'exec git push'  'time -p git push'  '! git push'  -> GIT RAN: push (each)
$ bash -c 'if true; then git push; fi'  '{ git push; }'          -> GIT RAN: push
$ bash -c 'echo git push | xargs'  'sh -c "echo git push"'        -> git push   (prints the words, runs nothing)
```

## Decisions

- **Separators, not a shell parser.** `(`, `)` and backticks outside quotes end a command, like `;`. That covers a subshell, `$(…)` and `` `…` `` with the code that already exists. A substitution inside double quotes (`echo "$(git push)"`) runs in the shell but stays one quoted word here; not recognized, and said so.
- **A function defined on the line is a push.** `f() { git push; }; f` runs one, and the separators and the keyword `{` already read it as one; an alias or a function defined outside the line cannot be seen, and is named in the README as not recognized.
- **A closed list of wrappers, not "any first word".** The words listed are those an agent puts in front of a push; each is read with the options that take a value (`env -u NAME`, `env -C dir`, `timeout -k t`, `timeout -s sig`) and the one duration word of `timeout`. Any other wrapper (`sudo`, `xargs`, `eval`, `ssh host`) leaves the push unrecognized: the hook stays silent, as before, and the README names them. Guessing that any unknown word wraps the next command would count `echo git push` as a push.
- **`sh`, `bash` and `zsh` with `-c` are read recursively.** The script is a command line like any other, so the same function reads it; the depth is the nesting of quotes. The name is matched as written (no path), and the options before the script must all start with `-` (`-c`, `-lc`, `-e -c`); `bash -o pipefail -c …` is not recognized.
- **Keywords are skipped like wrappers.** `if git push; then`, `{ git push; }` and `! git push` run a push; `echo then git push` does not, since only leading words are skipped.
- **The landing check stays the judge.** A command wrongly counted as a push costs nothing: the hook still acts only when `refs/remotes/origin/<branch>` is `HEAD`, a trailer commit and a recorded pass exist. Recognizing more forms cannot post a wrong comment.
