#!/bin/sh
# A generic CI gate: may this pull request skip its own checks?
#
# It may only when the head commit provably went through the full check in the pre-push hook:
# the run is a pull or merge request from the same repository, its source branch is not the
# default branch, and `prepush-ci verify <head sha>` exits 0. Every doubt means "do not skip".
#
# Map your CI's values to these variables (an unset or empty one means "do not skip"):
#   GATE_PULL_REQUEST    "true" on a pull or merge request, anything else otherwise
#   GATE_HEAD_SHA        the request's head commit (the source branch tip, not a merge commit)
#   GATE_HEAD_REPO       the repository the head commit lives in, e.g. owner/repo
#   GATE_BASE_REPO       the repository the request targets, e.g. owner/repo
#   GATE_HEAD_BRANCH     the request's source branch
#   GATE_DEFAULT_BRANCH  the repository's default branch
#   PREPUSH_CI_CMD       how to start the tool (default: uvx prepush-ci), split into words
#
# Run it in a checkout of the head commit. It prints exactly one line on standard output,
# `verified=true` or `verified=false` (append it to a CI output file as is), explains itself
# on standard error and always exits 0, so a failing gate step means a broken CI, never a skip.
# Let the jobs that follow run unless the line says `verified=true`, also when this step failed.
#
# Optional, off by default: one full run per pull request anyway (for example when it is marked
# ready for review) covers developers whose local hooks are missing. Turn it on by making the
# jobs that follow run on that event whatever this gate says.

PREPUSH_CI_CMD=${PREPUSH_CI_CMD:-uvx prepush-ci}

no() {
    echo "gate: $1" >&2
    echo "verified=false"
    exit 0
}

[ "${GATE_PULL_REQUEST:-}" = "true" ] || no "not a pull request"
[ -n "${GATE_HEAD_SHA:-}" ] || no "no head commit given"
[ -n "${GATE_HEAD_REPO:-}" ] || no "no head repository given"
[ -n "${GATE_BASE_REPO:-}" ] || no "no base repository given"
[ -n "${GATE_HEAD_BRANCH:-}" ] || no "no source branch given"
[ -n "${GATE_DEFAULT_BRANCH:-}" ] || no "no default branch given"
[ "$GATE_HEAD_REPO" = "$GATE_BASE_REPO" ] || no "pull request from another repository"
[ "$GATE_HEAD_BRANCH" != "$GATE_DEFAULT_BRANCH" ] || no "source branch is the default branch"

# Unquoted on purpose: the command may be several words. Its output joins standard error.
if $PREPUSH_CI_CMD verify "$GATE_HEAD_SHA" >&2; then
    echo "verified=true"
else
    no "head commit does not verify"
fi
