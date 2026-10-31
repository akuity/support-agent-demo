#!/bin/sh
# For maintainers: builds the demo's commit history, one agent version per
# commit. Run each scenario once, in order, in a fresh repo (see README.md),
# then push.
#
#   demo/apply.sh 01-initial              # first commit: the whole repo, with v1 in agent/
#   demo/apply.sh 02-model-upgrade        # new model         -> sails through
#   demo/apply.sh 03-prompt-regression    # "harmless" prompt -> evals fail in dev
#   demo/apply.sh 04-refunds              # new tool + policy -> allowed in prod-us, blocked in prod-eu
set -eu

cd "$(dirname "$0")/.."
scenario="demo/${1:?usage: demo/apply.sh <scenario>}"
[ -d "$scenario" ] || { echo "no such scenario: $scenario" >&2; exit 1; }

cp -R "$scenario/agent/." agent/
if git rev-parse -q --verify HEAD >/dev/null; then
  git add agent
else
  git add -A
fi
git commit -m "$(cat "$scenario/MESSAGE")"
git show --stat --oneline HEAD
