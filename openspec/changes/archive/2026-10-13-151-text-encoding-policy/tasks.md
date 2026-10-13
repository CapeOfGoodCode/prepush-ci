# Tasks

## 1. The module

- [x] 1.1 Rebase on `main` after PR #142 (#134) and PR #147 (#144) have landed, or on whichever has; add `src/prepush_ci/text_io.py` with the pure part (`decode`, `encode`, `from_os`, `to_os`); verify with unit specs for the scenarios "Bytes survive the round trip" and "Tool text survives the operating system's strings"
- [x] 1.2 Add `read_text`, `read_utf8` (raises a `NotUtf8` naming the path), `write_text`, the subprocess `run`, `run_shell` for the user's commands, `stdin_text` and `configure_streams`; verify with unit specs for each (a Latin-1 byte, a non-ASCII path, an ASCII stream)
- [x] 1.3 Move `git.py`, `commit_msg_hook.py`, `repo_config.py`, `install_command.py`, `init_command.py`, `doctor_command.py`, `strip_command.py`, `pass_cache.py`, `pre_push_hook.py`, `preflight.py`, `checking.py` and `cli.py` onto the module, with no change to what they print or exit with; add the scan spec; verify with the scan scenarios and the integration specs unchanged

## 2. The variant

- [x] 2.1 Add the `utf8` and `ascii` variants to the `repo` fixture and the CLI helper of `tests/integration/conftest.py`, with the helper for printed text; verify with specs for "Both variants run" and "The ascii variant is hostile"
- [x] 2.2 Fix, with one spec each, what the variant finds in the command that breaks; each fix folds into the commit that adds its spec; verify with the scenarios of "The tool's text is UTF-8", "A file the tool parses must be UTF-8", "A file the tool edits keeps its bytes", "A file the tool writes reads back equal" and "Every command handles non-ASCII names the same way" (the check and preflight scenarios included) (the reproductions of #130, #134, #144, #145, #146, #150)
- [x] 2.3 Add the scenarios of "The terminal never makes a command fail" (#115); verify them in the `ascii` variant and report the time the integration tier takes in the two variants in the pull request

## 3. Finish

- [x] 3.1 Run `sh scripts/ci` and verify it passes on both platforms
