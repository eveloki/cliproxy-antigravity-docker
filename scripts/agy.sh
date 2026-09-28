#!/usr/bin/env bash
set -euo pipefail
binary="${HOME:?}/.local/bin/agy"
[[ -x "$binary" ]] || { echo 'agy missing. Run the container login command first.' >&2; exit 127; }
exec "$binary" "$@"
