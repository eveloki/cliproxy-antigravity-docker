#!/usr/bin/env bash
set -euo pipefail
image=${1:?image required}
mock=$(mktemp)
container=
cleanup() {
  result=$?
  if [[ "$result" != 0 && -n "$container" ]]; then docker logs "$container" >&2 || true; fi
  if [[ -n "$container" ]]; then docker rm -f "$container" >/dev/null; fi
  rm -f "$mock"
}
trap cleanup EXIT
cat > "$mock" <<'MOCK'
#!/bin/sh
if [ "${1:-}" = models ]; then
  printf 'mock-model\tMock Model\n'
elif [ "${1:-}" = --version ]; then
  printf 'mock-agy (NO GOOGLE AUTH)\n'
else
  cat >/dev/null
  printf '%s\n' '{"status":"SUCCESS","response":"mock response","usage":{"input_tokens":1,"output_tokens":1,"total_tokens":2}}'
fi
MOCK
chmod 755 "$mock"
container=$(docker create --network none --cap-drop ALL --security-opt no-new-privileges:true \
  -e AGY_AUTO_INSTALL=false "$image")
docker cp "$mock" "$container:/home/cliproxy/.local/bin/agy"
docker start "$container" >/dev/null
ready=false
for attempt in {1..30}; do
  if docker exec "$container" python3 /opt/cliproxy/scripts/healthcheck.py; then ready=true; break; fi
  sleep 2
done
if [[ "$ready" != true ]]; then docker logs "$container"; exit 1; fi
docker exec -i "$container" python3 - <<'PY'
import json, time, urllib.request, urllib.error, yaml
config = yaml.safe_load(open('/config/config.yaml'))
headers = {'Authorization': 'Bearer ' + config['access']['api-keys'][0], 'Content-Type': 'application/json'}
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
# HTTP liveness can precede provider registration. Wait for the plugin model.
for attempt in range(30):
    req = urllib.request.Request('http://127.0.0.1:8317/v1/models', headers=headers)
    with opener.open(req, timeout=5) as response:
        models = json.load(response)['data']
    if any(model['id'] == 'agy/default' for model in models):
        break
    time.sleep(1)
else:
    raise RuntimeError('Plugin model missing: ' + json.dumps(models))
payload = {'model': 'agy/default', 'messages': [{'role': 'user', 'content': 'Reply only with OK'}]}
req = urllib.request.Request('http://127.0.0.1:8317/v1/chat/completions',
    data=json.dumps(payload).encode(), headers=headers)
try:
    with opener.open(req, timeout=30) as response:
        message = json.load(response)['choices'][0]['message']
except urllib.error.HTTPError as error:
    # This isolated container has only synthetic data, no real account or prompt.
    print('Mock request error:', error.code, error.read().decode())
    raise
assert message.get('content') == 'mock response', message
PY
echo 'PASS: non-root container, config initialization, CPA/plugin request routing using mock agy.'
echo 'Google OAuth and real agy are NOT tested.'
