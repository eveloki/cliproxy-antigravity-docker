#!/usr/bin/env bash
set -euo pipefail
image=${1:?image required}
root=$(mktemp -d)
project="cpa-compat-$RANDOM"
model=$(cat "$(dirname "$0")/../scripts/test-model.txt")
expected=$(python3 -c 'import json; print(json.load(open("upstream-versions.json"))["agy"]["version"])')
[[ "$(docker run --rm --network none "$image" agy --version)" == "$expected" ]]
# These native commands must work without a writable rootfs or config creation.
for mode in help discover; do
  args=(-help)
  if [[ "$mode" == discover ]]; then args=(discover --help); fi
  native=$(docker run --rm --network none --read-only --tmpfs /tmp --entrypoint /CLIProxyAPI/CLIProxyAPI "$image" "${args[@]}" 2>&1)
  wrapped=$(docker run --rm --network none --read-only --tmpfs /tmp "$image" ./CLIProxyAPI "${args[@]}" 2>&1)
  [[ "$native" == "$wrapped" ]]
done
echo 'PASS: native help and discover help match direct CPA execution on a read-only rootfs.'
compose() { CLIPROXY_COMPAT_IMAGE="$image" CLIPROXY_TEST_MODEL="$model" docker compose -p "$project" -f "$root/compose.yaml" "$@"; }
cleanup() {
  result=$?
  if [[ "$result" != 0 ]]; then compose logs >&2 || true; fi
  compose down --remove-orphans >/dev/null || true
  # The container creates root-owned files in these synthetic test mounts.
  docker run --rm --entrypoint sh -v "$root:/test" "$image" -c 'rm -rf /test/*' || true
  rmdir "$root" || true
}
trap cleanup EXIT
mkdir -p "$root/auths" "$root/logs" "$root/plugins" "$root/data"
cat > "$root/config.yaml" <<'YAML'
# Existing legacy layout, deliberately left unchanged by the distribution.
host: '0.0.0.0'
port: 8317
api-keys: ['compat-client-key']
auth-dir: '/root/.cli-proxy-api'
logging-to-file: true
remote-management:
  allow-remote: false
  disable-control-panel: true
plugins:
  enabled: true
  dir: '/CLIProxyAPI/plugins'
  configs:
    cliproxy-antigravity:
      enabled: true
      binary_path: '/usr/local/bin/agy'
      workdir: '/CLIProxyAPI/data/agy-workspace'
YAML
# Disabled synthetic native credential: enumerate only, never contact a provider.
printf '%s\n' '{"type":"codex","email":"compat@example.invalid","access_token":"synthetic-not-a-token","disabled":true}' > "$root/auths/compat-codex.json"
printf 'existing plugin sidecar\n' > "$root/plugins/user-sidecar.txt"
printf 'existing data\n' > "$root/data/existing.db"
config_hash=$(sha256sum "$root/config.yaml" | cut -d ' ' -f1)
auth_hash=$(sha256sum "$root/auths/compat-codex.json" | cut -d ' ' -f1)
cat > "$root/compose.yaml" <<'YAML'
services:
  cli-proxy-api:
    image: ${CLIPROXY_COMPAT_IMAGE}
    pull_policy: always
    ports:
      - '127.0.0.1::8317'
    volumes:
      - ./config.yaml:/CLIProxyAPI/config.yaml:ro
      - ./auths:/root/.cli-proxy-api
      - ./logs:/CLIProxyAPI/logs
      - ./plugins:/CLIProxyAPI/plugins
      - ./data:/CLIProxyAPI/data
    environment:
      MANAGEMENT_PASSWORD: compat-management
      CLIPROXY_TEST_MODEL: ${CLIPROXY_TEST_MODEL}
    restart: unless-stopped
networks:
  default:
    internal: true
