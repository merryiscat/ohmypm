#!/bin/sh
# Compatibility entrypoint. 1.0 uses the cross-platform Python installer.
# Legacy --install shared/setup arguments are ignored; each new task owns setup.
set -eu
P=${1:?usage: ws-upgrade.sh project [--install] [--migrate-v1] [--dry-run]}
shift
K="$(cd "$(dirname "$0")" && pwd)"
MIGRATE=""
DRY=""
for arg in "$@"; do
  case "$arg" in --migrate-v1) MIGRATE="--migrate-v1";; --dry-run) DRY="--dry-run";; esac
done
exec python "$K/ws_upgrade.py" "$P" $MIGRATE $DRY
