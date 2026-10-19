Issue: #198

## Why

A passing check is remembered today by the exact commit, in a directory of the git directory. A push that changes only the commits and not the tree (fixups folded, a message reworded) runs the whole check again, and what one session learned is hidden from every tool that does not know that directory. Keyed by the tree and the inputs, and stored as a git ref, a result is something other tools can find (#196, step 2).

## What Changes

- A passing check is recorded as the ref `refs/prepush-ci/results/<tree>-<config>`. `<config>` hashes everything that decides the result besides the tree: `check`, `preflight`, `require_env`, `require_up_to_date` and the standard output of the `preflight` command (the tool versions it reports).
- The commit is no longer part of the key: the same tree with the same inputs is the same result, so amending a message or folding a fixup keeps it. The hook's skip line names the tree and the commit that passed.
- A ref that is missing, unreadable or points at another tree is a miss. A ref that cannot be written is a warning.
- `cache = false` still turns reading and writing off. `prepush-ci run` still always runs the check.

Split off into their own slices (#196 lists them as one): publishing and looking up results on the remote (#205, so a new session in a fresh clone finds them), and cleaning up old refs (#206). The acceptance criteria on the remote and on cleanup move with them.

## Capabilities

### Modified Capabilities

- `run-cache`: what a pass is recorded as, what its key is, and what a miss is.
- `text-encoding`: the list of files the tool writes no longer holds the pass records (the requirement is replaced under a new name, `A written file reads back equal`).

## Impact

- `pass_cache.py` and `core/run_cache.py` change: records become refs, written with `git commit-tree` and `git update-ref`; the key loses the commit sha and gains the preflight output. The preflight runs before the key is complete, so its standard output is captured while it is still shown.
- Records of the earlier format under `prepush-ci/` in the git directory are never read again and are left where they are.
- No config key, no runtime dependency.