YAML
start() {
  compose create --pull never >/dev/null
  container=$(compose ps -aq cli-proxy-api)
  docker cp "$root/mock-agy.sh" "$container:/opt/agy/agy"
  compose start >/dev/null
  for attempt in {1..30}; do
    if compose exec -T cli-proxy-api python3 /opt/cliproxy/scripts/healthcheck.py; then return; fi
    sleep 1
  done
  return 1
}
# docker cp preserves source mode, so make an executable test fixture.
cp "$(dirname "$0")/mock-agy.sh" "$root/mock-agy.sh"
chmod 755 "$root/mock-agy.sh"
start
[[ "$(compose exec -T cli-proxy-api id -u)" == 0 ]]
compose exec -T cli-proxy-api python3 /opt/cliproxy/scripts/smoke.py
compose exec -T cli-proxy-api python3 /opt/cliproxy/scripts/smoke.py --stream
compose exec -T cli-proxy-api agy --test-home
compose exec -T cli-proxy-api python3 - <<'PY'
import json, os, urllib.request
from datetime import datetime, timezone
from pathlib import Path
assert os.getcwd() == '/CLIProxyAPI'
assert os.environ['HOME'] == '/root'
assert Path('/CLIProxyAPI/plugins/cliproxy-antigravity.so').is_file()
assert Path('/CLIProxyAPI/plugins/user-sidecar.txt').read_text() == 'existing plugin sidecar\n'
assert Path('/CLIProxyAPI/data/existing.db').read_text() == 'existing data\n'
Path('/CLIProxyAPI/plugins/writable.txt').write_text('plugin store can write here')
Path('/CLIProxyAPI/data/persisted.db').write_text('plugin data survives')
assert Path('/CLIProxyAPI/logs/main.log').is_file()
request = urllib.request.Request('http://127.0.0.1:8317/v0/management/auth-files',
    headers={'Authorization': 'Bearer compat-management'})
with urllib.request.urlopen(request, timeout=10) as response:
    versions = dict(line.split('=', 1) for line in Path('/opt/cliproxy/upstream-versions.txt').read_text().splitlines() if '=' in line)
    assert response.headers.get('X-CPA-VERSION') == versions['CPA_VERSION']
    assert response.headers.get('X-CPA-COMMIT') == versions['CPA_COMMIT']
    build_date = response.headers.get('X-CPA-BUILD-DATE', '')
    assert build_date.endswith('Z'), repr(build_date)
    built_at = datetime.fromisoformat(build_date.replace('Z', '+00:00'))
    assert datetime(2020, 1, 1, tzinfo=timezone.utc) < built_at <= datetime.now(timezone.utc), build_date
    files = json.load(response)['files']
print('PASS: management API version/commit match bundled provenance; valid UTC CPA build date: ' + build_date)
assert any(item.get('name') == 'compat-codex.json' and item.get('provider') == 'codex' for item in files), files
PY
compose down >/dev/null
# Exercise the upstream executable command and native -config override on recreation.
python3 - "$root/compose.yaml" <<'PYCODE'
from pathlib import Path
import sys
path = Path(sys.argv[1])
path.write_text(path.read_text().replace('    pull_policy: always', '    command: ["./CLIProxyAPI", "-config", "/CLIProxyAPI/ignored.yaml", "--config=/CLIProxyAPI/config.yaml"]\n    pull_policy: always'))
PYCODE
start
compose exec -T cli-proxy-api python3 - <<'PY'
from pathlib import Path
assert not Path('/CLIProxyAPI/ignored.yaml').exists()
assert Path('/root/.cli-proxy-api/agy-home/.compat-cli-state').read_text() == 'persistent CLI state\n'
assert Path('/CLIProxyAPI/data/persisted.db').read_text() == 'plugin data survives'
assert Path('/CLIProxyAPI/plugins/writable.txt').is_file()
PY
[[ "$(sha256sum "$root/config.yaml" | cut -d ' ' -f1)" == "$config_hash" ]]
[[ "$(sha256sum "$root/auths/compat-codex.json" | cut -d ' ' -f1)" == "$auth_hash" ]]
echo 'PASS: upstream five-bind layout, root/WORKDIR, legacy read-only config, native CPA auth, writable plugins/logs/data, agy child HOME and recreation persistence.'
