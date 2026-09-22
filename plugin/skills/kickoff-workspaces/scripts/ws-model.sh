#!/bin/sh
# Legacy model switches no longer edit project documents.
set -eu
echo 'Use environment_cli.py register --profiles <roles.json> for future tasks; running tasks stay pinned.' >&2
exit 2
