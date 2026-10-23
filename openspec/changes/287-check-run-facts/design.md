## Context

The result ref of the run cache (`refs/prepush-ci/results/<tree>-<config>`) points at a parentless commit whose message is `prepush-ci: the check passed` and `commit <sha>`. It is shared with `origin` by a push to `origin`, and the post-push hook already looks it up by tree. The facts ride in that commit: it is the one record that is tied to the tree, survives amend and squash (same tree), and is fetched with a pass from `origin`.

## Verified with the tools

pytest 9.1.1, `--junitxml` with `-o junit_family=xunit1` writes `file` and `line` on each `testcase`; the default family writes only `classname` and `name`:

```
$ pytest -q a_spec.py --junitxml=r.xml -o junit_family=xunit1; grep -o '<testcase [^>]*>' r.xml
<testcase classname="a_spec" name="test_a" file="a_spec.py" line="0" time="0.000" />
<testcase classname="a_spec" name="test_b" file="a_spec.py" line="1" time="0.001">
$ pytest -q a_spec.py --junitxml=r2.xml; grep -o '<testcase [^>]*>' r2.xml
<testcase classname="a_spec" name="test_a" time="0.000" />
<testcase classname="a_spec" name="test_b" time="0.000">
```

git 2.39.5, `git commit-tree <tree> -m <a> -m <b> -m <c>` makes three paragraphs, and `git log -1 --format='%T%n%b'` (what the cache reads) returns the tree, then the last two:

```
$ git log -1 --format='%T%n%b' $c
4b825dc642cb6eb9a060e54bf8d69288fbee4904
commit abc

facts {"v":1,"seconds":492}
```

## Decisions

- **The facts live in the third paragraph of the result commit, as one line of JSON after `facts `.** The reader takes the first line of the second paragraph as the commit, as before, so refs without facts and facts it cannot read both leave the pass valid. Rationale: no new ref, and a pass that comes from `origin` brings its facts.
- **The config key is `results = { junit = [...], coverage = "...", ruff = "...", mypy = "..." }`, every sub-key optional.** Rationale: the names of `report`'s flags; the same paths the setup skill writes (#286). A path must be relative, written with `/` only, without `..`, with no leading `/` and no drive (`X:`), and a backslash is refused on every OS. Rationale: the same config must read the same everywhere, and the tool deletes the path.
- **The tool deletes each named file before the check starts, instead of comparing modification times, and only when the cache is on.** Rationale: file systems differ in the resolution of mtimes, a deletion is exact; with `cache = false` no pass is recorded, so there are no facts and nothing to clean for.
- **Only a regular, untracked file (not in `HEAD`, not in the index) with no symbolic link or junction on its way, whose real path is under the real path of the worktree, is deleted; anything else, and a deletion that fails, is left alone, not read, and costs one warning line naming the key.** Rationale: the tool must never delete outside the worktree or what the user versioned, and a stale file must never be read as a fact. A link is skipped, not unlinked, so the user's link stays.
- **The rule judges the file, not its spelling.** The config refuses a `.git` component (any case, trailing dots and spaces dropped, and `git~1`). The delete step also leaves alone a path with a `.git` or a gitlink on its way (a submodule or a nested repository: the superproject's `HEAD` and index do not list its files), and compares the path with `HEAD` and the index per component without case and without trailing dots and spaces, on every operating system. Rationale: a committed config must not delete the git directory, another repository's files or a tracked file on a case-folding or Windows file system; one rule on every OS keeps tests on Linux meaningful, and the cost is that a file differing from a tracked one only by case is left alone with a warning.
- **The duration is that of the check command alone (whole seconds, rounded), recorded even when `results` is absent.** Rationale: it needs no file, and the preflight is not the check.
- **A file that is missing, damaged or not of the format yields no fact for it, a one-line warning naming the key, and never fails the run.** Rationale: the check passed; the facts are a courtesy and must not turn a pass into a refusal. A failing case in a passing run is recorded as it is: the tool saw the files, not the session.
- **Per test file, a case is counted under its `file` attribute only when that path names a file of the checked tree; all other cases go under `other`.** Rationale: the comment is public, and a name that comes from a result file is output of the check. pytest writes `file` only with `junit_family=xunit1`; without it the details hold the totals only.
- **At most 50 test files are listed, the largest numbers of cases first, the rest summed as `other`.** Rationale: a bound on the size of the commit message and of the comment.
- **Coverage is kept only when the text of `percent_covered_display` is ASCII digits with at most one `.`, a digit on each side of it, and from 0 to 100, and it is kept and shown as the file wrote it (`100` stays `100`).** Rationale: `float()` takes `nan`, `1e3` and `-5`, and the comment must agree with `report`.
- **The error counts of the tools are the number of entries of the ruff array and the `Found <n> error` line of mypy (`Success` is 0).** Rationale: the same readers `report` has, and only numbers go public.
- **When one tree holds several passes (the check or another input of the key changed), the facts are those of the pass whose result commit has the latest committer date; ties go to the last ref name; no fall-back to an older pass with facts.** Rationale: the recorded date is the time of the pass (`A recorded pass is dated when it is recorded`), so the latest pass is the last check that ran on this tree.
- **"Reused" is decided by comparing the commit the facts name with `HEAD`.** A different commit with the same tree (amend, squash, a pass fetched from `origin`) says `Reused from the run on <sha> (same tree)`; the same commit says `Checked on this commit`. Rationale: the ref names the commit already; no second clock.
- **`prepush-ci run` records facts as well as the hook.** Rationale: both record the pass and a later push skips the check; if only the hook did, `run` then a push would show nothing.

## Risks

- A repository with `cache = false` records no pass and so shows no facts, as it shows no comment today.
- The facts are published with the ref to `origin`; they hold numbers and paths of files of the commit, which `origin` receives anyway.

## Docs

The README names `results` in its config reference (the `readme` spec checks that every key is listed). The one sentence it gets under `hook post-push` (the comment also holds the facts of the run, details collapsed) is pinned by "The facts are one line and a collapsed block" and "The details are collapsed"; the sentence on deleting the named files before the check is pinned by "The files of this run only".

The agent's own call of `report --markdown` (#286) writes the same comment with its own files and replaces the whole body, facts included; the next push of the hook writes them again. This is the existing "replaced" behavior and needs no rule.
