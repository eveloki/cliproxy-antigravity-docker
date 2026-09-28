#!/usr/bin/env bash
set -euo pipefail
image=${1:?image required}
model=$(cat "$(dirname "$0")/../scripts/test-model.txt")
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
  printf '%s\tGemini 3.5 Flash Lite\n' "$CLIPROXY_TEST_MODEL"
elif [ "${1:-}" = --version ]; then
  printf 'mock-agy (NO GOOGLE AUTH)\n'
else
  selected_model=
  format=
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --model) shift; selected_model=${1:-} ;;
      --output-format) shift; format=${1:-} ;;
    esac
    [ "$#" -gt 0 ] && shift
  done
  if [ "$selected_model" != "$CLIPROXY_TEST_MODEL" ]; then
    echo 'Pinned model missing or changed; refusing mock fallback.' >&2
    exit 2
  fi
  cat >/dev/null
  printf '%s:%s\n' "$format" "$selected_model" >> "$HOME/mock-agy-invocations"
  if [ "$format" = stream-json ]; then
    printf '%s\n' '{"event":"step_update","step_update":{"step_type":"agent_response","text_delta":"mock response"}}'
    printf '%s\n' '{"event":"result","result":{"status":"SUCCESS","response":"mock response","usage":{"input_tokens":1,"output_tokens":1,"total_tokens":2}}}'
  else
    printf '%s\n' '{"status":"SUCCESS","response":"mock response","usage":{"input_tokens":1,"output_tokens":1,"total_tokens":2}}'
  fi
fi
MOCK
chmod 755 "$mock"
container=$(docker create --network none --cap-drop ALL --security-opt no-new-privileges:true \
  -e AGY_AUTO_INSTALL=false -e CLIPROXY_TEST_MODEL="$model" "$image")
docker cp "$mock" "$container:/home/cliproxy/.local/bin/agy"
docker start "$container" >/dev/null
ready=false
for attempt in {1..30}; do
  if docker exec "$container" python3 /opt/cliproxy/scripts/healthcheck.py; then ready=true; break; fi
  sleep 2
done
if [[ "$ready" != true ]]; then docker logs "$container"; exit 1; fi
docker exec -i "$container" python3 - <<'PY'
import json, os, time, urllib.request, urllib.error, yaml
from pathlib import Path
api_model = 'agy/' + os.environ['CLIPROXY_TEST_MODEL']
config = yaml.safe_load(open('/config/config.yaml'))
headers = {'Authorization': 'Bearer ' + config['access']['api-keys'][0], 'Content-Type': 'application/json'}
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
# HTTP liveness can precede provider registration. Wait for the plugin model.
for attempt in range(30):
    req = urllib.request.Request('http://127.0.0.1:8317/v1/models', headers=headers)
    with opener.open(req, timeout=5) as response:
        models = json.load(response)['data']
    if any(model['id'] == api_model for model in models):
        break
    time.sleep(1)
else:
    raise RuntimeError('Pinned plugin model missing: ' + api_model + '; no fallback allowed')
payload = {'model': api_model, 'messages': [{'role': 'user', 'content': 'Reply only with OK'}]}
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
payload['stream'] = True
req = urllib.request.Request('http://127.0.0.1:8317/v1/chat/completions',
    data=json.dumps(payload).encode(), headers=headers)
chunks, finished, done = [], False, False
with opener.open(req, timeout=30) as response:
    for raw in response:
        line = raw.decode().strip()
        if not line.startswith('data:'):
            continue
        data = line[5:].strip()
        if data == '[DONE]':
            done = True
            break
        event = json.loads(data)
        assert not event.get('error'), event
        for choice in event.get('choices', []):
            chunks.append(choice.get('delta', {}).get('content') or '')
            finished = finished or bool(choice.get('finish_reason'))
assert ''.join(chunks) == 'mock response' and finished and done, (chunks, finished, done)
# Direct executor routing must preserve inbound API authentication.
req = urllib.request.Request('http://127.0.0.1:8317/v1/chat/completions',
    data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
try:
    opener.open(req, timeout=5)
except urllib.error.HTTPError as error:
    assert error.code == 401, error.code
else:
    raise AssertionError('Client API authentication was bypassed')
# Nor may a bare model silently hit the plugin instead of a native provider.
payload.update(model=os.environ['CLIPROXY_TEST_MODEL'], stream=False)
req = urllib.request.Request('http://127.0.0.1:8317/v1/chat/completions',
    data=json.dumps(payload).encode(), headers=headers)
try:
    opener.open(req, timeout=5)
except urllib.error.HTTPError:
    pass
else:
    raise AssertionError('Unprefixed model was unexpectedly handled')
assert not list(Path('/home/cliproxy/.cli-proxy-api').glob('*.json')), 'Unexpected CPA credentials'
calls = Path('/home/cliproxy/mock-agy-invocations').read_text().splitlines()
model = os.environ['CLIPROXY_TEST_MODEL']
assert calls == ['json:' + model, 'stream-json:' + model], calls
PY
echo 'PASS: non-root container; pinned model reaches mock agy in non-streaming and SSE modes; client auth and native routes preserved.'
echo 'Google OAuth and real agy are NOT tested.'
