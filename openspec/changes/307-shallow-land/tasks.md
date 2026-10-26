## 1. The answer of a shallow clone

- [x] 1.1 In `core/land.py` and `land_command.py`, tell a moved branch from history the clone lacks: when `git rev-parse --is-shallow-repository` prints `true` and both ancestry questions answer no, print the shallow line; verify with an integration spec per scenario of "A shallow clone says what it cannot tell", in real shallow clones of a bare `origin`
- [x] 1.2 Keep the answers a shallow clone can give and the moved line of a complete clone; verify with the scenarios "A shallow clone that can see the tip lands", "The branch moves while landing, in a shallow clone", "The shallow refusal comes before the preflight", "A complete clone is told that the branch moved" and the existing scenarios of "Only a head on top of the tip lands"

## 2. Archive

- [ ] 2.1 Run `sh scripts/ci` and verify it passes
