# Design

## Context

Step 2 of #196: a result outlives the session that made it. Today `run-cache` keeps a file per (commit, tree, config) under `prepush-ci/` in the git directory. This change makes the record a git ref keyed by the tree and the inputs, so that the same state is checked once however its commits are written. Sharing refs through the remote (#205) and cleaning them up (#206) are separate slices; `land` (#199) reads the refs this change writes.

## Decisions

- **#198 is split in three.** The issue asks for the ref, the remote lookup and the cleanup; the remote needs decisions of its own (which remote when `run` has no push, a network round trip per hook, a remote that refuses the ref) and cleanup needs a rule and a place to run. This change is the local ref and its key; #205 carries the remote and the acceptance criterion on a fresh clone, #206 the cleanup. The criteria "a new session in a fresh clone finds the result" and "result refs are cleaned up" move with them. Cost: #198 closes with the first, third and fourth criteria met and the second and fifth open in #205 and #206.
- **The check script and the lock files are not hashed: the tree already holds them.** The issue puts them into `<config>`. The worktree is clean when the result is recorded and the check runs on the committed files, so the same tree is the same script and the same lock files; hashing them again could only repeat the tree. What is left outside the tree is the config (`check`, `preflight`, `require_env`, `require_up_to_date`, as before) and the tool versions.
- **Tool versions are the standard output of the `preflight` command; no new config key.** The mockup says "the tool versions the preflight reports". A `preflight` such as `uv --version; git --version` already says them, so the key follows it with nothing to configure. Cost: a preflight that prints something that changes at every run (a time) never reuses a result; a preflight that prints nothing leaves tool versions out of the key, and the result then holds for any version. The preflight's standard output is piped into the hash, not only inherited: a tool that colours its output only on a terminal prints without colour. It is still shown. The order between the two streams is not kept: the standard output is shown while the command runs but is read in steps of 0.1 s, so when both streams go to one place (`2>&1`) a line of stderr can come before an earlier line of stdout. Keeping the order would need one stream for both, which would put stderr into the key; the spec therefore does not promise the order.
- **The guarantee becomes "the check passed on exactly that tree with those inputs".** Until now a trailer commit on the remote implied the check passed on exactly that commit; with the commit out of the key it implies the check passed on a commit of that tree. A reused result says nothing about what the check reads from the commit and not from the tree: a message lint (commitlint, a DCO check) or a version taken from `git describe` (setuptools-scm, hatch-vcs). A project whose check reads those sets `cache = false`, and the README says so. The Purpose of `pre-push-hook`, the two README lines on a remembered pass and the wording in `LOOP.md` (reserved for the human; a `Task` issue proposes it) follow. The result commits are parentless and show in `git log --all`; the README says that too.
- **The skip line names the tree and the commit by their first twelve characters each.** The full hashes are in the ref and its message; twelve characters read in one line and identify a commit as well as `git log --abbrev` does.
- **The commit sha leaves the key.** It was there so a result belonged to a commit. The tree is what the check ran on; the commit adds only the message and the history, which a folded fixup or a reworded message changes. The hook's line names the commit that passed, so a reader sees the reuse across commits.
- **The ref points at a commit, not at the tree.** A ref to a tree would work, but it carries no date, and cleanup (#206) needs the age of a result. The commit is made with `git commit-tree` and a fixed author and committer (`prepush-ci <prepush-ci@localhost>`), so it needs no `user.name` and no signing, and has no parent; its message names the commit that was checked. A result is a miss unless the tree of the commit its ref points at is the key's tree.
- **`run` records but does not skip.** `run` is how to run a flaky check again; unchanged. Only the hook reads results. A pass in `run` refreshes the ref.
- **Records of the earlier format are left alone.** They live under `prepush-ci/` in the git directory, are never read and hold nothing a user needs; deleting a user's files is not worth a rule. The first push after the update runs the check once.
- **The tree is read before the preflight, the preflight's output after it.** The key is complete only when the preflight ended; the tree is read first so a commit the preflight makes cannot change what the pass is recorded for.

## The new Purpose of `pre-push-hook`

Copied word for word into `openspec/specs/pre-push-hook/spec.md` (a Purpose is not a delta):

> The `pre-push` hook that enforces the trailer: a pushed branch tip that carries it reaches the remote only if it is the checked-out `HEAD`, the worktree is clean and the full check passed on its tree with the current inputs, so a trailer commit on the remote implies the check passed on exactly that tree. The check may have run on another commit of that tree; what it reads from the commit and not from the tree (the message, the author, the history) is not covered, and `cache = false` turns the reuse off.

## The new Purpose of `run-cache`

Copied word for word into `openspec/specs/run-cache/spec.md` (a Purpose is not a delta):

> `prepush-ci run`, which starts the pre-push hook's sequence by hand on HEAD, and the result refs under `refs/prepush-ci/results/` that let the hook skip a check that already passed on exactly that tree with the same inputs, whatever commit it was made for. The cache can only cost time: anything damaged, stale or unwritable means the check runs.

## Run the tools

git 2.39.5. A commit of a tree with no identity configured (`HOME` unset, no global or system config), then a ref to it:

```
$ env HOME=/nonexistent GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null \
    GIT_AUTHOR_NAME=prepush-ci GIT_AUTHOR_EMAIL=prepush-ci@localhost \
    GIT_COMMITTER_NAME=prepush-ci GIT_COMMITTER_EMAIL=prepush-ci@localhost \
    git commit-tree $T -m "prepush-ci: the check passed" -m "commit deadbeef"
$ git update-ref refs/prepush-ci/results/$T-cfg $C
$ git log -1 --format='%s|%b' refs/prepush-ci/results/$T-cfg
prepush-ci: the check passed|commit deadbeef
$ git gc -q --prune=now; git cat-file -t $C
commit                                   # the ref keeps the commit and its tree alive
```

Without the identity variables, `commit-tree` exits 128 (`Author identity unknown`). Reading the tree of a ref, and the three misses:

```
$ git rev-parse --verify --quiet refs/prepush-ci/results/$T-abc^{tree}     # a good ref
3be22be77da4887e869c981806d8452f034dd014                                   # = $T, exit 0
$ : > .git/refs/prepush-ci/results/empty                                   # emptied file
$ git rev-parse --verify --quiet refs/prepush-ci/results/empty^{tree}
warning: ignoring broken ref refs/prepush-ci/results/empty                 # exit 1
$ touch .git/refs/prepush-ci; git update-ref refs/prepush-ci/results/x $C  # a file in the way
fatal: update_ref failed for ref 'refs/prepush-ci/results/x': cannot lock ref ... non-directory in the way
                                                                           # exit 128
$ git pack-refs --all; git rev-parse --verify --quiet refs/prepush-ci/results/y^{tree}
3be22be7...                                                                # packed refs read alike
```

A linked worktree sees the refs of the main one (`git for-each-ref refs/prepush-ci` in `../wt` lists them). Folding a fixup keeps the tip's tree:

```
$ git rev-parse HEAD^{tree} HEAD          # tip: fixup! feat: a
a4c77bfa88effc40fa7fe8cf0d8d152f4b900371
d4a2a5f8f06493e6763bd12dd33f0727cf283d1e
$ GIT_SEQUENCE_EDITOR=: git rebase -q -i --autosquash --root
$ git rev-parse HEAD^{tree} HEAD
a4c77bfa88effc40fa7fe8cf0d8d152f4b900371  # same tree
4c5c28b5f7b8e0bdd38e22e24af064c121abf123  # new commit
```
