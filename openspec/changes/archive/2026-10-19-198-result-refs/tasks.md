# Tasks

## 1. The key

- [x] 1.1 Make the key the tree and `<config>`, a hash of `check`, `preflight`, `require_env`, `require_up_to_date` and the preflight's standard output; run the preflight with its standard output both shown and captured, and complete the key after it; verify with unit specs for the key and its hash (each input changes it, other keys do not) and integration specs for an amended message, a changed tool version, a changed output of the preflight and a preflight whose output is shown

## 2. The ref

- [x] 2.1 Record a pass as `refs/prepush-ci/results/<tree>-<config>` pointing at a commit of the tree whose message names the commit that was checked, and treat a missing, unreadable or foreign-tree ref as a miss; verify with specs for each miss, for `cache = false`, for a failing check, a refusal and a commit made during the check, and for a ref that cannot be written (in `run` and in the hook)
- [x] 2.2 Print the hook's skip line with the first twelve characters of the tree and of the commit that passed; verify with specs for a retried push and an amended commit

## 3. What the change says to readers

- [x] 3.1 Copy the Purposes of `pre-push-hook` and `run-cache` from this `design.md` into `openspec/specs/pre-push-hook/spec.md` and `openspec/specs/run-cache/spec.md`, word for word, when the change is archived; verify with `openspec validate --all --strict`
- [x] 3.2 Change the README's step 5 ("passes on exactly that commit; a pass is remembered, so a retried push does not run the check twice") and the `cache` row of the config reference to say that a pass is kept for the tree and the inputs, so an amended or squashed commit of the same tree skips the check; that what the check reads from the commit (a message lint, a version from `git describe`) is not covered and calls for `cache = false`; and that the results are parentless commits under `refs/prepush-ci/results/` that show in `git log --all`; every such sentence is run against the head, as `AGENTS.md` asks, and the output goes into the PR
