#!/usr/bin/env bash
set -euo pipefail
umask 077
install_root="${HOME:?HOME must be set}/.local/bin"
mkdir -p "$install_root"
# Serialize installations across compose run / exec / service startup.
exec 9>"$HOME/.agy-install.lock"
flock -w 360 9
if [[ -x "$install_root/agy" ]]; then
  exit 0
fi
if [[ "${AGY_AUTO_INSTALL:-true}" != true ]]; then
  echo 'agy missing; enable AGY_AUTO_INSTALL or install it into ~/.local/bin.' >&2
  exit 1
fi
installer=$(mktemp)
trap 'rm -f "$installer"' EXIT
echo 'Installing agy from the official installer. Distribution status: NOT READY.' >&2
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
  --connect-timeout 20 --max-time 120 --retry 2 \
  https://antigravity.google/cli/install.sh --output "$installer"
expected=${AGY_INSTALLER_SHA256:-}
if [[ -n "$expected" ]]; then
  [[ "$expected" =~ ^[0-9a-fA-F]{64}$ ]] || { echo 'Invalid installer SHA256.' >&2; exit 2; }
  printf '%s  %s\n' "$expected" "$installer" | sha256sum --check --status
fi
sha256sum "$installer" | cut -d ' ' -f 1 > "$HOME/.agy-installer-sha256"
# Official documented flags; keep the normal installation path.
timeout --kill-after=10s 300s bash "$installer" --skip-aliases --skip-path
[[ -x "$install_root/agy" ]] || { echo 'Installer did not produce ~/.local/bin/agy; inspect upstream changes.' >&2; exit 1; }
# Record provenance only. Never record OAuth data or print credential files.
timeout --kill-after=5s 20s "$install_root/agy" --version > "$HOME/.agy-version.txt"
