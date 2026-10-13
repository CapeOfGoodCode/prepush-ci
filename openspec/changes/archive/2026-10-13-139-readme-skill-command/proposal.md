Issue: #139

## Why

The README's agent setup step hands the agent a link to `SKILL.md` on `main`, which can name commands the installed version lacks and needs GitHub access. The tool now ships its skill as a command and as a Claude Code plugin (#138), so a reader who follows the README should be given those; otherwise they keep using the link that #138 exists to replace (#1, the skill that tells an agent to set the tool up).

## What Changes

- The prompt of usage step 1 tells the agent to run `uvx prepush-ci skill` and follow what it prints, instead of linking to `SKILL.md` on `main`. The absolute link is no longer required, and no longer the prompt.
- Because PyPI has no release with `skill` yet, the step also gives the form that runs from the repository, `uvx --from git+https://github.com/CapeOfGoodCode/prepush-ci prepush-ci skill`, "until the first release is on PyPI".
- The step names the Claude Code plugin as the other way: `/plugin marketplace add CapeOfGoodCode/prepush-ci`, then `/plugin install prepush-ci@prepush-ci`.
- The way to keep the skill with a project becomes `prepush-ci skill --write`, which writes `.claude/skills/prepush-ci-setup/SKILL.md`, instead of copying a folder of a checkout the reader may not have.
- The rest of the step (what the agent needs, delivers and asks; the manual core) is unchanged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `readme`: the agent step requirement is replaced (prompt, pre-release form, plugin), the walk requirement loses a pointer and the requirement that names the other way and the manual path (`skill --write`).

## Impact

`README.md` usage step 1 and `tests/integration/readme_spec.py`. No code of the tool changes: `skill`, `--write` and the plugin exist (#138).
