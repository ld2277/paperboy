#!/bin/bash
# One-time: push the paperboy publishing machinery to GitHub.
# Run this from inside the paperboy folder:  bash setup.sh
set -e

REPO="https://github.com/ld2277/paperboy.git"

if [ ! -d .git ]; then
  git init -q
  git remote add origin "$REPO"
  git fetch -q origin main
  git checkout -q -B main origin/main
fi

git add -A
git commit -qm "Add publishing machinery: renderer, relay, workflow" || {
  echo "nothing to commit"; exit 0; }
git push -u origin main
echo
echo "Pushed. Now, on github.com/ld2277/paperboy:"
echo "  Settings > Pages          -> Source: Deploy from a branch, main, / (root)"
echo "  Settings > Variables      -> PAPERBOY_OUTBOX = <Drive folder id>"
echo "  Actions tab               -> run 'Publish paperboy briefs' to test"
