## Decisions

- **Only the empty flow list.** pre-commit accepts any YAML list, but only `[]` has no entries to move; a flow list with entries (`repos: [{repo: local}]`) would need the block rewritten as flow, so it stays refused. `repos:` with nothing is not valid for pre-commit (below) and stays refused.
- **Two spaces of indent** for the entries under `repos:`: the usual form of the files `install` already edits; the entries of the existing block-list case keep their own indent.
- **No dry run of `install` before `init` writes the config.** The refusal leaves `.prepush-ci.toml`, which is a valid config the user wants anyway, and the second run is already idempotent (`init` does not write over an existing config, `--check` may be left out; one that differs from the config exits 1, as "An existing config is kept" says). A dry run would split `install` into a plan and an apply step for the sake of a file that is not wrong. If the config turns out to be unwanted after a refusal, `init` says `written:` first, so the user sees it.

## Run against the head

pre-commit 4.7.0 (`uvx pre-commit validate-config <file>`):

| `repos` line | exit | message |
| --- | --- | --- |
| `repos: []` | 0 | |
| `repos: [] # none` | 0 | |
| `repos: [{repo: local, hooks: []}]` | 0 | |
| `repos:` | 1 | `At key: repos … Expected array but got 'NoneType'` |
| `repos:  # none` | 1 | the same |

`prepush-ci install --hooks pre-commit` at `07ad0e7` on `repos: []`:

```
prepush-ci install: .pre-commit-config.yaml: `repos` must be a block list: `repos:` and `- repo:` entries
exit 1
```

The file this change makes `install` write for `repos: []` (the block shortened here to its pre-push hook), checked with `pre-commit validate-config`, exit 0:

```yaml
default_install_hook_types: [pre-commit, commit-msg, pre-push]
default_stages: [pre-commit]
repos:
  # prepush-ci: begin
  - repo: local
    hooks:
      - id: prepush-ci-pre-push
        …
  # prepush-ci: end
```

The second run (`init --non-interactive --check true --hooks pre-commit` refused on `repos: [{repo: local}]`, the file changed to a block list, `init --non-interactive --hooks pre-commit` again) at `07ad0e7`: first run exit 1 after `written: .prepush-ci.toml`; second run prints `kept: .prepush-ci.toml`, `installed: pre-commit`, exits 0; the modification time of the config is unchanged.
