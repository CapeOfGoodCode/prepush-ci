## Decisions

- **Inside the two existing checks, no seventh check.** The report is "six checks" in five requirements and a dozen scenarios, and the closing line counts "of six". A check that says what the hook runs belongs to the lines about the hooks, which already fail together when the manager is not set up.
- **A difference fails the check; there is no warning.** `doctor` has `ok`, `fail` and `skip`, and its exit status is 0 only when every line starts with `ok`. A hook that runs another version than the one `doctor` reports is the very case the issue calls a false `ok`; a warning that leaves the exit status at 0 would be ignored by the scripts that read it.
- **The whole `--version` line is compared, not a version number.** Two builds of the same version number from different commits are different tools; the line carries what the `version` capability (#236) says about the build. The requirement names the line, not its form, so it holds with or without that suffix.
- **Missing, failing and silent executables fail too.** A hook that finds no `prepush-ci` fails at every commit (below), so `ok` would be wrong; an executable that cannot say its version cannot be shown to be the same. They are the same fix: put the right one on `PATH`.
- **10 seconds, then the process is ended.** A shim that prompts or waits for a network must not hang `doctor`; `--version` of a healthy install answers in well under one second.
- **Husky and lefthook are covered, not only pre-commit.** Their files start `prepush-ci` from `PATH` too (`install`, "The tool is found without PATH"). Husky 9 puts `node_modules/.bin` on the `PATH` of its hooks; a `prepush-ci` installed there is not seen by `doctor`, which reads its own `PATH`. That case is left out, and a user who has it sees the lines name a different path than the one the hook uses.
- **The look-up is git's own shell, not a copy of its rules.** `doctor` runs `command -v prepush-ci` and then `prepush-ci --version` as the command of a git alias (`git -c alias.…=!<command>`), which git runs in the shell it runs hooks with, from the top of the worktree. An empty `PATH` entry is then the repository root, a relative one is relative to it, and on Windows only the names that Git's sh runs count (`prepush-ci.cmd` and `.bat` do not), and an extensionless script runs through that sh. `shutil.which` and a walk of `PATH` in Python differ from it in each of these.
- **A doctor that cannot read its own version fails; it does not skip.** `doctor` run from source that is no installed distribution (for example `PYTHONPATH=src python -m prepush_ci doctor` in a checkout) has nothing to compare the hook's executable with, so it cannot show the hook runs the same version. `skip` is for a check that does not apply, and this one does; a `skip` would let the manager checks pass on the false `ok` the issue is about. The cost is that a source run with a manager set up exits 1; native hooks and the failures that are already there do not depend on the version and stand as they are.
- **The `PATH` of `doctor` stands for the hook's.** A hook run from a graphical git client may have a shorter `PATH`; `doctor` cannot know it.
- **`install` is left alone.** The issue allows either place; `doctor` is where the other checks of the hooks are, and `install` does not know which version the user wants on `PATH`. Its `next: run pre-commit install` when pre-commit is already active is a separate matter and not part of this change.

## Run against the tools

pre-commit 4.7.0, git 2.39.5, uv 0.13.4. A repository whose `.pre-commit-config.yaml` has the `local` hook `entry: prepush-ci hook pre-push`, `language: system`, `stages: [pre-push]`, after `pre-commit install --hook-type pre-push`, and `pre-commit run --hook-stage pre-push --all-files`:

| `PATH` | result |
| --- | --- |
| holds a directory with an executable `prepush-ci` that exits 0 | `prepush-ci pre-push....Passed`; the hook ran that executable |
| holds no `prepush-ci` | `Failed`, `exit code: 1`, ``Executable `prepush-ci` not found`` |

`sh -c 'command -v prepush-ci'` with that directory first on `PATH` prints the path of the executable in it: the first executable of the name wins, which is what the requirement says. The issue's reproduction (an old `prepush-ci` 0.1.2 on `PATH`, `install` and `doctor` of a newer one through `uvx`) shows `doctor` reporting every line `ok` while the hook runs 0.1.2.
