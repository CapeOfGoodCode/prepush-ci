# Tasks

## 1. The command

- [x] 1.1 Add `prepush-ci skill`: print the skill as bytes, from the source checkout when it has the file, else from the installed distribution's data file, else exit 1 with the message (the choice of source is pure logic in `core/`, the lookup does the I/O); verify with specs for the output equal to the file, the help listing, the lookup order and the missing file
- [x] 1.2 Add `--write`: write `.claude/skills/prepush-ci-setup/SKILL.md` at the root of the working tree, creating the directories, replacing an existing file, refusing outside a git repository; verify with specs for a new file, a replaced one, a subdirectory, a linked worktree, outside a repository and a non-ASCII path under an ASCII locale

## 2. The wheel

- [x] 2.1 Add `[tool.uv.build-backend.data] data = "skills"` to `pyproject.toml`; verify with an integration spec that runs `uv build`, installs the wheel into a new virtual environment and compares what the installed `prepush-ci skill` prints with `skills/prepush-ci-setup/SKILL.md`, and that the sdist carries the file

## 3. The plugin

- [x] 3.1 Add `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` as in `design.md`; verify with specs for the names, the source, the missing version, the skill's front matter and the single `SKILL.md`

## 4. The README reference

- [ ] 4.1 Add the entry for `skill` to the command reference of `README.md`, with its synopsis (`prepush-ci skill [--write]`) and one example, and make `test_the_reference_lists_the_eight_commands` name the nine commands; verify with the `readme` check on the repository and the scenario of a reference without an entry for `skill`
