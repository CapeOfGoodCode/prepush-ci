## 1. The workflow

- [x] 1.1 Write `docs/ci/land.yml` and its specs: parse the YAML, and run the `run:` of the steps `decide`, `land` and `comment` under `sh` with a stub `gh` and a stub command; fix the claim "Landings run one at a time" in the header of the file and in the README sentence, which say how landings are ordered, to the one of "Every approval is handled"; make `decide` read the pull request and the review from the API and drop the draft test from the job's `if:`; verify with specs named after the scenarios of the requirements "The workflow runs when a review is submitted", "A step decides whether to land", "The pull request is read when the job runs", "Only an open pull request that is not a draft lands", "Only a review that still approves lands", "Only a reviewer who can write lands", "Only the approved head lands", "Only a pull request against the default branch lands", "Every approval is handled", "Land runs with the token of the app", "The line of land is kept", "A refusal is told on the pull request" and "The example says what it needs", "The example says what it costs"

## 2. The README

- [x] 2.1 Add the README step "Land instead of running CI on the default branch" with only the sentences that `design.md` pins; add the drift check; verify with specs named after the scenarios of "The README names the landing example"

## 3. Archive

- [ ] 3.1 Run `sh scripts/ci` and verify it passes
