#!/usr/bin/env bash
set -euo pipefail
# Do not reuse ~/.local/bin/agy from an older persistent HOME volume.
binary=/opt/agy/agy
[[ -x "$binary" ]] || { echo 'Bundled agy missing; rebuild the image.' >&2; exit 127; }
exec "$binary" "$@"
