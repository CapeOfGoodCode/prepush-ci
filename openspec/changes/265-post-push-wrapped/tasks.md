# Tasks

## 1. Recognize wrapped pushes

- [x] 1.1 Split at `(`, `)` and backticks outside quotes in `core/post_push.py`; verify with unit specs named after the scenarios of "A push is recognized from the command"
- [x] 1.2 Skip the wrappers, the keywords and read `sh`/`bash`/`zsh` with `-c` recursively; verify with unit specs named after the scenarios of "A wrapper does not hide a push", "A shell keyword does not hide a push", "A shell started with -c is read" and "Forms that are not recognized"
- [ ] 1.3 Add one integration spec: the payload `(time git push --force-with-lease) 2>&1 | tail -25` after an amended trailer commit updates the comment (scenario "A wrapped push updates the comment")
- [ ] 1.4 Say in the README of `hook post-push` which forms are recognized and which are not, as the requirements state them; run the README's sentences against the head

## 2. Archive

- [ ] 2.1 Run `sh scripts/ci` and verify it passes
