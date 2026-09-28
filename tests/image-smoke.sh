#!/usr/bin/env bash
set -euo pipefail
image=${1:?image required}
mock=$(mktemp)
container=
cleanup() {
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
docker exec "$container" python3 /opt/cliproxy/scripts/smoke.py
echo 'PASS: non-root container, config initialization, CPA/plugin request routing using mock agy.'
echo 'Google OAuth and real agy are NOT tested.'
