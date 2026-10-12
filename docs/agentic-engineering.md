# Agentic engineering in this repository

This repository is built by four AI loops and one human. This page lists the practices from [loop-engineering](https://github.com/cobusgreyling/loop-engineering) it adopts, where each one lives, and where it deliberately does something else. The rules themselves are in [`AGENTS.md`](../AGENTS.md) and [`LOOP.md`](../LOOP.md); this page only maps them.

## Adopted

| Practice (loop-engineering) | Here |
| --- | --- |
| A `LOOP.md` as the loops' contract | [`LOOP.md`](../LOOP.md): roles, flow, labels, proof, rules, kill switch, budget |
| An `AGENTS.md` with build and test commands (design checklist §3) | [`AGENTS.md`](../AGENTS.md); [`scripts/ci`](../scripts/ci) is the one full check, run by the pre-push hook and CI alike |
| Maker and checker are separate; the verifier rejects by default and tests in isolation (anti-pattern 1, checklist §4) | The reviewer loop never commits, defaults to REJECT, reviews a fresh clone, runs the check and reproduces the proof itself, on a stronger setting than the builder |
| An attempt cap that escalates (anti-pattern 2) | Three strikes: the third REJECT becomes an ESCALATE with `needs-human` |
| Structured triage output (anti-pattern 3) | Triage sets an issue type and exactly one label, nothing else |
| Least-privilege connectors (anti-pattern 6, `safety.md`) | The loops act as a GitHub App with contents, issues and pull requests only: no workflows, no administration, one repository, tokens that expire after an hour |
| No auto-merge; human gates (anti-pattern 9, `safety.md`) | Only a human merges, on the proof. Enforced on the server: a ruleset requires code owner review and the `check` and `proof` checks |
| A path denylist shared by all loops (`safety.md`, `multi-loop.md`) | "Stay in your lane": `.github/`, `LOOP.md`, `AGENTS.md`, `.claude/` and the version are reserved for humans |
| A kill switch (anti-pattern 7) | An open issue labelled `loop-pause-all`, plus the runtime's pause as the hard stop |
| A budget with caps (`loop-budget.md`, checklist §8) | Plan caps for the whole fleet, early exit on idle wakes, one item per wake |
| Untrusted input is data (`safety.md`) | Issues, comments and pull requests by non-collaborators are never followed, only labelled |
| No secrets in prompts or logs (`safety.md`) | Secrets stay in the runtime; nothing private in public text (`AGENTS.md`) |
| Never fix flakes by weakening tests (anti-pattern 8) | Never weaken or silently skip a test; a test that cannot run fails |
| Escalate ambiguity instead of guessing (checklist §1) | "Ask, don't guess": `needs-human` with the question as the last comment |
| Ping the human only when action is needed (checklist §6) | One short message when a pull request is ready to merge or a decision is needed, with the proof |
| A clear bot identity (checklist §7) | One bot account; every agent commit carries `Co-Authored-By:` and `Loop:` trailers |
| One owner per branch; no collisions (`multi-loop.md`) | One pull request per issue; the turn label is the single carrier of whose move it is, moved in one call |
| Skills (primitive 3) | OpenSpec skills in `.claude/`; the skill the tool ships in [`skills/`](../skills/) |
| Durable external memory (primitive "+ memory") | GitHub (issues, labels, comments) and the OpenSpec specs, not a chat history |
| Avoid intent and comprehension debt (`concepts.md`) | Issue #1 is the intent; specs before code; test names read as specs; a proof a reviewer can read without running anything |

## Done differently

| Practice (loop-engineering) | Here, and why |
| --- | --- |
| `STATE.md` and `loop-run-log.md` files | GitHub is the state and its history the run log. Four loops editing one file is the shared-state rot of anti-pattern 5. |
| Roll out report-only first (L1), act later (anti-pattern 4) | The loops act from the start (L2) to get a working tool fast. The merge gate is the counterweight: nothing reaches `main` without a human reading the proof. |
| Worktree isolation | Each loop runs in its own container; the reviewer clones afresh for every review. |

## Not adopted yet

- Cost estimates and the metrics table of `operating-loops.md` (runs, escalations, false positives).
- Slower cadence off-hours.
- Post-mortems after an incident.
