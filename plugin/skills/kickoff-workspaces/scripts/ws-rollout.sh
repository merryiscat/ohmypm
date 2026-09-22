#!/bin/sh
# Explicit targets only. No discovery, staging, commits or project-file installation.
set -eu
K="$(cd "$(dirname "$0")" && pwd)"
[ "$#" -gt 0 ] || { echo 'usage: ws-rollout.sh <project> [<project> ...]' >&2; exit 2; }
for project in "$@"; do
  python "$K/ws_upgrade.py" "$project"
done
