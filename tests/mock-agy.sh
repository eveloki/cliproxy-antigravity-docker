#!/bin/sh
if [ "${1:-}" = models ]; then
  printf '%s\tGemini 3.8 Flash\n' "$CLIPROXY_TEST_MODEL"
elif [ "${1:-}" = --test-home ]; then
  printf "persistent CLI state\n" > "$HOME/.compat-cli-state"
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
