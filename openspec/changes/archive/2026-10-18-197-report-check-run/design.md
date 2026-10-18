# Design

## Context

`report` is step 1 of #196: the pull request shows what a session checked. It decides nothing about whether a commit may skip CI (`verify` does) and runs no check (`run` does). See `proposal.md` for the why and the delta specs for the behavior. A result is self-reported: the session that ran the check says so, and the check run names what ran so a reviewer can verify it (#196, "Trust").

## Decisions

- **#197 is split in three.** The issue asks for the check run, the manifest flow, annotations in batches of 50, the `in_progress` state and ruff and mypy input; reviewing that in one sitting is not possible. This change is the `report` command: final result, summary, JUnit and coverage input, the refusal of a wrong tree, the status fallback. #200 carries annotations, ruff and mypy input and `in_progress`; #201 carries `app setup` and the README on app setup. The acceptance criteria on annotations and on the README move with them; each slice is useful alone (the status fallback needs no app).
- **The caller states the tree.** `--tree` is required: only the session knows which state it checked, and `report` can compare it with the tree of the commit it is asked to report on. The check is only as good as the caller, which the epic accepts until trust levels exist.
- **No "hash of the check script" in the summary; it names the `check` command instead.** The owner's mockup shows the sha256 of `scripts/ci`. The script's content is already pinned by the tree the summary names, finding the script inside a shell command is a guess, and a hash of the command text printed beside it verifies nothing. The config is read from the commit, as `verify` does, so the summary describes the commit it is posted on. Cost: a reviewer reads the command and the tree, not a digest.
- **Tool versions are given, not detected: `--tool NAME=VERSION`.** `report` cannot know which tools a check ran and must not run them; the caller that ran them knows. The OS is the platform's. The mockup's per-step timing table is left out: the tool has no per-step data, and a table filled by the caller would be prose. The preflight row names the command the config sets (or `none`), not a result: `report` runs nothing and cannot know how the preflight ended, and a caller that reports a run has by definition not been stopped by it. #196's mockup shows a result; this is the cost.
- **Usage errors exit 2, as every other argparse command does; `--help` exits 0.** `verify` alone exits 1 for bad arguments, because it is a CI gate (`cli.py`); `report` is not one. Malformed values (`--tool`, `--duration`, `--name`) are usage errors for the same reason and are refused before anything else is read.
- **The status description has no cut.** It is made of counts, a coverage figure, 7 characters of the tree and a fixed phrase, which stays under GitHub's 140 characters; `--name` goes into the `context`, not the description.
- **An empty variable counts as unset**, as `PREPUSH_CI` does: on Actions a missing secret arrives set but empty.
- **The repository comes from `origin`, ignoring any userinfo (a token in a clone URL), in the `https://`, `ssh://` and scp forms; `GITHUB_REPOSITORY` names it when `origin` cannot** (a session whose `origin` is a local proxy). `origin` wins when both exist: it is what the pull request's branch was pushed to. The userinfo never reaches the output.
- **JUnit is counted by test case, not by the counters in the file.** pytest writes `<testsuites><testsuite tests=… failures=… errors=… skipped=…>`; `node --test --test-reporter=junit` nests suites and writes comment lines; counting `testcase` elements by their `failure`, `error` and `skipped` children gives the same numbers for both and cannot count a nested suite twice. (Run with pytest and node 22.23: one passed, one failed, one skipped and one setup error give 4 cases, 1 failure, 1 error, 1 skipped.) A failed test is a `failure` or `error` child.
- **A `passed` result with failing tests in the given JUnit file is refused.** The check run's conclusion and its counts must not contradict each other. A `failed` result with no failing test is allowed: lint or types can fail alone.
- **The app is used or it is an error; there is no quiet fall back to a status.** With `PREPUSH_CI_APP_ID` set, a failing app (bad key, not installed) exits 1 with the reason, so the pull request never shows a status where a check run was expected. A status is posted only when no app is configured.
- **The app's token is requested with the program `openssl`.** The standard library cannot sign RS256, and a runtime dependency needs its own change (`openspec/config.yaml`). `openssl` is on Linux and macOS and ships with Git for Windows. A missing program is a refusal that says so. The key arrives as PEM text in `PREPUSH_CI_APP_KEY`, is handed to `openssl` without being written to the repository, and is not left on disk.
- **Statuses and check runs use the endpoints GitHub documents:** `POST /repos/{owner}/{repo}/check-runs` (app token), `POST /repos/{owner}/{repo}/statuses/{sha}`, `GET /repos/{owner}/{repo}/installation` (app JWT) and `POST /app/installations/{id}/access_tokens`; the status description stays under GitHub's 140 characters. The API is at `GITHUB_API_URL` (default `https://api.github.com`, the variable Actions and GitHub Enterprise Server set), which also lets the tests point `report` at a local server.

## Run the tools

`openssl` signs what the JWT needs (OpenSSL 3.0.22):

```
$ printf 'header.payload' > msg
$ openssl dgst -sha256 -sign k.pem msg | wc -c          # 2048-bit RSA key
256
$ openssl dgst -sha256 -sign k.pem msg > sig && openssl dgst -sha256 -verify p.pem -signature sig msg
Verified OK
$ openssl dgst -sha256 -sign e.pem msg                  # an Ed25519 key
Key type not supported for this operation               # exit 1
$ openssl dgst -sha256 -sign bad.pem msg                # a file that is no key
Could not read private key from bad.pem                 # exit 1
```

A key that is not RSA, or no key, exits 1, which `report` reports as an unusable key. The signature is 256 bytes, which the JWT carries base64url-encoded.

`coverage json` writes `totals.percent_covered_display` (`'100'` for a fully covered file) and `percent_covered` (`100.0`); `report` reads the first.

## Risks / Trade-offs

- [A caller can state a tree it did not check] → self-reported until trust levels exist (#196, "Trust"); the check run says "reported from a session" and names the tree.
- [`openssl` may be missing in a minimal image] → refused with the program's name; installing a package is the user's choice, and no dependency enters the wheel.
- [GitHub's behavior is read from its documentation, not exercised by the tests] → the tests run against a local server that answers as the documentation says; terminator exercises a real app in a throwaway repository.

## Purpose of the `report` spec

The builder copies this text, verbatim, into the `## Purpose` of `openspec/specs/report/spec.md` when the change is archived (the Purpose is not part of a delta):

> `prepush-ci report`: posts the result of a run of the check, made in a session or on a machine, for a commit, as a check run through the team's GitHub App or, without an app, as a commit status. It refuses a tree that is not the commit's tree, runs nothing itself, and names in the check run what ran.
