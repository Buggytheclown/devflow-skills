#!/usr/bin/env bash
set -euo pipefail

if (( $# > 1 )); then
  printf 'Usage: %s [skills-directory]\n' "$0" >&2
  exit 2
fi

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
target_dir="${1:-$HOME/.agents/skills}"
shopt -s nullglob
skill_dirs=("$repo_dir"/skills/devflow-*)

if (( ${#skill_dirs[@]} == 0 )); then
  printf 'No devflow skills found in %s/skills\n' "$repo_dir" >&2
  exit 1
fi

# Check every destination before creating any links.
for source_dir in "${skill_dirs[@]}"; do
  if [[ ! -f "$source_dir/SKILL.md" ]]; then
    printf 'Missing SKILL.md: %s\n' "$source_dir" >&2
    exit 1
  fi
  destination="$target_dir/${source_dir##*/}"
  if [[ -L "$destination" && "$(readlink "$destination")" == "$source_dir" ]]; then
    continue
  fi
  if [[ -e "$destination" || -L "$destination" ]]; then
    printf 'Installation stopped: destination already exists: %s\n' "$destination" >&2
    exit 1
  fi
done

mkdir -p -- "$target_dir"
for source_dir in "${skill_dirs[@]}"; do
  destination="$target_dir/${source_dir##*/}"
  if [[ -L "$destination" && "$(readlink "$destination")" == "$source_dir" ]]; then
    printf 'Already installed: %s\n' "${source_dir##*/}"
  else
    ln -s -- "$source_dir" "$destination"
    printf 'Installed: %s\n' "${source_dir##*/}"
  fi
done
