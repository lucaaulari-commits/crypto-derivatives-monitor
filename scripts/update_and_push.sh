#!/usr/bin/env bash
# Update the data locally and publish it (same steps as .github/workflows/update.yml).
# Used because Bybit blocks GitHub-hosted runners.
# Run from anywhere:  ./scripts/update_and_push.sh
set -euo pipefail

cd "$(dirname "$0")/.."           # go to the repository root
PYTHON="${PYTHON:-.venv/bin/python}"

git pull --ff-only                # start from the latest published version
"$PYTHON" -m scripts.update       # download new records, rebuild docs/index.html

# Commit only when there are new funding records (the page changes on every build).
git add data docs
if git diff --staged --quiet -- data; then
  echo "No new funding records: nothing to commit."
  git restore --staged docs && git restore docs
else
  git commit -m "Update funding data $(date -u +'%Y-%m-%d %H:%M') UTC"
  git push
fi
