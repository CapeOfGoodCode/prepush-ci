# Design

## Context

`install` writes manager entries that start `prepush-ci` from `PATH` (specs `install`, "Entries are portable"). #69 shows that this blocks every commit and push of a contributor who lacks the tool; the native hooks do not (spec "A missing interpreter"). See `proposal.md` for the why, the delta spec for the behavior.

## Goals / Non-Goals

**Goals:** a contributor without `prepush-ci` can commit; a push without the tool is refused with a message that says why, as the native `pre-push` does.

**Non-Goals:** making the tool available to such a contributor (README and skill wording, #86 and #15), a `doctor` check for it, any change to the native hooks.

## Decisions

- **Guard the entries; do not specify "a manager entry blocks everyone".** The issue offers both. A docs contributor who cannot commit is a worse outcome than the cost of a four-line guard, and the native hooks already behave that way, so a team's choice of manager does not change what a missing tool means.
- **`commit-msg` warns and passes; `pre-push` refuses.** Same as the native hooks. A commit that never got the trailer demands no check on the server, so a lost trailer costs nothing. A push is different: a commit that carries the trailer can reach someone without the tool by rebase or cherry-pick, and its new sha was never checked. Refusing keeps "a trailer on the remote implies the check passed on exactly that commit" for every push path that runs the hook. A contributor who knowingly pushes without the tool has `--no-verify`.
- **The guard is `command -v prepush-ci`, written into each entry.** The entries are the only code that runs when the tool is absent, so the guard cannot live in the tool. `command -v` is POSIX `sh`; husky and lefthook already run their lines through `sh`, and for pre-commit the entry becomes `sh -c '…' prepush-ci` (`language: system` only needs `sh`, which git hooks have on every platform, Git for Windows included).
- **The warning is not a new phrase per manager.** All six messages contain `not on PATH`; the push messages add `cannot be checked`. One string to test, one to grep for in a bug report.
- **`verbose: true` on the pre-commit `commit-msg` hook.** Run below: without it pre-commit hides the output of a hook that passes, so the warning is never shown. The cost is three lines (`- hook id`, `- duration`, blank) on each commit, also when the tool is found. `pre-push` needs no setting: a failing hook's output is always shown.
- **The lefthook scenarios run the `run:` line through `sh`; lefthook is not added as a dev dependency.** `install` writes a line, and the line is all that is under test; running the real `lefthook` would add a dependency to every CI job (Windows included) to test lefthook's own dispatch. The husky scenarios already work this way. pre-commit is a dev dependency already, so its scenarios stay end to end.
- **The entry text is specified, not left to the tests.** A new requirement says every entry SHALL contain `prepush-ci hook <name>` (the guarded entries still do), and the new requirements say what it does without the tool. The "lefthook entries" scenario that compared the whole line is MODIFIED to "contains"; "pre-commit entries" and "husky entries" stay as they are, because adding the sentence to them would push each past the 500 characters `openspec validate --strict` allows a requirement. The unit tests that compared the whole unguarded text (`hook_managers_spec.py`, `install_managers_spec.py:607`) change to "contains", and the tool-found scenarios keep the end-to-end check.
- **Doctor is not touched.** The guarded entries still contain `prepush-ci hook <name>`, which its hook checks search for (spec `doctor`, hook checks).

## Risks / Trade-offs

- [A contributor without the tool cannot push until they install it or use `--no-verify`] → the message says it; the server-side CI gate demands the check for a commit without the trailer anyway.
- [Windows: the pre-commit entry needs `sh` on `PATH` inside pre-commit; not run here, only Linux was available] → git for Windows runs hooks from its own `sh`, which puts its `usr/bin` on `PATH`; the Windows job of `scripts/ci` runs the same integration specs, and a red result there is a finding for the builder, and the pre-commit scenarios must run there, not skip.
- [The entries are longer and harder to read] → they sit in a block marked `# prepush-ci: begin/end` that nobody edits by hand; `install` rewrites it.

## Tools run

Versions: git 2.39.5, pre-commit 4.6.2, lefthook 2.2.2 (installed ad hoc with `uv pip install lefthook` for the real-dispatch runs; the project does not carry it), `sh` is dash. "Without the tool" is `PATH=/usr/bin:/bin`, "with" adds the virtualenv of this repository. Each scratch repository has an empty bare remote and a first commit pushed with `--no-verify`.

**pre-commit.** `.pre-commit-config.yaml` after `pre-commit install` (three hook types):

```yaml
- id: prepush-ci-commit-msg
  name: prepush-ci commit-msg
  entry: sh -c 'if command -v prepush-ci >/dev/null 2>&1; then exec prepush-ci hook commit-msg "$1"; else echo "prepush-ci is not on PATH, so no trailer is written - install it" >&2; fi' prepush-ci
  language: system
  stages: [commit-msg]
  verbose: true
- id: prepush-ci-pre-push
  name: prepush-ci pre-push
  entry: sh -c 'if command -v prepush-ci >/dev/null 2>&1; then exec prepush-ci hook pre-push; else echo "prepush-ci is not on PATH, so this push cannot be checked - install it" >&2; exit 1; fi' prepush-ci
  language: system
  stages: [pre-push]
  pass_filenames: false
  always_run: true
```

```
$ PREPUSH_CI=full PATH=/usr/bin:/bin git commit -m plain
prepush-ci is not on PATH, so no trailer is written - install it
[main b6ba7f6] plain                                   (rc=0, message has no trailer)
$ PATH=/usr/bin:/bin git push origin main
- exit code: 1
prepush-ci is not on PATH, so this push cannot be checked - install it
error: failed to push some refs to '../pc-r.git'      (rc=1)
$ PREPUSH_CI=full PATH=<venv>:/usr/bin:/bin git commit -m "with tool"
prepush-ci commit-msg....................................Passed
- hook id: prepush-ci-commit-msg
- duration: 2.71s
[main 91832c0] with tool again                         (message ends with "Prepush-CI: full")
$ PATH=<venv>:/usr/bin:/bin git push origin main
prepush-ci pre-push......................................Passed   (rc=0)
```

The same run without `verbose: true`: the commit succeeded with `commit-msg ... Passed` and no warning on the screen.

**lefthook.** `run:` lines, `use_stdin: true` on `pre-push`:

```yaml
run: if command -v prepush-ci >/dev/null 2>&1; then prepush-ci hook commit-msg {1}; else echo "prepush-ci is not on PATH, so no trailer is written - install it" >&2; fi
run: if command -v prepush-ci >/dev/null 2>&1; then prepush-ci hook pre-push; else echo "prepush-ci is not on PATH, so this push cannot be checked - install it" >&2; exit 1; fi
```

```
$ PREPUSH_CI=full PATH=<lefthook>:/usr/bin:/bin git commit -m plain
┃  prepush-ci ❯
prepush-ci is not on PATH, so no trailer is written - install it
✔️ prepush-ci (0.00 seconds)                           (rc=0, no trailer)
$ PATH=<lefthook>:/usr/bin:/bin git push origin main
exit status 1                                          (rc=1, push refused)
$ … with the virtualenv on PATH: the commit gets "Prepush-CI: full", the push passes (rc=0)
```

The scenarios run the `run:` line without lefthook, `{1}` replaced by a message file, ref line on standard input for `pre-push` (`bash run.sh`; `V` is this repository's virtualenv, `.prepush-ci.toml` holds `check = "true"` in the last run):

```
$ PREPUSH_CI=full PATH=/usr/bin:/bin sh -c "<commit-msg run line>"
prepush-ci is not on PATH, so no trailer is written - install it
rc=0 msg=add x
$ echo "<ref line>" | PATH=/usr/bin:/bin sh -c "<pre-push run line>"
prepush-ci is not on PATH, so this push cannot be checked - install it
rc=1
$ PREPUSH_CI=full PATH=$V:/usr/bin:/bin sh -c "<commit-msg run line>"
rc=0, message file: "add x", blank line, "Prepush-CI: full"
```

lefthook's `{1}` template is still replaced by the message file; the braces of the shell lines are not used (no `{ …; }`), so lefthook has nothing to misread.

**husky.** The hook files run with `sh` as the specs do (`sh .husky/commit-msg msg`); `commit-msg` and a `pre-push` block that keeps the `refs=$(cat)` and `exec <<…` lines of the existing block:

```
if command -v prepush-ci >/dev/null 2>&1; then
  prepush-ci hook commit-msg "$1" || exit $?
else
  echo "prepush-ci is not on PATH, so no trailer is written - install it" >&2
fi
```

```
$ PREPUSH_CI=full PATH=/usr/bin:/bin sh .husky/commit-msg msg
prepush-ci is not on PATH, so no trailer is written - install it
later line ran                                         (rc=0, msg unchanged)
$ PREPUSH_CI=full PATH=<venv>:/usr/bin:/bin sh .husky/commit-msg msg
later line ran                                         (rc=0, msg ends with "Prepush-CI: full")
$ echo "<ref line>" | PATH=/usr/bin:/bin sh .husky/pre-push origin url
prepush-ci is not on PATH, so this push cannot be checked - install it   (rc=1, "later line" not printed)
```

`pre-push` is the existing block with `if command -v prepush-ci …; then printf … | prepush-ci hook pre-push "$@" || exit $?; else echo … >&2; exit 1; fi` in place of the single pipeline, before the `exec <<` lines.
