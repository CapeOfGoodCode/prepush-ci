# prepush-ci

[![CI](https://github.com/CapeOfGoodCode/prepush-ci/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/CapeOfGoodCode/prepush-ci/actions/workflows/ci.yml)
[![Coverage](https://raw.githubusercontent.com/CapeOfGoodCode/prepush-ci/python-coverage-comment-action-data/badge.svg)](https://github.com/CapeOfGoodCode/prepush-ci/tree/python-coverage-comment-action-data)
[![PyPI](https://img.shields.io/pypi/v/prepush-ci)](https://pypi.org/project/prepush-ci/)
[![Python](https://img.shields.io/pypi/pyversions/prepush-ci)](https://pypi.org/project/prepush-ci/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Built by loops](https://img.shields.io/badge/built%20by-4%20AI%20loops-8a2be2)](LOOP.md)

Run the full CI check in the `pre-push` hook of an AI agent's cloud session (or any machine that opts in), and let pull request CI skip commits that provably went through it. The default branch always runs CI in full.

> **Status: under construction.** The tool is being built by a small fleet of AI coding loops from the intent in [issue #1](https://github.com/CapeOfGoodCode/prepush-ci/issues/1). Nothing here is released yet.

## How it works (in one paragraph)

When `PREPUSH_CI=full` is set, a `commit-msg` hook writes the trailer `Prepush-CI: full` into each commit. The `pre-push` hook refuses to push a tip commit that carries the trailer unless the full check passes on it. A small gate in pull request CI reads the trailer of the head commit and skips the remaining jobs. The default branch ignores the trailer and runs CI in full. See [issue #1](https://github.com/CapeOfGoodCode/prepush-ci/issues/1) for the full design.

## How this repository is built

This repository is also an example of agentic engineering:

- [`AGENTS.md`](AGENTS.md) is the rulebook for every contributor, human or agent (`CLAUDE.md` imports it).
- [`LOOP.md`](LOOP.md) describes the loops that build the tool: their roles, the label state machine they share, what each may touch, and where a human decides.
- [`openspec/`](openspec/) holds the specifications. Every feature starts as an OpenSpec change.
- [`scripts/ci`](scripts/ci) is the one entry point for the full check; CI and the pre-push hook run the same script.

## Development

```sh
uv sync && npm ci          # Python tooling, OpenSpec CLI
uv run pre-commit install  # commit-msg, pre-commit and pre-push hooks
sh scripts/ci              # the full check, exactly as CI runs it
```

## License

[MIT](LICENSE)
