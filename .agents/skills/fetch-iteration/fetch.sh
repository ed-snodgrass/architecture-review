#!/usr/bin/env bash
# Adopt the iteration after the one in ITERATION (or the first, if there is
# none). Run from the factory's folder: tetris/.factory through iteration
# 003, factory/ from 004 (this script moves it there when it adopts 004).
# Reads the course from GitHub at $COURSE_REF (default main). Does not
# commit.
set -euo pipefail

ref=${COURSE_REF:-main}
root=$(git rev-parse --show-toplevel)
seeds="$root/tetris/seeds"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

curl -fsSL "https://codeload.github.com/lean-software-production/tutorial/tar.gz/$ref" \
  | tar -xz -C "$tmp" --strip-components=1

# Ledger rows look like: | 001 | [Title](001-folder/README.md) |
ledger=$(grep -oE '^\| [0-9]{3} \| \[[^]]*\]\([^/]+/' "$tmp/docs/iterations/README.md" \
  | sed -E 's/^\| ([0-9]{3}) .*\(([^/]+)\/$/\1 \2/')

current=$(cut -d' ' -f1 ITERATION 2>/dev/null || true)
if [ -z "$current" ]; then
  next=$(echo "$ledger" | head -1)
else
  next=$(echo "$ledger" | awk -v c="$current" 'found { print; exit } $1 == c { found = 1 }')
fi
if [ -z "$next" ]; then
  echo "nothing left to fetch after $current"
  exit 1
fi

id=${next%% *}
src="$tmp/docs/iterations/${next#* }"

mkdir -p spec/features "$seeds"
cp "$src/README.md" "$src/FACTORY.md" spec/
rm -rf spec/features
cp -r "$src/features" spec/features
if [ -f "$src/spec.md" ] && [ ! -e "$seeds/tetris.md" ]; then
  cp "$src/spec.md" "$seeds/tetris.md"
fi
rm -rf stand-ins
cp -r "$tmp/stand-ins" stand-ins

echo "$id WIP" > ITERATION
echo "adopted iteration $id (${next#* })"

# From 004 the factory has a codebase of its own, beside tetris/.
if [ "$((10#$id))" -ge 4 ] && [ "$(pwd -P)" = "$(cd "$root/tetris/.factory" 2>/dev/null && pwd -P)" ]; then
  cd "$root"
  git mv tetris/.factory factory
  ln -sfn ../../.agents/skills factory/.claude/skills
  git add factory/.claude/skills
  echo "moved the factory to factory/: reopen your coding agent there"
fi
