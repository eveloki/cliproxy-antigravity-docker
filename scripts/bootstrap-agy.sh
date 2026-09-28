#!/usr/bin/env bash
set -euo pipefail
# Compatibility entry point: the pinned executable now lives in the image.
[[ -x /opt/agy/agy ]] || { echo 'Bundled agy missing; rebuild the image.' >&2; exit 1; }
