#!/usr/bin/env bash
# Rebuild the `pages` branch from scratch from the current commit's public/
# directory, plus a freshly generated index.html and the Codeberg Pages
# custom-domain file.
#
# Always force-pushes a fresh orphan commit: `pages` is a pure build
# artifact fully regenerated every run, so keeping its history serves no
# purpose and would let every past revision of every large published file
# (e.g. foi-disclosures) accumulate against Codeberg's shared org-wide git
# storage quota forever. Fails loudly on any error; no retry, no fallback.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKTREE_DIR="$(mktemp -d /tmp/pages-build.XXXXXX)"
CUSTOM_DOMAIN="data.publicinformation.ie"

cleanup() {
  git -C "$REPO_ROOT" worktree remove --force "$WORKTREE_DIR" 2>/dev/null || true
  rm -rf "$WORKTREE_DIR"
}
trap cleanup EXIT

echo "Fetching latest 'pages' branch state from origin..."
git -C "$REPO_ROOT" fetch origin pages

echo "Creating worktree for 'pages' branch at $WORKTREE_DIR..."
git -C "$REPO_ROOT" worktree add -B pages "$WORKTREE_DIR" origin/pages

echo "Clearing worktree contents (except .git)..."
find "$WORKTREE_DIR" -mindepth 1 -maxdepth 1 ! -name ".git" -exec rm -rf {} +

echo "Copying public/ into worktree root..."
cp -R "$REPO_ROOT/public/." "$WORKTREE_DIR/"

echo "Writing custom domain file..."
printf '%s\n' "$CUSTOM_DOMAIN" > "$WORKTREE_DIR/.domains"

cd "$WORKTREE_DIR"
git add -A

if git diff --cached --quiet; then
  echo "No changes to publish; pages branch is already up to date."
  exit 0
fi

echo "Creating fresh orphan commit (no parent history) for pages branch..."
git checkout --orphan pages-rebuild
git add -A
git commit -m "chore: rebuild pages branch from public/"
git branch -M pages-rebuild pages

echo "Force-pushing squashed 'pages' branch to origin..."
git push --force origin pages
echo "Published."
