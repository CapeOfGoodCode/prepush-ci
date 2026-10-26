## Context

`land` asks git two questions after it fetched the head and the tip: is the head the tip or an ancestor of it, is the tip an ancestor of the head (`git merge-base --is-ancestor`). Two "no" answers mean the branch moved. In a shallow clone, "no" can also mean "the history that would say yes is not here".

Reproduced on `main` at 30b772f, git 2.39.5, with the script of #307 (`origin` a bare repository on the same machine, `git clone --depth 1`, then `git fetch --depth 1` of the pull ref and the results):

```
$ git rev-parse --is-shallow-repository
true
$ git merge-base --is-ancestor <tip> <head>; echo $?
1
$ git merge-base --is-ancestor <head> <tip>; echo $?
1
$ prepush-ci land 7; echo status=$?
not landed: main of origin has commits that the head does not contain: rebase onto main and push again
status=1
$ git fetch --unshallow origin
$ prepush-ci land 7; echo status=$?
landed: 6168efa502f3c511d68377e136f86ac1304f5dd6 on main
status=0
```

The same clone fetched with `--depth 2` holds the head's parent, and `land` lands it (`merge-base --is-ancestor <tip> <head>` exits 0). With `main` advanced by another commit after the head was made, the depth-1 clone prints the same moved line as above; after `git fetch --unshallow` it still does, and that one is true. So git gives the same two exit codes for a branch that moved and for one it cannot see.

## Decisions

- **Refuse with a line of its own; do not land, do not deepen.** A shallow clone gives the same two answers for a moved branch and for missing history, so landing on the guess could push a head onto a branch it does not follow (origin refuses a non-fast-forward push, but `land` checks before it pushes, and before it runs the preflight with the author's code). Deepening the clone on its own makes `land` download a history the user chose not to have, and no depth is known to be enough. One command fixes it and the line names it; the same advice `verify` gives for a missing commit.
- **Only the two-"no" case changes.** A "yes" is true in any clone, so a shallow clone that can show the tip below the head still lands and a head on the branch is still `already on`.
- **The line says "cannot tell", not "moved".** After `--unshallow` a truly moved branch gets the moved line, as in a complete clone.
- **Shallow means `git rev-parse --is-shallow-repository` prints `true`.** The test `verify` already uses for its fetch advice. A shallow clone whose history happens to be complete enough still gets the line when the answer is "no": the clone cannot know, and the cost is one command.
- **The line names `git fetch --unshallow` and `fetch-depth`**, as `verify` does for a missing commit, so one phrase serves a person and a workflow.
- **Only the decision before the push changes.** After `origin` refuses the push, the moved line stays: it is said because the tip `origin` lists then is a different sha, a fact, not a guess from missing history, and the clone has fetched that tip down to the head and the old tip.
- **The shallow refusal is decided before the `preflight`**, like every refusal that needs no command of the head: "No command of the head runs before the refusals that need none" lists it, and a scenario writes a file from the `preflight` to show it did not run.
