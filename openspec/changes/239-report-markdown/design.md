## Context

A session that cannot reach the API still has a way to write on the pull request: the agent's GitHub tool or `gh`. The tool's part is to produce the text from the facts it already knows (commit, tree, check, preflight, tools, counts, failures); posting stays with the agent.

## Verified with the tool

`gh version 2.102.0`, `gh pr comment --help`:

```
      --edit-last        Edit the last comment of the current user
```

`--edit-last` edits the last comment of the user, whatever it says. In a session that comments for other reasons it would overwrite the wrong one, so the skill finds the comment by the marker.

## Decisions

- **Only `report --markdown` writes the text; the hook does not.** The pre-push hook is the path the invariant rests on; a file it wrote into the worktree could dirty it and refuse the next push, and a session that cannot reach the API is the case where nothing else is promised anyway. The agent runs one more command after the push.
- **The layout is the check run's.** After the marker and the title line, the text is the summary of the check run, unchanged, so a human reads the same in both places and the failures-first rule holds in both.
- **The marker is `<!-- prepush-ci:<name> -->`, `<name>` the `--name` or `prepush-ci / full`.** One comment per check name. A name that holds `--` or a line break would close the comment early, so `--markdown` refuses it (exit 2); the check run keeps accepting it.
- **The result is `--result passed|failed`, as for a post.** The skill passes `passed`: the push that comes before it ran the check. `--markdown` does not combine with `--start`, which has nothing to show on a pull request.
- **The commit line is what makes a stale comment visible.** The text names the full sha; the reader compares it with the head of the pull request. No timestamp, so the same inputs give the same text and an update that changes nothing changes nothing.
- **Inputs are read and checked as for a post** (tree, config, JUnit, ruff, mypy, coverage), so a comment never shows a state the session did not check. Annotations are not produced.
- **The instruction goes into the `CLAUDE.md` section, not a step of the setup.** `SKILL.md` runs once; the sessions that push afterwards read only the section its documentation step has the agent write. The eleven existing `report` requirements that speak of posting (what is printed, the exit status, where and to which address it is posted, the credentials, the key and signer, the commit status, completing a run, annotations and their batches) are limited to a run without `--markdown`, so that the archived spec holds no two SHALLs that cannot both be true.
