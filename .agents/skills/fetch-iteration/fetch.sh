#!/usr/bin/env bash
# Adopt the iteration after the one in ITERATION (or the first, if there is
# none). The factory source lives in factory/ for every iteration.
# This script may be called from any directory.
# Reads the course from GitHub at $COURSE_REF (default main). Does not
# commit.
set -euo pipefail

ref=${COURSE_REF:-main}
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd -P)
mkdir -p "$root/factory"
cd "$root/factory"
seed="$root/tetris/spec.md"
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

mkdir -p spec/features "$(dirname "$seed")"
cp "$src/README.md" "$src/FACTORY.md" spec/
rm -rf spec/features
cp -r "$src/features" spec/features
if [ -f "$src/spec.md" ] && [ ! -e "$seed" ]; then
  cp "$src/spec.md" "$seed"
fi

echo "$id WIP" > ITERATION
echo "adopted iteration $id (${next#* })"
