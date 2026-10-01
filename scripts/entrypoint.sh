#!/usr/bin/env bash
set -euo pipefail
case "${1:-./CLIProxyAPI}" in
  serve|./CLIProxyAPI|CLIProxyAPI|/CLIProxyAPI/CLIProxyAPI|/opt/cliproxy/CLIProxyAPI)
    if [[ $# -gt 0 ]]; then shift; fi
    ;;
  -*) ;;
  login)
    shift
    exec agy "$@"
    ;;
  doctor)
    shift
    exec /opt/cliproxy/scripts/doctor.sh "$@"
    ;;
  init)
    exec python3 /opt/cliproxy/scripts/init-config.py
    ;;
  *) exec "$@" ;;
esac
config_path=$(python3 /opt/cliproxy/scripts/runtime_config.py path "$@")
# A missing bind-mounted file can become a directory. Never overwrite it.
if [[ -d "$config_path" ]]; then
  echo "Config path is a directory; create the host config file before starting: $config_path" >&2
  exit 1
fi
if [[ ! -f "$config_path" ]]; then
  python3 /opt/cliproxy/scripts/init-config.py "$config_path"
fi
python3 /opt/cliproxy/scripts/prepare-plugins.py "$config_path"
python3 /opt/cliproxy/scripts/runtime_config.py record "$config_path"
exec /CLIProxyAPI/CLIProxyAPI -config "$config_path" "$@"
