#!/bin/sh
set -eu
K="$(cd "$(dirname "$0")" && pwd)"
exec python "$K/ws_upgrade.py" "$@"
