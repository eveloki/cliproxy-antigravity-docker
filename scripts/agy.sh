#!/usr/bin/env bash
set -euo pipefail
# CPA keeps the upstream HOME. Only the agy child uses this persistent subdirectory.
# The previous non-root Compose explicitly sets AGY_HOME=/home/cliproxy.
agy_home=${AGY_HOME:-${HOME:?}/.cli-proxy-api/agy-home}
mkdir -p -m 700 "$agy_home"
exec env HOME="$agy_home" /opt/agy/agy "$@"
