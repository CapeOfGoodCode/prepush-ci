## 1. The answer after a refused push

- [x] 1.1 In `core/land.py` and `land_command.py`, after a refused push list the tip again, fetch it, and answer `landed: <sha> already on <branch>` (exit 0) when the head is the tip or an ancestor of it; verify with an integration spec per scenario of "A head that landed meanwhile is landed", against a bare `origin` whose `pre-receive` hook makes the window wide
- [x] 1.2 Keep the answers of a tip that does not contain the head, of a refusal with an unchanged tip and of a branch or tip that cannot be read or fetched; verify with the scenarios "The branch moves while landing", "A remote that declines" and "The branch is gone"

## 2. Archive

- [x] 2.1 Run `sh scripts/ci` and verify it passes
