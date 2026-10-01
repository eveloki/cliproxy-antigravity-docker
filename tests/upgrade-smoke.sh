#!/usr/bin/env bash
set -euo pipefail
image=${1:?image required}
# Published v8.0.6-0.1.3-agy1.2.12-rc.1; pin the original bytes, not the moving rc alias.
legacy=ghcr.io/eveloki/cliproxy-antigravity-docker@sha256:1d8432eb6bc1f202adc15c38f45fe075b01f04f3f82ba1880feb9c0b08611f39
root=$(mktemp -d)
project="cpa-upgrade-$RANDOM-$$"
home_volume="$project-home"
config_volume="$project-config"
model=$(cat scripts/test-model.txt)
compose() { IMAGE="$image" CLIPROXY_TEST_MODEL="$model" docker compose -p "$project" -f compose.yaml -f "$root/override.yaml" "$@"; }
cleanup() {
  result=$?
  if [[ "$result" != 0 && -f "$root/override.yaml" ]]; then compose logs >&2 || true; fi
  if [[ -f "$root/override.yaml" ]]; then compose down --remove-orphans >/dev/null || true; fi
  docker volume rm "$home_volume" "$config_volume" >/dev/null || true
  rm -rf "$root"
}
trap cleanup EXIT
docker pull "$legacy" >/dev/null
docker volume create "$home_volume" >/dev/null
docker volume create "$config_volume" >/dev/null
mounts=(--mount "type=volume,src=$home_volume,dst=/home/cliproxy" --mount "type=volume,src=$config_volume,dst=/config")
# Let the old image populate both named volumes and generate its original config.
docker run --rm --network none "${mounts[@]}" "$legacy" init
docker run --rm -i --network none "${mounts[@]}" "$legacy" python3 - record < tests/upgrade-state.py
cat > "$root/override.yaml" <<YAML
services:
  cliproxy:
    network_mode: none
    ports: !reset []
    environment:
      CLIPROXY_TEST_MODEL: \${CLIPROXY_TEST_MODEL}
volumes:
  agy-home:
    external: true
    name: $home_volume
  cpa-config:
    external: true
    name: $config_volume
YAML
cp tests/mock-agy.sh "$root/mock-agy.sh"
chmod 755 "$root/mock-agy.sh"
start() {
  compose create --pull never >/dev/null
  container=$(compose ps -aq cliproxy)
  docker cp "$root/mock-agy.sh" "$container:/opt/agy/agy"
  compose start >/dev/null
  for attempt in {1..30}; do
    if compose exec -T cliproxy python3 /opt/cliproxy/scripts/healthcheck.py; then return; fi
    sleep 1
  done
  return 1
}
start
compose exec -T cliproxy python3 - new < tests/upgrade-state.py
compose exec -T cliproxy python3 /opt/cliproxy/scripts/smoke.py
compose exec -T cliproxy python3 /opt/cliproxy/scripts/smoke.py --stream
compose exec -T cliproxy agy --test-home
compose down >/dev/null
start
compose exec -T cliproxy python3 - new < tests/upgrade-state.py
compose exec -T cliproxy python3 -c 'from pathlib import Path; assert Path("/home/cliproxy/.compat-cli-state").read_text() == "persistent CLI state\n"'
compose down >/dev/null
# Roll back just the image with the same explicit non-root Compose and persisted volumes.
image=$legacy
start
compose exec -T cliproxy python3 - old < tests/upgrade-state.py
echo 'PASS: actual RC-created named volumes upgrade without pre-creating plugins, survive recreation and roll back; no real credentials used.'
