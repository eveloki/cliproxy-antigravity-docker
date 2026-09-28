#!/usr/bin/env python3
"""Explicit live API checks. These consume upstream quota; never run in healthcheck."""
import argparse
import json
from pathlib import Path
import urllib.request
import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='agy/default')
    parser.add_argument('--tools', action='store_true')
    parser.add_argument('--stream', action='store_true')
    args = parser.parse_args()
    if args.tools and args.stream:
        parser.error('Run --tools and --stream separately; streaming tool calls remain a manual gate.')
    config = yaml.safe_load(Path('/config/config.yaml').read_text())
    key = config['access']['api-keys'][0]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(payload):
        req = urllib.request.Request('http://127.0.0.1:8317/v1/chat/completions',
            data=json.dumps(payload).encode(), headers={
                'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        return opener.open(req, timeout=300)

    messages = [{'role': 'user', 'content': 'Reply only with OK.'}]
    payload = {'model': args.model, 'messages': messages, 'stream': args.stream}
    if args.tools:
        messages[0]['content'] = 'Call probe_echo with value ping. After receiving its result, reply with the returned value.'
        payload['tools'] = [{'type': 'function', 'function': {
            'name': 'probe_echo', 'description': 'A harmless connectivity test function.',
            'parameters': {'type': 'object', 'properties': {'value': {'type': 'string'}},
                           'required': ['value'], 'additionalProperties': False}}}]
        payload['tool_choice'] = {'type': 'function', 'function': {'name': 'probe_echo'}}
    with request(payload) as response:
        if args.stream:
            chunks, finished, done = [], False, False
            for raw in response:
                line = raw.decode().strip()
                if not line.startswith('data:'):
                    continue
                data = line[5:].strip()
                if data == '[DONE]':
                    done = True
                    break
                event = json.loads(data)
                if event.get('error'):
                    raise RuntimeError('SSE error event')
                for choice in event.get('choices', []):
                    delta = choice.get('delta', {}).get('content')
                    if delta:
                        chunks.append(delta)
                    if choice.get('finish_reason'):
                        finished = True
            if not (done and finished and ''.join(chunks).strip()):
                raise RuntimeError('Incomplete SSE response: expected content, finish_reason and DONE')
            print('PASS: SSE content, finish_reason and DONE received.')
            return
        result = json.load(response)
    choice = result['choices'][0]
    message = choice['message']
    if not args.tools:
        if not (message.get('content') or '').strip():
            raise RuntimeError('No assistant content')
        print('PASS: non-streaming inference returned content.')
        return
    calls = message.get('tool_calls', [])
    if choice.get('finish_reason') != 'tool_calls' or len(calls) != 1:
        raise RuntimeError('Expected exactly one client-side tool call')
    call = calls[0]
    if call['function']['name'] != 'probe_echo' or json.loads(call['function']['arguments']) != {'value': 'ping'}:
        raise RuntimeError('Unexpected tool name or arguments')
    messages.append(message)
    # The client supplies the result. No model-supplied code is executed.
    messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': '{"value":"pong-verified"}'})
    payload['tool_choice'] = 'none'
    with request(payload) as response:
        followup = json.load(response)['choices'][0]['message']
    if followup.get('tool_calls') or 'pong-verified' not in (followup.get('content') or ''):
        raise RuntimeError('Tool-result round trip failed')
    print('PASS: tool name/arguments/id, client result and final reply verified.')


if __name__ == '__main__':
    main()
