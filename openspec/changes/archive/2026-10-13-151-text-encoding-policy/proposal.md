Issue: #151

## Why

The release waits until no bug is open, and bugs of one class keep arriving one at a time: a non-ASCII repository path, remote name or config byte, or a message that is not UTF-8, under an ASCII locale. Seven so far (#115, #130, #134, #144, #145, #146, #150). Each fix covered the one command a sweep happened to try, because every module decides for itself how to decode what it reads (`git.py` the file system encoding with `surrogateescape`, `commit_msg_hook.py` the locale, `repo_config.py` strict UTF-8, `doctor_command.py` `replace`). The user meets them as tracebacks, or as a check that silently does not match; the bug count does not converge.

## What Changes

- New capability `text-encoding`: one policy for text that crosses a boundary (paths and git output, arguments, the environment and standard input, files the tool reads and writes, standard output and error), held in one module that every command uses, and a test that fails when another module decides an encoding itself.
- The integration specs run twice: as they do today, and in a variant with `LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0` in a repository whose path has a non-ASCII character. A command that breaks under it fails the suite before a sweep finds it.
- The reproductions of the seven issues become scenarios, so none can come back. Where a scenario needs a user-visible message (a config or a file that is not UTF-8), the message is specified here.

## Capabilities

### New Capabilities

- `text-encoding`: how the tool turns bytes into text and back at every boundary, and the variant of the integration suite that holds it.

### Modified Capabilities

None. No existing requirement says anything about encoding; the new ones add to what `config`, `commit-msg-hook`, `doctor`, `init` and `install` already specify and change none of it.

## Impact

- Edited: every module of `src/prepush_ci/` that reads or writes text or starts a subprocess; new `src/prepush_ci/text_io.py` and a unit spec for its pure part. `tests/integration/conftest.py` gets the variant.
- Closes with the implementation: #145, #146 and #150 (blocked by this issue; their reproductions are scenarios below). #134 (PR #142) and #144 (PR #147) land first on their own track; this change then moves their read and write calls into the module.
- Out of scope: the output of the user's own `check` and `preflight` commands (the tool passes it through untouched); the encoding of commit messages git writes (`i18n.commitEncoding`); Windows code pages beyond the non-ASCII path in the variant.
