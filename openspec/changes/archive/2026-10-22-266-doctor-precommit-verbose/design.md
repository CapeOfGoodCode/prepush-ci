## Context

`doctor` finds the block of a manager in the file `install` edits and requires `prepush-ci hook <name>` in it ("A manager's block is present"). It does not read what the hooks of the block set. `install` writes `verbose: true` on both hooks and, on a block of an earlier version, rewrites it ("pre-commit shows the messages of its hooks").

## Verified with the tools

`prepush-ci` built from `main`, in a scratch repository with `repos: []`:

```
$ prepush-ci init --non-interactive --check true --hooks pre-commit     # the block has verbose: true twice
$ <delete the verbose line of the pre-push hook>
$ prepush-ci doctor --hooks pre-commit | grep -A1 pre-push
fail pre-push: pre-commit is not activated: …/.git/hooks/pre-push does not exist
  fix: run `pre-commit install`                                         # the block is not looked at
$ prepush-ci install --hooks pre-commit
updated: pre-commit
$ grep -c verbose .pre-commit-config.yaml
2
```

After `pre-commit install` that doctor run passes: the missing key is not seen. `install` puts the key back.

## Decisions

- **The fix line names `prepush-ci install`, not `init`.** `install` is the command that rewrites the block (`init --non-interactive` calls it after asking for a check command it already has), and the other fix lines of this check name it. The issue's trial used `init`; both add the key.
- **Only the pre-push hook is required to have the key.** The issue is about the lines of the pre-push hook; the warning of `commit-msg` is rare and a `commit-msg` hook without the key is not a failure.
- **The hook is found by its id, its lines run to the next `- id:` or the end of the block.** A line `verbose: true` in them counts; a comment, `verbose: false` or the key in the other hook does not. This reads the text the way `install` writes it, with no YAML parser.
- **Before the activation check.** The key belongs to the block, like "A manager's block is present", so it is reported first; fixing it then shows the activation problem, if any. Nothing PATH-related runs for a failing check ("Only a check that would otherwise pass looks at PATH").
