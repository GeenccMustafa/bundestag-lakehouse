#!/usr/bin/env bash
# Sync vendored Claude skills from .claude/skills/vendor.lock.
# - Copies each listed skill directory from its upstream repo at the pinned commit.
# - Removes previously vendored skills that are no longer listed.
# - Project-owned skills (no .upstream file) are never touched.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
SKILLS="$ROOT/.claude/skills"
LOCK="$SKILLS/vendor.lock"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

listed=()
while read -r name repo path sha; do
  [[ -z "${name:-}" || "$name" == \#* ]] && continue
  listed+=("$name")
  src="$TMP/${repo//\//__}"
  if [[ ! -d "$src" ]]; then
    git clone -q --filter=blob:none "https://github.com/$repo.git" "$src"
  fi
  git -C "$src" checkout -q "$sha"
  full_sha="$(git -C "$src" rev-parse HEAD)"

  rm -rf "${SKILLS:?}/$name"
  cp -R "$src/$path" "$SKILLS/$name"
  # Keep the upstream license next to the copy (required by MIT / Apache-2.0 / CC-BY-SA).
  for lic in LICENSE LICENSE.md LICENSE.txt; do
    [[ -f "$src/$lic" ]] && cp "$src/$lic" "$SKILLS/$name/LICENSE.upstream" && break
  done
  printf 'repo: %s\npath: %s\ncommit: %s\n' "$repo" "$path" "$full_sha" > "$SKILLS/$name/.upstream"

  if [[ "$sha" == "HEAD" ]]; then
    short="$(git -C "$src" rev-parse --short HEAD)"
    sed -i.bak -E "s#^($name[[:space:]]+$repo[[:space:]]+$path[[:space:]]+)HEAD#\1$short#" "$LOCK" && rm -f "$LOCK.bak"
  fi
  echo "synced  $name  ($repo@${full_sha:0:7})"
done < "$LOCK"

for dir in "$SKILLS"/*/; do
  name="$(basename "$dir")"
  [[ -f "$dir/.upstream" ]] || continue
  if [[ ! " ${listed[*]} " =~ " $name " ]]; then
    rm -rf "$dir"
    echo "removed $name"
  fi
done
