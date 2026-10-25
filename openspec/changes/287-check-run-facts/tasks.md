# Tasks

## 1. The config

- [x] 1.1 Add `results` to the keys of the config, with its checks (type, relative path, no `..`); verify with unit specs named after the scenarios of "Config keys and defaults", "The result files are named in results", "A result path stays inside the worktree", "A result path reads the same on every operating system" and "A result path never names the git directory"

## 2. Record the facts

- [ ] 2.1 Add the pure logic in `core/`: the facts of a run from the contents of the named files (counts per test file, coverage, error counts), their one-line encoding and decoding, and the message of the result commit; verify with unit specs for "A recorded pass holds the facts of its run", "The files named in results become facts", "Test-file names are paths of the tree" and "Only numbers are kept"
- [ ] 2.2 Delete the named untracked files before the check, time the check, read the files after a pass and record the facts with the pass, in `run` and in the pre-push hook; verify with integration specs for "The files of this run only", "A path that is not safe to delete is left alone", "A path in another repository or under a tracked name is left alone", "A path that is left alone costs one line" and "A fact that cannot be read costs a warning"

## 3. Show them

- [ ] 3.1 Add the facts to the comment of the post-push hook: the visible line, the collapsed block, the note for a reused pass, and the choice of the latest pass; verify with integration specs for "The comment is the Markdown of report", "The facts are those of the latest pass for the tree", "The facts are one line and a collapsed block", "The details are collapsed" and "The facts say which run they come from"
- [ ] 3.2 Name `results` in the config reference of the README, and say in one sentence under `hook post-push` what the comment adds; run the drift checks against the head

## 4. Close

- [ ] 4.1 Run `sh scripts/ci` through the push hook; archive the change
