#!/usr/bin/env bash
set -euo pipefail
umask 077
echo 'CLIProxyAPI Antigravity Docker — stable release.' >&2
case "${1:-serve}" in
  serve|login|doctor|init)
    python3 /opt/cliproxy/scripts/init-config.py
    ;;
esac
case "${1:-serve}" in
  serve)
    /opt/cliproxy/scripts/bootstrap-agy.sh
    # No authentication gate here: first-login recovery must remain possible.
    exec /opt/cliproxy/CLIProxyAPI -config /config/config.yaml
    ;;
  login)
    /opt/cliproxy/scripts/bootstrap-agy.sh
    exec agy
    ;;
  doctor)
    /opt/cliproxy/scripts/bootstrap-agy.sh
    exec /opt/cliproxy/scripts/doctor.sh
    ;;
  init) exit 0 ;;
  *) exec "$@" ;;
esac
