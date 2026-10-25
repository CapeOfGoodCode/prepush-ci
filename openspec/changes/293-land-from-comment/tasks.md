## 1. The pure logic

- [ ] 1.1 Add to `core/land.py` the reading of a comment: marker, title, `Tree`, `Check` and `Preflight` rows, the permission answer, and the lines of the refusals; verify with unit specs named after the scenarios of "A comment of the pull request is a pass when no result is found", "A comment states a pass", "A comment names this tree, check and preflight", "Only a comment of someone with write access counts", "A comment of an App does not count" and "A comment that cannot be read is not a pass"
- [x] 1.2 Make the title line of `report --markdown` for a failed result with counts say `Failed (<counts>)`; verify with the scenarios of "The Markdown is the check run's summary under a marker"

- [x] 1.3 Record `config <digest>` in the result commit and make the post-push hook count only the refs of the committed config; verify with the scenarios of "A recorded pass names the config it ran with" and "Only a pass of the committed config is shown"

## 2. The command

- [ ] 2.1 Add the two reads to `github_api.py` (the permission of a user; the comments with their author) and the lookup in `land_command.py` after the result refs; verify with integration specs against a local stub of the API named after the scenarios of the `land` requirements above

## 3. The README

- [ ] 3.1 Say in the README what `land` reads when there is no result ref, and what it needs for it; every sentence backed by a requirement or run (`AGENTS.md`, Docs say only what is pinned or run)

## 4. Archive

- [ ] 4.1 Run `sh scripts/ci` and verify it passes
