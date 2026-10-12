# Design

## Context

`verify` (#6) decides about a commit. A gate must also decide whether the pipeline is one that may skip at all, and then wire "skip" into a CI system. A wrong "skip" lets unchecked code through the pull request; a wrong "run" costs one run. Every doubt answers "run".

## Goals / Non-Goals

**Goals:** one decision rule, written once and executed in tests; copyable examples for GitHub Actions and GitLab CI; an optional GitHub Action that reuses the rule.

**Non-Goals:** the default branch's own pipeline (it always runs in full and should gate deployment; the examples leave it alone), other CI systems (the shell gate is the template), `init` output (#12), prose in README and `SKILL.md` (#15).

## Decisions

- **The rule lives in `docs/ci/gate.sh`, and the action calls it.** The shell gate is both the generic example and the engine of `action.yml` (`$GITHUB_ACTION_PATH/docs/ci/gate.sh`), so the rule exists once and tests run it for real. The GitLab example cannot reach a script that is not in the user's repository, so it spells the same rule out inline.
- **Interface of `gate.sh`: environment in, one line out.** Inputs: `GATE_PULL_REQUEST` (`true` on a pull or merge request), `GATE_HEAD_SHA`, `GATE_HEAD_REPO`, `GATE_BASE_REPO`, `GATE_HEAD_BRANCH`, `GATE_DEFAULT_BRANCH`, and `PREPUSH_CI_CMD` (default `uvx prepush-ci`, run as `$PREPUSH_CI_CMD verify <sha>` with word splitting). Standard output is exactly `verified=true` or `verified=false`, ready to append to `$GITHUB_OUTPUT`; the reason goes to standard error. It exits 0 whatever it decides, so a gate step that fails means a broken CI, never a skip, provided the jobs that need the gate run when it failed (next decision). Plain environment variables carry no CI vendor's vocabulary into the rule.
- **Skip only when every input is present and agrees.** An empty variable means "do not skip": a deleted fork has no head repository, an unset sha makes `verify` fail. A source branch equal to the default branch does not skip either (a pull request from `main` to a release branch), which is the literal "never on the default branch".
- **The other jobs run unless the gate says `true`, also when the gate failed.** GitHub skips a job whose `needs` job failed unless its `if:` holds a status function, and a skipped job reports success, even as a required check. The example writes `if: ${{ !cancelled() && needs.gate.outputs.verified != 'true' }}`, so a broken gate means a full run.
- **The action step takes everything through `env:`.** `github.head_ref` is a name the pull request's author chooses, and `inputs.command` is user text; expanding either as `${{ }}` inside `run:` is script injection. `run:` holds none.
- **Only the `pull_request` event counts on GitHub.** `pull_request_target` runs the base branch's workflow with secrets for fork code, and `push`, `merge_group` and scheduled runs are not pull requests. All of them output `false`.
- **The head commit, not the merge commit, is verified.** GitHub checks out a merge commit by default, committed by `noreply@github.com`, which never verifies (#6). The examples check out `github.event.pull_request.head.sha`, or `verify` would always say no. GitLab's detached merge request pipeline already runs on the source head; a merged-results pipeline exposes it as `CI_MERGE_REQUEST_SOURCE_BRANCH_SHA`.
- **The action installs nothing of its own.** Input `command` defaults to `pipx run prepush-ci` (pipx is on GitHub-hosted runners; `uvx` is not); the user may pass `uvx prepush-ci` after setting up uv. The action does not check out the repository: the workflow does, at the head sha.
- **The GitLab example skips with a generated child pipeline.** Variables from a `dotenv` report cannot be used in `rules:`, and a job that starts and exits early still bills. The `gate` job writes `child.yml`, which either includes the real pipeline or holds one `echo` job; a trigger job includes it. Pipelines on the default branch trigger the real pipeline directly. Cost of the choice: one tiny job on a skipped merge request.
- **How the specs are checked, and the limit.** `gate.sh` is run in tests against real temporary repositories, with `PREPUSH_CI_CMD` pointing at a one-line shim that starts `sys.executable -m prepush_ci`. `action.yml` and the two YAML examples are checked as text, since no test can run a hosted CI: the test reads each file and asserts the lines the requirements name (event, repository comparison, default branch, head sha, the call to `verify` or to `gate.sh`, the mention of the full run). That the YAML works in a real CI is for terminator to try, not for the suite.
- **The mitigation is a documented line, not a default.** Each example carries a comment naming the option of one full run per pull request (for example on `ready_for_review`) and how to switch it on. It stays off: turning it on is the user's trade between cost and trust in local hooks.

## Risks / Trade-offs

- [The YAML examples can rot without a test noticing] → accepted; the textual checks pin the rule's lines, the rule itself is executed through `gate.sh`.
- [GitLab's UI rebase keeps the trailer under the clicking user (#6)] → the GitLab example warns not to use that button on a merge request that relies on skipping.
- [`pipx` is missing on a self-hosted runner] → the action fails loudly, which is a failed gate, not a skip; `command` replaces it.
